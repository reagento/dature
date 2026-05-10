# PR2 plan: cross-source interpolation

> **Standalone briefing for a fresh session.** Everything below is self-contained — you do not need any prior conversation.

## Context

dature is a type-safe config loader for Python dataclasses. It loads YAML/JSON/TOML/INI/ENV/Docker secrets/CLI args into a dataclass, with merging across sources.

PR1 (already shipped on branch `task/84-add-cli`) added a CLI Source — `CliSource` (abstract base) and `ArgparseSource` (first concrete implementation). It supports argparse subparsers. The public surface is intentionally minimal: only `ArgparseSource(parser=...)`, no peek methods, no `argv=` parameter — the parser reads `sys.argv` itself via `parse_args()`.

For imperative bootstrap today, the user parses argv themselves and reads the Namespace:

```python
parser = argparse.ArgumentParser()
parser.add_argument("--env", default="dev")

ns = parser.parse_args()  # peek; argparse parsers are stateless

config = load(
    JsonSource(file=f"config.{ns.env}.yaml"),
    ArgparseSource(parser=parser),  # parses argv again inside load() — fine, it's cheap
    schema=Config,
)
```

**This PR (PR2)** adds a **declarative** alternative — let other sources reference the parsed values of "primary" sources directly in their string init fields:

```python
config = load(
    JsonSource(file="config.${@cli.env:-dev}.yaml"),  # <-- the new feature
    ArgparseSource(parser=parser, tag="cli"),
    schema=Config,
)
```

The same mechanism feeds Vault (and other future remote sources) credentials from upstream sources — the canonical bootstrap pattern:

```python
config = load(
    EnvSource(tag="env"),
    VaultSource(
        url="${@env.VAULT_ADDR}",
        token="${@env.VAULT_TOKEN}",
        path="myapp/config",
    ),
    schema=Config,
)
```

The imperative pattern (`parser.parse_args()` + reading the Namespace) **stays** — it's still useful when bootstrap logic needs branching or computation, not just substitution.

## Why this design (decisions made and why)

These were debated in the design phase; do not re-litigate without good reason.

1. **Syntax: `${@<tag>.<key>}` and `${@<tag>.<key>:-<default>}`** — `@` prefix unambiguously distinguishes cross-source refs from existing `${VAR}` env-var expansion. POSIX env-var names cannot start with `@`, so there's **zero overlap** with the existing parser. The dot separates tag from key (and supports nested keys like `${@env.db.host}`).
   - Rejected alternative: `${tag:key}` (Docker-compose-style). It works but requires a look-ahead in the existing env-expand parser to disambiguate `${VAR:-default}` from `${tag:key}`. Higher risk of silent breakage.

2. **Tag = `tag or format_name`.** New optional `tag: str | None = None` field on `Source` base. If unset, `tag` defaults to the source's `format_name` (e.g. `argparse`, `env`, `json`). Users override `tag="primary"` etc. for multi-instance disambiguation. Note: `ArgparseSource` users will likely set `tag="cli"` manually, since `format_name` is `"argparse"` — that's fine, it's an explicit choice.

3. **Resolution scope: any string init field of any Source** — `file` (file-based sources), `dir_` (`DockerSecretsSource`), `url`/`token`/`role_id`/`secret_id` (`VaultSource` and other `RemoteSource` subclasses), and any future Source's string init fields. The orchestration discovers them generically via `dataclasses.fields(source)` (string-typed only) — no hardcoded whitelist. **Not** values inside loaded data (those stay handled by `expand_env_vars` for `${VAR}` only). Smaller surface, less to test, easier to extend later.

4. **Two-phase load with one-level depth:**
   - Phase 1: load all sources whose string init fields contain **no** `${@...}` refs. Build a context dict `{tag: source.cross_ref_data()}`.
   - Phase 2: for sources with `${@...}` refs, interpolate fields against the Phase 1 context, then load.
   - Cycles or Phase-2-references-Phase-2 chains: raise `DatureConfigError`. (Multi-level support can come later if needed; one level covers the bootstrap case.)

5. **Backward compat: existing `expand_env_vars` is untouched.** Cross-source is a new module + new regex. The old `${VAR}` / `${VAR:-default}` paths run independently. Zero risk of tihaya polomka.

