"""Tests for ArgparseSource."""

import argparse
import sys
from collections.abc import Callable
from dataclasses import dataclass
from typing import Literal

import pytest

from dature import ArgparseSource, JsonSource, load


def _flat_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--name")
    parser.add_argument("--port", type=int)
    parser.add_argument("--debug", action="store_true")
    return parser


def _subparser_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--verbose", action="store_true")
    subs = parser.add_subparsers(dest="command")
    create = subs.add_parser("create")
    create.add_argument("--name")
    delete = subs.add_parser("delete")
    delete.add_argument("--item-id", type=int)
    return parser


@pytest.fixture
def set_argv(monkeypatch: pytest.MonkeyPatch) -> Callable[[list[str]], None]:
    def _set(argv: list[str]) -> None:
        monkeypatch.setattr(sys, "argv", ["prog", *argv])

    return _set


@dataclass
class _FlatConfig:
    name: str
    port: int
    debug: bool = False


@dataclass
class _CreateArgs:
    name: str


@dataclass
class _DeleteArgs:
    item_id: int


@dataclass
class _SubConfig:
    command: str
    verbose: bool = False
    create: _CreateArgs | None = None
    delete: _DeleteArgs | None = None


class TestArgparseSourceFlat:
    def test_basic_string_args(self, set_argv: Callable[[list[str]], None]):
        set_argv(["--name", "foo", "--port", "5432"])
        result = load(ArgparseSource(parser=_flat_parser()), schema=_FlatConfig)

        assert result == _FlatConfig(name="foo", port=5432, debug=False)

    def test_flat_dict_via_load_raw(self, set_argv: Callable[[list[str]], None]):
        set_argv(["--port", "8080"])
        src = ArgparseSource(parser=_flat_parser())

        assert src.load_raw().data == {"port": 8080, "debug": False}

    @pytest.mark.parametrize(
        ("action_kwargs", "argv", "expected_value"),
        [
            pytest.param({"action": "store_true"}, ["--flag"], True, id="store_true_passed"),
            pytest.param({"action": "store_true"}, [], False, id="store_true_default"),
            pytest.param({"action": "store_false"}, ["--flag"], False, id="store_false_passed"),
            pytest.param({"action": "store_false"}, [], True, id="store_false_default"),
            pytest.param(
                {"action": argparse.BooleanOptionalAction},
                ["--flag"],
                True,
                id="bool_optional_yes",
            ),
            pytest.param(
                {"action": argparse.BooleanOptionalAction},
                ["--no-flag"],
                False,
                id="bool_optional_no",
            ),
        ],
    )
    def test_bool_actions(
        self,
        set_argv: Callable[[list[str]], None],
        action_kwargs: dict[Literal["action"], str | type[argparse.Action]],
        argv: list[str],
        expected_value: bool,
    ):
        set_argv(argv)
        parser = argparse.ArgumentParser()
        parser.add_argument("--flag", **action_kwargs)
        src = ArgparseSource(parser=parser)

        assert src.load_raw().data == {"flag": expected_value}

    def test_bool_optional_action_default_when_absent(self, set_argv: Callable[[list[str]], None]):
        set_argv([])
        parser = argparse.ArgumentParser()
        parser.add_argument("--flag", action=argparse.BooleanOptionalAction, default=True)
        src = ArgparseSource(parser=parser)

        assert src.load_raw().data == {"flag": True}

    @pytest.mark.parametrize(
        ("action_kwargs", "argv", "expected"),
        [
            pytest.param(
                {"action": "store_true", "default": None},
                [],
                {},
                id="store_true_none_default_absent_dropped",
            ),
            pytest.param(
                {"action": "store_true", "default": None},
                ["--flag"],
                {"flag": True},
                id="store_true_none_default_passed",
            ),
            pytest.param(
                {"action": argparse.BooleanOptionalAction, "default": None},
                [],
                {},
                id="bool_optional_none_default_absent_dropped",
            ),
            pytest.param(
                {"action": argparse.BooleanOptionalAction, "default": None},
                ["--flag"],
                {"flag": True},
                id="bool_optional_none_default_passed",
            ),
        ],
    )
    def test_bool_with_none_default_suppressed_when_absent(
        self,
        set_argv: Callable[[list[str]], None],
        action_kwargs: dict[str, object],
        argv: list[str],
        expected: dict[str, bool],
    ):
        set_argv(argv)
        parser = argparse.ArgumentParser()
        parser.add_argument("--flag", **action_kwargs)
        src = ArgparseSource(parser=parser)

        assert src.load_raw().data == expected

    @pytest.mark.parametrize(
        ("type_", "default", "argv", "expected_present"),
        [
            pytest.param(int, 8080, [], False, id="int_default_dropped"),
            pytest.param(int, 8080, ["--x", "9"], True, id="int_passed"),
            pytest.param(str, "hello", [], False, id="str_default_dropped"),
            pytest.param(str, "hello", ["--x", "world"], True, id="str_passed"),
            pytest.param(float, 1.5, [], False, id="float_default_dropped"),
        ],
    )
    def test_non_bool_default_dropped_unless_passed(
        self,
        set_argv: Callable[[list[str]], None],
        type_: type,
        default: object,
        argv: list[str],
        expected_present: bool,
    ):
        set_argv(argv)
        parser = argparse.ArgumentParser()
        parser.add_argument("--x", type=type_, default=default)
        src = ArgparseSource(parser=parser)
        data = src.load_raw().data

        assert isinstance(data, dict)
        assert ("x" in data) == expected_present

    def test_help_action_ignored(self, set_argv: Callable[[list[str]], None]):
        set_argv(["--name", "x"])
        parser = argparse.ArgumentParser()
        parser.add_argument("--name")
        src = ArgparseSource(parser=parser)
        data = src.load_raw().data

        assert isinstance(data, dict)
        assert "help" not in data

    def test_nargs_list_passed_through(self, set_argv: Callable[[list[str]], None]):
        set_argv(["--items", "a", "b", "c"])
        parser = argparse.ArgumentParser()
        parser.add_argument("--items", nargs="+")
        src = ArgparseSource(parser=parser)

        assert src.load_raw().data == {"items": ["a", "b", "c"]}

    def test_nested_via_double_dash(self, set_argv: Callable[[list[str]], None]):
        @dataclass
        class _Db:
            host: str
            port: int

        @dataclass
        class _Cfg:
            db: _Db

        set_argv(["--db--host", "localhost", "--db--port", "5432"])
        parser = argparse.ArgumentParser()
        parser.add_argument("--db--host", required=True)
        parser.add_argument("--db--port", type=int, required=True)
        result = load(ArgparseSource(parser=parser), schema=_Cfg)

        assert result == _Cfg(db=_Db(host="localhost", port=5432))

    def test_nested_sep_dot(self, set_argv: Callable[[list[str]], None]):
        @dataclass
        class _Db:
            host: str

        @dataclass
        class _Cfg:
            db: _Db

        set_argv(["--db.host", "localhost"])
        parser = argparse.ArgumentParser()
        parser.add_argument("--db.host", dest="db.host", required=True)
        result = load(ArgparseSource(parser=parser, nested_sep="."), schema=_Cfg)

        assert result == _Cfg(db=_Db(host="localhost"))

    def test_prefix_filtering(self, set_argv: Callable[[list[str]], None]):
        set_argv(["--myapp_foo", "1", "--bar", "2"])
        parser = argparse.ArgumentParser()
        parser.add_argument("--myapp_foo", dest="myapp_foo")
        parser.add_argument("--bar")
        src = ArgparseSource(parser=parser, prefix="myapp_")

        assert src.load_raw().data == {"foo": "1"}

    def test_parser_not_mutated_after_parse(self, set_argv: Callable[[list[str]], None]):
        set_argv(["--verbose", "create", "--name", "x"])
        parser = _subparser_parser()
        defaults_before = {a.dest: a.default for a in parser._actions}
        for action in parser._actions:
            if isinstance(action, argparse._SubParsersAction):
                for sp in action.choices.values():
                    defaults_before.update({(action.dest, a.dest): a.default for a in sp._actions})

        src = ArgparseSource(parser=parser)
        src.load_raw()

        defaults_after = {a.dest: a.default for a in parser._actions}
        for action in parser._actions:
            if isinstance(action, argparse._SubParsersAction):
                for sp in action.choices.values():
                    defaults_after.update({(action.dest, a.dest): a.default for a in sp._actions})

        assert defaults_before == defaults_after


