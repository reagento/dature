import sys
from dataclasses import dataclass
from typing import ClassVar

import click
import dature
from dature.sources.base import CliSource


@dataclass(kw_only=True, repr=False)
class ClickSource(CliSource):
    cli: click.Command
    discriminator: str = "command"
    format_name: ClassVar[str] = "click"

    def _parse_argv(self) -> dict[str, dature.type_aliases.JSONValue]:
        ctx = self.cli.make_context(
            info_name=self.cli.name or "cli",
            args=sys.argv[1:],
            resilient_parsing=False,
        )
        out: dict[str, dature.type_aliases.JSONValue] = {}
        self._walk(ctx, self.cli, prefix=[], out=out)
        return out

    def _walk(
        self,
        ctx: click.Context,
        cmd: click.Command,
        *,
        prefix: list[str],
        out: dict[str, dature.type_aliases.JSONValue],
    ) -> None:
        sep = self.nested_sep
        for param in cmd.params:
            param_name = param.name or ""
            value = ctx.params.get(param_name)
            source = ctx.get_parameter_source(param_name)
            key = sep.join([*prefix, param_name])
            if (
                isinstance(param, click.Option) and param.is_flag
            ) or source == click.core.ParameterSource.COMMANDLINE:
                out[key] = value

        if not isinstance(cmd, click.Group):
            return

        rest = [*getattr(ctx, "protected_args", ()), *ctx.args]
        if not rest:
            return
        sub_name, sub_cmd, sub_args = cmd.resolve_command(ctx, rest)
        if sub_cmd is None or sub_name is None:
            return
        out[sep.join([*prefix, self.discriminator])] = sub_name
        sub_ctx = sub_cmd.make_context(
            info_name=sub_name,
            args=sub_args,
            parent=ctx,
            resilient_parsing=False,
        )
        self._walk(sub_ctx, sub_cmd, prefix=[*prefix, sub_name], out=out)


@click.group(invoke_without_command=True)
@click.option("--verbose", is_flag=True)
def cli(verbose: bool) -> None:  # noqa: FBT001
    pass


@cli.command()
@click.option("--name", required=False)
def create(name: str | None) -> None:
    pass


@cli.command()
@click.option("--item-id", type=int, required=False)
def delete(item_id: int | None) -> None:
    pass


@dataclass
class CreateArgs:
    name: str = "default"


@dataclass
class DeleteArgs:
    item_id: int = 0


@dataclass
class Config:
    command: str | None = None
    verbose: bool = False
    create: CreateArgs | None = None
    delete: DeleteArgs | None = None


def main() -> None:
    config = dature.load(ClickSource(cli=cli), schema=Config)
    print(config)


if __name__ == "__main__":
    main()
