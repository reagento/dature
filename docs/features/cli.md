# CLI

dature ships with a `dature` console script — installed automatically with the package, no extra dependencies. It provides two subcommands:

- [`dature inspect`](#inspect) — print the [LoadReport](../advanced/debug.md) (sources, field origins, merged data) for an existing configuration.
- [`dature validate`](#validate) — load the schema; exit `0` on success, `1` on validation failure, `2` on usage error.

Run `dature --help` for the top-level summary or `dature <command> --help` for per-command flags.

!!! note "Nothing in the CLI is invented"

    Every flag below is a 1-to-1 reflection of an existing Python API:

    - `--schema` → the [`schema`](../api-reference.md#datureload) argument of [`dature.load()`](../api-reference.md#datureload)
    - `--source type=X,k=v,...` → instantiating a [`Source`](../api-reference.md#source) subclass with `k=v` keyword arguments
    - All [global flags](#global-flags) → matching parameters of [`dature.load()`](../api-reference.md#datureload), generated from its signature so they stay in sync automatically

    The only CLI-specific flags are `--field` and `--format` (output filtering and rendering for `inspect`).

## Quick start

A schema module and a JSON config file:

=== "myschema.py"

    ```python
    --8<-- "examples/docs/features/cli/myschema.py"
    ```

=== "sources/config.json"

    ```json
    --8<-- "examples/docs/features/cli/sources/config.json"
    ```

Validate the config — exit `0`, prints `OK`:

=== "Command"

    ```bash
    --8<-- "examples/docs/features/cli/cli_quickstart_validate.sh"
    ```

=== "Output"

    ```
    --8<-- "examples/docs/features/cli/cli_quickstart_validate.stdout"
    ```

Inspect the load report in human-readable form:

=== "Command"

    ```bash
    --8<-- "examples/docs/features/cli/cli_quickstart_inspect_text.sh"
    ```

=== "Output"

    ```
    --8<-- "examples/docs/features/cli/cli_quickstart_inspect_text.stdout"
    ```

## `inspect`

Loads the schema with `debug=True`, retrieves the [`LoadReport`](../advanced/debug.md), and prints it.

```
--8<-- "examples/docs/features/cli/cli_inspect_help.stdout"
```

| Flag | Maps to | Description |
|------|---------|-------------|
| `--field PATH` | *CLI-only* | Filters [`field_origins`](../api-reference.md#loadreport-sourceentry-fieldorigin) and `merged_data` by a dotted path (e.g. `db.port`). Origins matching the path or prefixed by it are shown; merged data is narrowed to the value at that path. |
| `--format {json,text}` | *CLI-only* | Output format. `json` (default) is stable and parseable; `text` is human-readable. |

### JSON output

=== "Command"

    ```bash
    --8<-- "examples/docs/features/cli/cli_inspect_json.sh"
    ```

=== "Output"

    ```json
    --8<-- "examples/docs/features/cli/cli_inspect_json.stdout"
    ```

### Field filter

Narrow the report to a single dotted path — `db.port` here resolves to a scalar in `merged_data`:

=== "Command"

    ```bash
    --8<-- "examples/docs/features/cli/cli_inspect_field.sh"
    ```

=== "Output"

    ```json
    --8<-- "examples/docs/features/cli/cli_inspect_field.stdout"
    ```

## `validate`

Runs `load(*sources, schema=Schema, ...)` and reports the result via exit code. Use it as the final gate in CI/CD.

```
--8<-- "examples/docs/features/cli/cli_validate_help.stdout"
```

| Exit code | Meaning |
|-----------|---------|
| `0` | All sources loaded, schema validated — `OK` printed to stdout. |
| `1` | Loading or validation failed (invalid value, missing source file, merge conflict). Full error written to stderr. |
| `2` | Usage error — bad `--schema` import path, malformed `--source` spec, or class that is not a `dature.Source` subclass. |

Two sources merged with `last_wins`:

=== "Command"

    ```bash
    --8<-- "examples/docs/features/cli/cli_validate_two_sources.sh"
    ```

=== "Output"

    ```
    --8<-- "examples/docs/features/cli/cli_validate_two_sources.stdout"
    ```

When validation fails, the error includes the field path, the offending value, and the source location:

=== "Command"

    ```bash
    --8<-- "examples/docs/features/cli/cli_validate_fail.sh"
    ```

=== "sources/bad.json"

    ```json
    --8<-- "examples/docs/features/cli/sources/bad.json"
    ```

=== "stderr (exit 1)"

    ```
    --8<-- "examples/docs/features/cli/cli_validate_fail.stderr"
    ```

## `--source` spec

Each `--source` is a serialised constructor call for a [`Source`](../api-reference.md#source) subclass. The CLI parses the spec, imports the class, and calls `Class(**kwargs)`:

```
--source type=<ImportPath>[,key=value][,key=value]...
```

- `type` (required) — import path of a class derived from [`Source`](../api-reference.md#source). Both `dature.JsonSource` and `dature.sources.json_:JsonSource` work.
- Other keys map directly to the constructor's keyword arguments — same names, same semantics. The full set is documented under [`Source`](../api-reference.md#source) (base), [`FileSource`](../api-reference.md#filesourcesource) (file-based), and [`FlatKeySource`](../api-reference.md#flatkeysourcesource) (env-style) plus per-class extras under [Source Classes](../api-reference.md#source-classes). Values are parsed as JSON first (e.g. `skip_if_broken=true` → `True`, `port=8080` → `8080`); strings that aren't valid JSON pass through unchanged.

`--source` is repeatable — order matters and is preserved (relevant for `last_wins`/`first_wins` strategies, see [`strategy`](../api-reference.md#datureload)).

### Built-in source types

| `type=` | Class | Required kwargs |
|---------|-------|-----------------|
| `dature.JsonSource` | [JSON](../introduction.md) | `file=` |
| `dature.Json5Source` | JSON5 (extra `[json5]`) | `file=` |
| `dature.Yaml11Source`, `dature.Yaml12Source` | YAML (extra `[yaml]`) | `file=` |
| `dature.Toml10Source`, `dature.Toml11Source` | TOML (extra `[toml]`) | `file=` |
| `dature.IniSource` | INI | `file=` |
| `dature.EnvSource` | OS environment | — |
| `dature.EnvFileSource` | `.env`-style file | `file=` (default `.env`) |
| `dature.DockerSecretsSource` | `/run/secrets`-style dir | `dir_=` |

User-defined `Source` subclasses work too — pass the full import path.

### Escaping commas and equals signs

Use `\,` and `\=` to keep literal `,` / `=` inside a value:

```python
--8<-- "examples/docs/features/cli/cli_source_escape.py"
```

## `--schema MODULE:ATTR`

Import path to the dataclass schema. Internally the CLI passes the resolved class to the [`schema`](../api-reference.md#datureload) parameter of [`dature.load()`](../api-reference.md#datureload). Both `:` and final-dot separators work:

- `myapp.config:Settings` — recommended, unambiguous
- `myapp.config.Settings` — convenient when the class is exported at top level

Nested attributes after `:` are supported: `myapp:Container.Settings`.

## Global flags

These flags are **generated from the signature of [`dature.load()`](../api-reference.md#datureload)** at startup — same names (with `_` → `-`), same types, same defaults. Adding a new parameter to `load()` adds the flag automatically; nothing in the CLI hard-codes the list.

| CLI flag | `load()` parameter | Notes |
|----------|--------------------|-------|
| `--strategy` | [`strategy`](../api-reference.md#datureload) | Choices: `last_wins`, `first_wins`, `first_found`, `raise_on_conflict`. See [Merge Rules](../advanced/merge-rules.md). |
| `--skip-broken-sources` | [`skip_broken_sources`](../api-reference.md#datureload) | See [Skipping Broken Sources](../advanced/merge-rules.md#skipping-broken-sources). |
| `--skip-invalid-fields` | [`skip_invalid_fields`](../api-reference.md#datureload) | See [Skipping Invalid Fields](../advanced/merge-rules.md#skipping-invalid-fields). |
| `--expand-env-vars` | [`expand_env_vars`](../api-reference.md#datureload) | Choices: `disabled`, `default`, `empty`, `strict`. See [ENV Expansion](../advanced/env-expansion.md). |
| `--secret-field-names` | [`secret_field_names`](../api-reference.md#datureload) | Repeatable. See [Masking](masking.md). |
| `--mask-secrets` | [`mask_secrets`](../api-reference.md#datureload) | See [Masking](masking.md). Also affects `inspect` output. |

Per-source overrides for parameters that exist on both `load()` and the [`Source`](../api-reference.md#source) constructor (e.g. [`expand_env_vars`](../api-reference.md#source)) can be passed inside `--source`, e.g. `--source type=...,expand_env_vars=strict`. The Source-level value takes priority — same precedence rules as in code.

## Limitations

The CLI exposes the common case. [`load()`](../api-reference.md#datureload) parameters that require Python objects — [`field_merges`](../api-reference.md#field-merge-strategies), [`field_groups`](../advanced/field-groups.md), [`type_loaders`](../advanced/custom_types.md), callable [`root_validators`](../api-reference.md#root-validator-daturevalidatorsroot), explicit [`field_mapping`](../features/naming.md) — must be expressed in code. For those, use [`dature.load(...)`](../api-reference.md#datureload) directly. The CLI is intentionally not a substitute for the library.

## Implementation note: dogfooding

The `dature` console script parses its own arguments through [`ArgparseSource`](../api-reference.md#argparsesourceflatkeysource) — the very class users instantiate to feed CLI arguments into their own configurations. The dataclass schema that the CLI loads into is built at runtime from the signature of [`load()`](../api-reference.md#datureload) (via `dataclasses.make_dataclass` over `typing.get_type_hints(load)`), so adding or changing a parameter on `load()` is automatically reflected in the CLI without any hand-written wiring. The CLI is not special code: it is dature using itself.