class TestArgparseSourceSubparsers:
    def test_basic_subparsers_create(self, set_argv: Callable[[list[str]], None]):
        set_argv(["create", "--name", "foo"])
        result = load(ArgparseSource(parser=_subparser_parser()), schema=_SubConfig)

        assert result == _SubConfig(
            command="create",
            verbose=False,
            create=_CreateArgs(name="foo"),
            delete=None,
        )

    def test_basic_subparsers_delete(self, set_argv: Callable[[list[str]], None]):
        set_argv(["delete", "--item-id", "5"])
        result = load(ArgparseSource(parser=_subparser_parser()), schema=_SubConfig)

        assert result == _SubConfig(
            command="delete",
            verbose=False,
            create=None,
            delete=_DeleteArgs(item_id=5),
        )

    def test_subparser_bool_default_included(self, set_argv: Callable[[list[str]], None]):
        set_argv(["create"])
        parser = argparse.ArgumentParser()
        subs = parser.add_subparsers(dest="command")
        create = subs.add_parser("create")
        create.add_argument("--debug", action="store_true")

        src = ArgparseSource(parser=parser)

        assert src.load_raw().data == {"command": "create", "create": {"debug": False}}

    def test_unselected_subparser_args_absent(self, set_argv: Callable[[list[str]], None]):
        set_argv(["delete", "--item-id", "5"])
        src = ArgparseSource(parser=_subparser_parser())
        data = src.load_raw().data

        assert isinstance(data, dict)
        assert "create" not in data
        assert data == {"command": "delete", "verbose": False, "delete": {"item_id": 5}}

    def test_nested_subparsers(self, set_argv: Callable[[list[str]], None]):
        set_argv(["user", "create", "--name", "alice"])
        parser = argparse.ArgumentParser()
        top = parser.add_subparsers(dest="action")
        user = top.add_parser("user")
        user_subs = user.add_subparsers(dest="user_op")
        user_create = user_subs.add_parser("create")
        user_create.add_argument("--name")

        src = ArgparseSource(parser=parser)

        assert src.load_raw().data == {
            "action": "user",
            "user": {
                "user_op": "create",
                "create": {"name": "alice"},
            },
        }

    def test_required_subparser_missing(self, set_argv: Callable[[list[str]], None]):
        set_argv([])
        parser = argparse.ArgumentParser()
        subs = parser.add_subparsers(dest="command", required=True)
        subs.add_parser("create")

        src = ArgparseSource(parser=parser)

        with pytest.raises(SystemExit):
            src.load_raw()

    def test_top_level_args_with_subparsers(self, set_argv: Callable[[list[str]], None]):
        set_argv(["--verbose", "create", "--name", "foo"])
        result = load(ArgparseSource(parser=_subparser_parser()), schema=_SubConfig)

        assert result == _SubConfig(
            command="create",
            verbose=True,
            create=_CreateArgs(name="foo"),
            delete=None,
        )


