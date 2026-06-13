# Custom CLI Source

`CliSource` is the abstract base class for all CLI sources. To plug in a
different CLI library (click, typer, anything else), subclass it and implement
one method: `_parse_argv() -> dict[str, JSONValue]`.

For the built-in argparse integration, see [ArgparseSource](argparse.md).

## The `_parse_argv` contract

- Top-level args → key = field name.
- Groups / subcommands → emit a discriminator key + prefix the group's args
  with the chosen group name, joined with `self.nested_sep`.
- Bool-style flags — **always** in the result.
- Non-bool args — **only if the user explicitly passed them**.
- The parser/library reads `sys.argv` itself; do not add an `argv=` parameter.

## ClickSource example

Below is a complete `ClickSource` you can copy into your project. It supports
[click](https://click.palletsprojects.com/) groups of arbitrary depth.

=== "Script"

    ```python
    --8<-- "docs/examples/advanced/cli/custom/click_source.py"
    ```

=== "Command"

    ```bash
    --8<-- "docs/examples/advanced/cli/custom/click_source.sh"
    ```

=== "Output"

    ```
    --8<-- "docs/examples/advanced/cli/custom/click_source.stdout"
    ```

A `TyperSource` is a thin wrapper — typer commands are click commands under
the hood, so subclassing `ClickSource` and pointing at the underlying click
group works directly.

!!! warning "Not part of dature's API surface"

    `ClickSource` above is a teaching example. It's not shipped, not tested
    by dature's CI, and not bound by dature's backward-compatibility
    guarantees. Treat it as a starting point for your own implementation.
