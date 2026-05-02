# CLI Source

`ArgparseSource` loads command-line arguments into a dataclass, just like
`JsonSource`/`EnvSource` load files or env vars. It can be combined with other
sources via `load()` so a typical app reads:

```
JSON file (defaults) → env vars (per-deployment) → CLI args (operator overrides)
```

The base class is `CliSource` — abstract, designed so future implementations
(click, typer, your own parser) plug in by overriding a single method.
See [Implementing a custom CLI parser](#implementing-a-custom-cli-parser).

!!! note "Two different CLIs in dature"

    The [`dature` console script](cli.md) (`dature inspect`/`dature validate`)
    is a tool **for** dature. `ArgparseSource` is a Source you compose into
    **your own** application. They are unrelated.

## Quickstart

`ArgparseSource` reads `sys.argv[1:]` via the parser's own `parse_args()` —
there is no separate `argv=` parameter. Want to drive it from custom argv in
tests? Use `monkeypatch.setattr(sys, "argv", [...])`.

=== "Script"

    ```python
    --8<-- "examples/docs/features/cli_source/quickstart.py"
    ```

=== "Command"

    ```bash
    --8<-- "examples/docs/features/cli_source/quickstart.sh"
    ```

=== "Output"

    ```
    --8<-- "examples/docs/features/cli_source/quickstart.stdout"
    ```

## Defaults semantics — bool vs everything else

This is the most subtle rule. It makes merging with other sources predictable:

- **Bool-style actions** (`store_true`, `store_false`, `BooleanOptionalAction`)
  are **always** included in the result. If the user did not pass the flag,
  argparse's default value is used.
- **All other arguments** are included **only if the user explicitly passed
  them**. Argparse defaults for non-bool actions are dropped.

Why: when CLI is one of several sources (env, file, …), unset CLI args must
not silently override values from those sources. A user running
`./app --port 9000` does not want `--env` (with `default="dev"`) to clobber
`env: production` set in the loaded JSON file. Bool flags are different — they
are tri-state in name only (`--debug` / `--no-debug` / unset), and unset
genuinely means "use the declared default".

=== "Script"

    ```python
    --8<-- "examples/docs/features/cli_source/defaults.py"
    ```

=== "Command"

    ```bash
    --8<-- "examples/docs/features/cli_source/defaults.sh"
    ```

=== "Output"

    ```
    --8<-- "examples/docs/features/cli_source/defaults.stdout"
    ```

`--debug` is a bool action → always present. `--env` and `--port` are non-bool
and weren't passed → absent from the dict. The dataclass receiving this data
falls back to its own field defaults for the missing keys.

## Nesting

`CliSource` (and therefore `ArgparseSource`) defaults to `nested_sep="--"`.
A flag like `--db--host` nests as `db.host` in the dataclass:
`ArgparseSource` reads the long-form option string directly (instead of
argparse's `dest`, which collapses every `-` to `_`), so the original
separator survives.

To use a different separator (`.`, `__`, …), pass `nested_sep=` to the source.
For non-default separators that argparse can't preserve in `dest`, set
`dest=` explicitly so the parser stores the separator verbatim.

=== "Script"

    ```python
    --8<-- "examples/docs/features/cli_source/nesting.py"
    ```

=== "Command"

    ```bash
    --8<-- "examples/docs/features/cli_source/nesting.sh"
    ```

=== "Output"

    ```
    --8<-- "examples/docs/features/cli_source/nesting.stdout"
    ```

## Subparsers (and arbitrary nesting)

`ArgparseSource` walks any `add_subparsers(...)` tree, including nested ones.
The subparsers action's `dest` becomes a discriminator, and the chosen
subparser's args go into a sub-dict named after the chosen subparser.

The dataclass: one optional field per subparser plus the discriminator.
Args of subparsers that were **not** chosen are simply absent — adaptix uses
`None` from the dataclass default.

=== "Script"

    ```python
    --8<-- "examples/docs/features/cli_source/subparsers.py"
    ```

=== "Command"

    ```bash
    --8<-- "examples/docs/features/cli_source/subparsers.sh"
    ```

=== "Output"

    ```
    --8<-- "examples/docs/features/cli_source/subparsers.stdout"
    ```

## Bootstrap pattern — peek before `load()`

Sometimes a CLI flag selects which other config file to read. Since
`argparse.ArgumentParser` is stateless across `parse_args()` calls, you can
parse it yourself first, read the value, then hand the same parser to
`ArgparseSource` — the source will parse it again internally, which is cheap.

=== "Script"

    ```python
    --8<-- "examples/docs/features/cli_source/bootstrap.py"
    ```

=== "sources/config.dev.json"

    ```json
    --8<-- "examples/docs/features/cli_source/sources/config.dev.json"
    ```

=== "sources/config.production.json"

    ```json
    --8<-- "examples/docs/features/cli_source/sources/config.production.json"
    ```

=== "Command"

    ```bash
    --8<-- "examples/docs/features/cli_source/bootstrap.sh"
    ```

The order in `load()` controls precedence: with the default `last_wins`,
sources passed later override earlier ones. Put CLI last so operator overrides
win over file defaults.

## Combining with other sources

Standard `load()` rules apply. Only values the CLI explicitly received reach
the merge step (per the [defaults rule](#defaults-semantics--bool-vs-everything-else)),
so you can safely mix CLI with env vars and config files.

=== "Script"

    ```python
    --8<-- "examples/docs/features/cli_source/combining.py"
    ```

=== "sources/config.json"

    ```json
    --8<-- "examples/docs/features/cli_source/sources/config.json"
    ```

=== "Command"

    ```bash
    --8<-- "examples/docs/features/cli_source/combining.sh"
    ```

=== "Output"

    ```
    --8<-- "examples/docs/features/cli_source/combining.stdout"
    ```

## Implementing a custom CLI parser

`CliSource` is an abstract class. To plug in a different CLI library
(click, typer, anything else), subclass it and implement one method:
`_parse_argv() -> dict[str, JSONValue]`.

The contract:

- Top-level args → key = field name.
- Groups / subcommands → emit a discriminator key + prefix the group's args
  with the chosen group name, joined with `self.nested_sep`.
- Bool-style flags — **always** in the result.
- Non-bool args — **only if the user explicitly passed them**.
- The parser/library reads `sys.argv` itself; do not add an `argv=` parameter.

Below is a complete `ClickSource` you can copy into your project. It supports
[click](https://click.palletsprojects.com/) groups of arbitrary depth.

=== "Script"

    ```python
    --8<-- "examples/docs/features/cli_source/click_source.py"
    ```

=== "Command"

    ```bash
    --8<-- "examples/docs/features/cli_source/click_source.sh"
    ```

=== "Output"

    ```
    --8<-- "examples/docs/features/cli_source/click_source.stdout"
    ```

A `TyperSource` is a thin wrapper — typer commands are click commands under
the hood, so subclassing `ClickSource` and pointing at the underlying click
group works directly.

!!! warning "Not part of dature's API surface"

    `ClickSource` above is a teaching example. It's not shipped, not tested
    by dature's CI, and not bound by dature's backward-compatibility
    guarantees. Treat it as a starting point for your own implementation.

## Roadmap

A future PR will add **declarative cross-source interpolation** so that the
bootstrap pattern can be expressed without parsing argv twice:

```python
load(
    JsonSource(file="config.${@cli.env:-dev}.yaml"),
    ArgparseSource(parser=parser, tag="cli"),
    schema=Config,
)
```

The `${@<tag>.<key>}` form is namespaced (the `@` prefix avoids any clash
with the existing `${VAR}` env-var expansion).

## Known limitations

- **Discriminated unions** for subcommands (e.g. `args: CreateArgs | DeleteArgs`)
  are not supported in this iteration. Use one optional field per subparser
  plus a discriminator field, as shown above.
- A subparser whose name equals the subparsers action's `dest` (e.g.
  `add_subparsers(dest="create")` plus `add_parser("create")`) produces a key
  collision. Argparse allows it; we don't catch it. Avoid the pattern.
- Argparse rewrites `-` to `_` in `dest`. To get nested keys, use `__` in the
  flag name or set `dest=` explicitly.