class TestArgparseSourceMergeWithJson:
    def test_cli_overrides_json_when_passed(self, set_argv: Callable[[list[str]], None], tmp_path):
        @dataclass
        class _Cfg:
            host: str
            port: int

        (tmp_path / "config.json").write_text('{"host": "localhost", "port": 8080}')

        set_argv(["--port", "9000"])
        parser = argparse.ArgumentParser()
        parser.add_argument("--host")
        parser.add_argument("--port", type=int)

        result = load(
            JsonSource(file=tmp_path / "config.json"),
            ArgparseSource(parser=parser),
            schema=_Cfg,
        )

        assert result == _Cfg(host="localhost", port=9000)


class TestArgparseSourceDisplayProperties:
    def test_format_name_and_label(self):
        assert ArgparseSource.format_name == "argparse"
        assert ArgparseSource.location_label == "CLI"


class TestArgparseSourceResolveLocation:
    def test_resolve_returns_flag_name_top_level(self):
        parser = argparse.ArgumentParser()
        parser.add_argument("--host")
        src = ArgparseSource(parser=parser)

        locations = src.resolve_location(
            field_path=["host"],
            file_content=None,
            nested_conflict=None,
        )

        assert len(locations) == 1
        assert locations[0].env_var_name == "--HOST"
        assert locations[0].location_label == "CLI"

    def test_resolve_returns_flag_name_nested(self):
        parser = argparse.ArgumentParser()
        parser.add_argument("--db--host")
        src = ArgparseSource(parser=parser)

        locations = src.resolve_location(
            field_path=["db", "host"],
            file_content=None,
            nested_conflict=None,
        )

        assert len(locations) == 1
        assert locations[0].env_var_name == "--DB--HOST"