6. **CliSource view for cross-ref:** uses the same **explicit-only** view that flows into `load()` (no argparse defaults for non-bool args). Users who want a fallback write `${@cli.env:-dev}`. Exposed through a new internal-ish accessor (see "Architecture" below) — not a new public peek method.

## Architecture

### What "parsed data" is for each Source

The cross-ref lookup `${@<tag>.<key>}` reads from a per-source dict. We need a uniform way for any Source to expose its data **before** `load()` finalises everything:

- For `CliSource`, the data already lives behind `_parse_argv()` / the cached `_parsed` flat dict (see `src/dature/sources/cli_base.py`). Expose it through a new method (see below).
- For `EnvSource`, "parsed data" = its `load_raw().data` (essentially `os.environ` filtered/nested).
- For file sources... they need to be loaded first. **But** if a file source has no cross-refs in its own init fields, it's eligible to be a Phase-1 source whose `load_raw()` runs early.

Add a small method to `Source`:

```python
class Source:
    def cross_ref_data(self) -> dict[str, JSONValue]:
        """Return data this source exposes for ${@tag.key} resolution.

        Default: load_raw().data (nested dict). CliSource overrides to use
        the flat dict from _parse_argv() — keys match argparse dests so users
        write ${@cli.db__host}, not ${@cli.db.host}, when nested_sep="__".
        """
        result = self.load_raw().data
        return result if isinstance(result, dict) else {}
```

For `CliSource`, override `cross_ref_data()` to return the flat parsed dict (the `_parsed` cached_property). Naming choice: this method is intentionally descriptive (`cross_ref_data`) and lives only for the cross-ref machinery — it's not a general-purpose peek API.

### Tag field on Source

Add to `src/dature/sources/base.py` on the `Source` dataclass:

```python
tag: str | None = None
```

Add a property (or static helper) for resolved tag:

```python
@property
def resolved_tag(self) -> str:
    return self.tag if self.tag is not None else self.format_name
```

### New module: `src/dature/expansion/cross_source.py`

Self-contained parser for the new `${@...}` syntax.

```python
# Regex: ${@<tag>.<key>}, optional :- default
# Tag and first key segment must start with letter/underscore.
# Keys can contain dots (for nested paths) and underscores.
_CROSS_RE = re.compile(
    r"\$\{@([a-zA-Z_][\w]*)\.([\w][\w.]*)(?::-((?:[^{}]|\{[^}]*\})*))?\}"
)


def expand_cross_refs(
    text: str,
    *,
    context: dict[str, dict[str, JSONValue]],  # {tag: cross_ref_data() result}
    field_path: list[str] | None = None,  # for error messages
) -> str:
    """Replace every ${@tag.key} (or ${@tag.key:-default}) in `text`.

    Errors:
    - Tag not in context → DatureConfigError with helpful message listing known tags.
    - Key not in tag's data and no default → DatureConfigError.
    - Key path traverses non-dict value mid-way → DatureConfigError.
    """
    ...


def has_cross_refs(text: str) -> bool:
    """Cheap pre-check used to decide which phase a source belongs to."""
    return "${@" in text
```

Lookup logic for nested keys (`${@env.db.host}`):
- Split key on `.` → `["db", "host"]`.
- Walk `context["env"]`. If a step lands on a non-dict, raise error.
- If terminal value is not str/int/float/bool, stringify? For V1, accept only scalar terminal values; raise for dict/list to keep the contract clear.

Default rendering: the `:-default` part is treated as a literal string (no recursive expansion in V1 — keep it dumb).

### Two-phase orchestration

The orchestration code lives in `src/dature/main.py` (function `load`, lines 67–151) and `src/dature/loading/multi.py` (`_load_multi`).

Add a pre-step to `load`:

```python
def load(*sources, schema=None, ...):
    _validate_sources(sources)
    sources = _resolve_cross_refs(sources)  # NEW: returns sources with init fields interpolated
    # ... existing logic from here
```

`_resolve_cross_refs(sources)`:

1. Walk **all** string init fields via `dataclasses.fields(source)` (no hardcoded whitelist of `file`/`dir_`). For each, check `has_cross_refs(value)`. This automatically covers `VaultSource(url=..., token=..., role_id=...)`, `DockerSecretsSource(dir_=...)`, file-based `file=...`, and any future source with string init params.
2. Partition: Phase 1 = sources with NO refs anywhere, Phase 2 = sources with refs.
3. Build the context: for each Phase 1 source, call `source.cross_ref_data()` and stash under `source.resolved_tag`.
4. For each Phase 2 source: clone (or rebuild) it with init fields interpolated against the context. **Do not mutate** the original — produce a new instance so user's variable still works as expected.
5. If any Phase 2 source's resolved init field still contains `${@...}` (chain refs) → raise `DatureConfigError` with "cross-source chain refs not supported" message.
6. Tag collision: if two Phase 1 sources share `resolved_tag`, raise (both can't be referenced unambiguously). Suggest setting explicit `tag=`.
7. Return the new tuple of sources.

**Cloning sources is the tricky part.** Sources are dataclasses (`@dataclass(kw_only=True, repr=False)`), so `dataclasses.replace(source, file=interpolated)` works. But: some sources have `__post_init__` that resolves the file path immediately (e.g. `FileFieldMixin.__post_init__` at `src/dature/sources/base.py:325-327` calls `expand_file_path`). After PR2, that needs to **not** resolve cross-refs at `__post_init__` time — the source must hold the raw template until orchestration interpolates it.

Same in `DockerSecretsSource.__post_init__` (`src/dature/sources/docker_secrets.py:21-23`).

**Approach:** rewrite these `__post_init__` blocks to call a new variant `expand_file_path_preserve_cross_refs` that runs `${VAR}` env-expansion (keeps current behaviour) but **leaves `${@...}` strings intact**. Then `_resolve_cross_refs` does the cross-source pass + final filesystem path normalization.

Or simpler: split env-expansion and path-normalization into two steps; do env-expansion in `__post_init__`, do cross-source-expansion in `_resolve_cross_refs`, do path-normalization (Path conversion etc.) lazily at `_load()` time.

Pick whichever is less invasive — the first approach (single new function that skips `${@...}`) is probably less code.

**`RemoteSource` subclasses** (e.g. `VaultSource`) typically don't have file-path normalization in `__post_init__`, so for them `dataclasses.replace(source, **interpolated)` (or the `copy.copy + vars().update()` style used by `apply_source_init_params`) is enough — no special preservation logic needed. The string fields (`url`, `token`, etc.) are stored verbatim and only consumed at `_fetch()` time.

## Files to touch

### New

| File | What |
|---|---|
| `src/dature/expansion/cross_source.py` | `_CROSS_RE`, `expand_cross_refs`, `has_cross_refs`, error types |
| `tests/expansion/test_cross_source.py` | unit tests for the regex + expansion logic |
| `tests/loading/test_cross_source_loading.py` | end-to-end loading tests with cross-refs |
| `docs/features/cross_source_refs.md` | user-facing docs |
| `examples/cross_source_example.py` | working example |
| `changes/<NEW_ISSUE>.feature` | changelog fragment |

### Modified

| File | Change |
|---|---|
| `src/dature/sources/base.py` | Add `tag: str \| None = None` and `resolved_tag` property to `Source`. Modify `FileFieldMixin.__post_init__` (line 325) to skip `${@...}` patterns when expanding. Add `cross_ref_data()` method (default: returns `load_raw().data` if dict else `{}`). Note: cross-ref orchestration walks `dataclasses.fields(source)` generically, so it covers any future `RemoteSource` subclasses (`VaultSource` etc.) without special-casing |
| `src/dature/sources/cli_base.py` | Override `cross_ref_data()` on `CliSource` to return the flat `_parsed` dict (so argparse `dest` names are usable directly in refs) |
| `src/dature/sources/docker_secrets.py` | Same `__post_init__` adjustment as `FileFieldMixin` (line 21-23) |
| `src/dature/expansion/env_expand.py` | **Do not modify the regex.** If sharing helpers helps, factor; otherwise leave alone |
| `src/dature/main.py` | In `load()` (line 67), insert call to `_resolve_cross_refs(sources)` before existing logic. Probably extract the helper to a new file `src/dature/loading/cross_source.py` to keep `main.py` thin |
| `src/dature/loading/merge_config.py` | The Vault-PR introduces `apply_source_config_defaults` here for global-config fallback. **Order matters:** PR2's `_resolve_cross_refs` must run **before** `MergeConfig.__post_init__` (which calls `apply_source_init_params` + `apply_source_config_defaults`), so that interpolated string values are present when global-config merge happens |
| `src/dature/loading/__init__.py` | Export the new helper if needed |
| `src/dature/__init__.py` | Nothing (cross-source is implicit via `${@...}`; no new public class) |
| `mkdocs.yml` | Nav entry for `features/cross_source_refs.md` |

## Implementation order

1. Module + tests for the regex and `expand_cross_refs` (pure-function, easy to test in isolation).
2. Add `tag` + `resolved_tag` + `cross_ref_data()` on `Source`. Override `cross_ref_data()` in `CliSource`.
3. Adjust `__post_init__` in `FileFieldMixin` and `DockerSecretsSource` to leave `${@...}` strings intact.
4. Write `_resolve_cross_refs(sources)` orchestration helper. Tests in isolation.
5. Wire into `load()`. End-to-end tests.
6. Docs + example + changelog fragment.

## Tests

### `tests/expansion/test_cross_source.py`

Use `@pytest.mark.parametrize` for similar cases (project rule).

- **Regex matching**:
  - Parametrize over `"${@cli.env}"`, `"${@cli.db.host}"`, `"${@env.HOME:-default}"`, etc. → verify match groups.
  - Negative cases: `"${VAR}"`, `"${@}"`, `"${@cli}"` (no key), `"${@.env}"` (no tag) → no match (or fall through to literal).
- **Resolution**:
  - Tag found, key found → returns value.
  - Tag found, key missing, default present → returns default.
  - Tag found, key missing, no default → raises `DatureConfigError`.
  - Tag missing → raises (message lists known tags).
  - Nested key path (`db.host`) → walks dict, returns scalar.
  - Path traverses non-dict → raises.
- **Mixed strings**: `"prefix-${@cli.env}-suffix"` → correct interpolation. `"${VAR}-${@cli.env}"` → both are independent (env-expansion ran earlier; cross-source runs after).

### `tests/loading/test_cross_source_loading.py`

End-to-end. Parametrize where similar.

- `test_basic_cross_ref`: `JsonSource(file="config.${@cli.env}.json")` + `ArgparseSource(tag="cli", argv=["--env","prod"])` → loads `config.prod.json`.
- `test_with_default`: `--env` not passed → default `dev` used.
- `test_default_unused_when_value_present`.
- `test_unknown_tag_raises_with_helpful_message`.
- `test_cycle_detection`: source A refs source B refs source A → raises.
- `test_chain_refs_unsupported`: source A refs source B (which itself has refs) → raises with "chain refs not supported in V1".
- `test_tag_collision_raises`: two `EnvSource()` instances without explicit `tag` → both default to `tag="env"` → raises (suggest explicit tag).
- `test_explicit_tag_overrides_format_name`: `EnvSource(tag="primary_env")` works.
- `test_dir_field_on_docker_secrets`: works on `DockerSecretsSource(dir_="...${@cli.env}...")`.
- `test_existing_var_expansion_still_works`: `${VAR}` in init fields keeps working unchanged.
- `test_combined_var_and_cross_ref`: `"${HOME}/${@cli.env}/x"` resolves both.
- `test_cli_cross_ref_uses_explicit_only`: argparse default for non-bool — referenced via `${@cli.x}` without `:-` → raises (explicit-only semantics).
- `test_vault_token_from_env` (`@pytest.mark.integration`): `VaultSource(url="${@env.VAULT_ADDR}", token="${@env.VAULT_TOKEN}", path="myapp/config")` + `EnvSource(tag="env")` + `monkeypatch.setenv("VAULT_TOKEN", "...")` → reads from a live Vault container. Verifies cross-ref orchestration runs **before** `apply_source_config_defaults` so the interpolated values are present at merge time.
- `test_vault_url_from_cli` (`@pytest.mark.integration`): URL piped from `ArgparseSource(tag="cli")` into `VaultSource`.

### Regression

Existing tests must keep passing — especially `tests/expansion/test_env_expand.py` and `tests/sources/test_*` — since we touch `__post_init__` of file-based sources.

## Verification

```bash
uv run prek run -a       # ruff + mypy
uv run pytest -q         # full suite
uv run pytest tests/expansion/test_cross_source.py tests/loading/test_cross_source_loading.py -xvs
```

End-to-end:

```bash
.venv/bin/python examples/cross_source_example.py
```

After implementation: run `/done`.

## Open questions / refinements

These are not blockers but worth deciding once you start coding:

1. **`tag` default for `ArgparseSource`** — currently `format_name="argparse"`, so default tag is `"argparse"`. Users will probably want `${@cli.env}`, requiring `tag="cli"`. Options:
   - Leave as-is, document; users set `tag="cli"` explicitly.
   - Override `format_name = "cli"` in `CliSource` base (but it's abstract, so concrete classes still need their own).
   - Add a separate `default_tag` ClassVar that defaults to `format_name` but can be overridden. `CliSource.default_tag = "cli"`.
   - **Recommendation:** keep `tag = tag or format_name` as the unified rule, document the `tag="cli"` idiom prominently. Avoids special cases.

2. **What `cross_ref_data()` returns for a file source with nested data** — its `load_raw().data` is a nested dict. `${@json.db.host}` should walk it. Verify that `expand_cross_refs` walks dicts the same way for any source type (it should, if implementation is uniform).

3. **Stringification of non-scalar lookups** — e.g. `${@json.db}` where `db` is a sub-dict. Either:
   - Raise (user must reference a scalar).
   - Render as JSON.
   - **Recommendation:** raise. Less surprise.

4. **Empty parsed dict vs no source** — if `cli.cross_ref_data()` is `{}` (no args passed) and user writes `${@cli.env}` without default → raises "key not in tag's data". Make sure error is distinguishable from "tag not registered".

5. **Does `cross_ref_data()` need to be called lazily?** I.e. only if some source has cross-refs. Eager is simpler; lazy avoids unnecessary `load_raw()` for sources nobody references. Probably eager-with-caching is fine; revisit if perf matters.

6. **Should `tag` collisions WARN or RAISE?** Raising is safer (forces explicit disambiguation). Warning lets the first one win silently — bad. Raise.

7. **Vault secret missing from upstream + no default** — e.g. `VaultSource(token="${@env.VAULT_TOKEN}")` and `VAULT_TOKEN` is unset. The error should say "key not in tag's data" with the full `${@env.VAULT_TOKEN}` reference quoted, so the user immediately sees that the token wasn't propagated (vs. a generic missing-env complaint). The current "key not in tag's data" path covers this — no Vault-specific handling needed, but verify the error message includes the original ref string.

## Pointers to existing code (PR1 is your model)

- `src/dature/sources/cli_base.py` — `CliSource` (abstract base). Look at the cached `_parsed` property and the abstract `_parse_argv()` — that's the data PR2's `cross_ref_data()` override needs to expose.
- `src/dature/sources/argparse_.py` — `ArgparseSource` (concrete implementation, with subparsers). Models how a concrete subclass plugs in.
- `src/dature/sources/base.py` line 49 — `Source` dataclass; this is where `tag` goes.
- `src/dature/sources/base.py` line 325 — `FileFieldMixin.__post_init__` — this is the call site that needs to stop expanding when string contains `${@...}`.
- `src/dature/expansion/env_expand.py` — current expansion logic, especially `_VAR_RE` (line 8) and `expand_string` (line 99). **Don't touch this file**; mirror its style in your new `cross_source.py`.
- `src/dature/main.py` line 67 — `load()` is where you splice in `_resolve_cross_refs(sources)`.
- `tests/sources/test_cli.py` — `TestArgparseSourcePeekApi::test_bootstrap_pattern_e2e` — that's the imperative pattern PR2 makes declarative. Mirror its setup in PR2 tests.

## Out of scope (do NOT do in PR2)

- Cross-refs **inside loaded data** (e.g. `db_url: "postgres://${@cli.env}.db"` inside the JSON file). Stays env-var-only via `expand_env_vars`. Could be PR3.
- Multi-level refs (Phase 2 → Phase 2). One level covers bootstrap.
- Auto-tag collision resolution (we just raise).
- Click/Typer source implementations. PR1's docs include a teaching example for `ClickSource`.
- Discriminated unions for argparse subparsers (mentioned in PR1's "known limitations").

## Branch & changelog

- New branch: `task/<N>-cross-source-refs` (use the next issue number after 84).
- Changelog: `changes/<N>.feature` with a single paragraph describing the new `${@tag.key}` syntax, scope (init fields only), backward-compat note (existing `${VAR}` untouched).
