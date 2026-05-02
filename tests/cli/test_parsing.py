"""Tests for dature.cli.parsing."""

import argparse
import inspect
from dataclasses import fields, is_dataclass
from typing import Any, Literal, get_args, get_origin

import pytest

from dature import EnvSource, JsonSource
from dature.cli.parsing import (
    CLI_LOAD_PARAMS,
    add_common_args,
    add_load_args,
    add_typed_arg,
    build_load_kwargs_from_dataclass,
    build_sources,
    derive_cli_schema,
    import_attr,
    parse_source_spec,
    parse_value,
    split_escaped,
)
from dature.main import load


class TestImportAttr:
    @pytest.mark.parametrize(
        ("path", "expected_name"),
        [
            ("dature.JsonSource", "JsonSource"),
            ("dature:JsonSource", "JsonSource"),
            ("dature.sources.json_:JsonSource", "JsonSource"),
            ("dature.sources.env_.EnvSource", "EnvSource"),
        ],
    )
    def test_resolves(self, path, expected_name):
        obj = import_attr(path)
        assert getattr(obj, "__name__", None) == expected_name

    @pytest.mark.parametrize(
        ("path", "exc_type"),
        [
            ("noColonAndNoDot", ValueError),
            ("dature:NoSuchClass", AttributeError),
            ("nosuchmodule:Anything", ModuleNotFoundError),
        ],
    )
    def test_errors(self, path, exc_type):
        with pytest.raises(exc_type):
            import_attr(path)


class TestParseValue:
    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            ("hello", "hello"),
            ("42", 42),
            ("3.14", 3.14),
            ("true", True),
            ("false", False),
            ("null", None),
            ('"quoted"', "quoted"),
            ("[1,2,3]", [1, 2, 3]),
            ('{"a": 1}', {"a": 1}),
            ("not json", "not json"),
        ],
    )
    def test_parse(self, raw, expected):
        assert parse_value(raw) == expected


class TestSplitEscaped:
    @pytest.mark.parametrize(
        ("text", "sep", "expected"),
        [
            ("a,b,c", ",", ["a", "b", "c"]),
            (r"a\,b,c", ",", ["a,b", "c"]),
            ("k=v", "=", ["k", "v"]),
            (r"k\=name=v", "=", ["k=name", "v"]),
            ("", ",", [""]),
            (r"a\,b\,c", ",", ["a,b,c"]),
        ],
    )
    def test_split(self, text, sep, expected):
        assert split_escaped(text, sep) == expected

    def test_unsupported_separator(self):
        with pytest.raises(ValueError, match="separator"):
            split_escaped("a;b", ";")


class TestParseSourceSpec:
    def test_minimal(self):
        klass, kwargs = parse_source_spec("type=dature.JsonSource,file=/path/to/dir/a.json")
        assert klass is JsonSource
        assert kwargs == {"file": "/path/to/dir/a.json"}

    def test_multiple_kwargs(self):
        klass, kwargs = parse_source_spec(
            "type=dature.EnvSource,prefix=APP_,nested_sep=__",
        )
        assert klass is EnvSource
        assert kwargs == {"prefix": "APP_", "nested_sep": "__"}

    def test_json_value(self):
        klass, kwargs = parse_source_spec(
            "type=dature.EnvSource,prefix=APP_,skip_if_broken=true",
        )
        assert klass is EnvSource
        assert kwargs == {"prefix": "APP_", "skip_if_broken": True}

    @pytest.mark.parametrize(
        "spec",
        [
            r"type=dature.EnvSource,prefix=A\,B",
            r"type=dature.EnvSource,prefix=A\,B,nested_sep=__",
        ],
    )
    def test_escaped_comma_in_value(self, spec):
        klass, kwargs = parse_source_spec(spec)
        assert klass is EnvSource
        assert kwargs["prefix"] == "A,B"

    def test_escaped_equals(self):
        klass, kwargs = parse_source_spec(
            r"type=dature.EnvSource,prefix=k\=v",
        )
        assert klass is EnvSource
        assert kwargs == {"prefix": "k=v"}

    @pytest.mark.parametrize(
        ("spec", "exc_type", "match"),
        [
            ("file=/tmp/a.json", ValueError, "Missing required 'type"),
            ("type=dature.JsonSource,brokenpair", ValueError, "expected 'key=value'"),
            ("type=dature.JsonSource,=value", ValueError, "Empty key"),
            ("type=dature.JsonSource,file=a,file=b", ValueError, "Duplicate"),
            ("type=os.path", TypeError, "not a subclass"),
        ],
    )
    def test_errors(self, spec, exc_type, match):
        with pytest.raises(exc_type, match=match):
            parse_source_spec(spec)


class TestBuildSources:
    def test_instances(self, tmp_path):
        cfg = tmp_path / "x.json"
        cfg.write_text("{}")
        srcs = build_sources(
            [
                f"type=dature.JsonSource,file={cfg}",
                "type=dature.EnvSource,prefix=APP_",
            ],
        )
        assert len(srcs) == 2
        assert isinstance(srcs[0], JsonSource)
        assert isinstance(srcs[1], EnvSource)
        assert srcs[1].prefix == "APP_"


class TestAddTypedArg:
    @pytest.mark.parametrize(
        ("annotation", "argv", "expected"),
        [
            (bool, ["--flag"], True),
            (bool | None, ["--flag"], True),
            (Literal["a", "b"], ["--flag", "a"], "a"),
            (Literal["a", "b"] | None, ["--flag", "b"], "b"),
            (str, ["--flag", "hello"], "hello"),
            (str | None, ["--flag", "hello"], "hello"),
            (tuple[str, ...], ["--flag", "x", "--flag", "y"], ["x", "y"]),
            (tuple[str, ...] | None, ["--flag", "x"], ["x"]),
        ],
    )
    def test_supported(self, annotation, argv, expected):
        parser = argparse.ArgumentParser()
        add_typed_arg(parser, "flag", annotation)
        ns = parser.parse_args(argv)
        assert ns.flag == expected

    def test_default_when_omitted(self):
        parser = argparse.ArgumentParser()
        add_typed_arg(parser, "flag", bool | None)
        ns = parser.parse_args([])
        assert ns.flag is None

    def test_unsupported_type(self):
        parser = argparse.ArgumentParser()
        with pytest.raises(TypeError, match="Unsupported"):
            add_typed_arg(parser, "f", dict[str, int])


class TestAddLoadArgs:
    def test_all_params_resolve_in_signature(self):
        sig = inspect.signature(load)
        for name in CLI_LOAD_PARAMS:
            assert name in sig.parameters, f"{name} not in load() signature"

    def test_flags_present(self):
        parser = argparse.ArgumentParser()
        add_load_args(parser)
        ns = parser.parse_args(
            [
                "--strategy",
                "first_wins",
                "--skip-broken-sources",
                "--mask-secrets",
                "--secret-field-names",
                "password",
                "--secret-field-names",
                "api_key",
            ],
        )
        assert ns.strategy == "first_wins"
        assert ns.skip_broken_sources is True
        assert ns.mask_secrets is True
        assert ns.secret_field_names == ["password", "api_key"]


class TestBuildLoadKwargsFromDataclass:
    def test_drops_none(self):
        cls = derive_cli_schema()
        validate_field = next(f for f in fields(cls) if f.name == "validate")
        validate_args = _strip_optional(validate_field.type)(
            schema="x:Y",
            source=["type=dature.EnvSource"],
            strategy="last_wins",
            mask_secrets=True,
        )
        assert build_load_kwargs_from_dataclass(validate_args) == {
            "strategy": "last_wins",
            "mask_secrets": True,
        }

    def test_all_none_returns_empty(self):
        cls = derive_cli_schema()
        validate_field = next(f for f in fields(cls) if f.name == "validate")
        validate_args = _strip_optional(validate_field.type)(
            schema="x:Y",
            source=["type=dature.EnvSource"],
        )
        assert build_load_kwargs_from_dataclass(validate_args) == {}


class TestDeriveCliSchema:
    def test_top_level_fields(self):
        cls = derive_cli_schema()
        names = {f.name for f in fields(cls)}
        assert names == {"command", "inspect", "validate"}

    def test_command_is_literal(self):
        cls = derive_cli_schema()
        command_field = next(f for f in fields(cls) if f.name == "command")
        assert get_origin(command_field.type) is Literal
        assert set(get_args(command_field.type)) == {"inspect", "validate"}

    def test_cached(self):
        assert derive_cli_schema() is derive_cli_schema()

    @pytest.mark.parametrize("subcommand", ["inspect", "validate"])
    def test_subcommand_has_schema_and_source(self, subcommand):
        cls = derive_cli_schema()
        sub_field = next(f for f in fields(cls) if f.name == subcommand)
        sub_cls = _strip_optional(sub_field.type)
        assert is_dataclass(sub_cls)
        sub_names = {f.name for f in fields(sub_cls)}
        assert {"schema", "source"} <= sub_names

    @pytest.mark.parametrize("subcommand", ["inspect", "validate"])
    def test_subcommand_has_all_load_params(self, subcommand):
        cls = derive_cli_schema()
        sub_field = next(f for f in fields(cls) if f.name == subcommand)
        sub_cls = _strip_optional(sub_field.type)
        sub_names = {f.name for f in fields(sub_cls)}
        assert set(CLI_LOAD_PARAMS) <= sub_names

    def test_inspect_has_field_and_format(self):
        cls = derive_cli_schema()
        inspect_field = next(f for f in fields(cls) if f.name == "inspect")
        inspect_cls = _strip_optional(inspect_field.type)
        names = {f.name for f in fields(inspect_cls)}
        assert "field" in names
        assert "format" in names

    def test_validate_has_no_field_or_format(self):
        cls = derive_cli_schema()
        validate_field = next(f for f in fields(cls) if f.name == "validate")
        validate_cls = _strip_optional(validate_field.type)
        names = {f.name for f in fields(validate_cls)}
        assert "field" not in names
        assert "format" not in names

    def test_load_params_optional_with_none_default(self):
        cls = derive_cli_schema()
        validate_field = next(f for f in fields(cls) if f.name == "validate")
        validate_cls = _strip_optional(validate_field.type)
        for f in fields(validate_cls):
            if f.name in CLI_LOAD_PARAMS:
                assert f.default is None, f"{f.name} should default to None"
                args = get_args(f.type)
                assert type(None) in args, f"{f.name} should be Optional"

    def test_secret_field_names_is_list_str(self):
        cls = derive_cli_schema()
        validate_field = next(f for f in fields(cls) if f.name == "validate")
        validate_cls = _strip_optional(validate_field.type)
        f = next(f for f in fields(validate_cls) if f.name == "secret_field_names")
        non_none = [a for a in get_args(f.type) if a is not type(None)]
        assert non_none == [list[str]]


def _strip_optional(annotation: object) -> Any:
    """Return the non-None arm of ``T | None`` (or annotation unchanged)."""
    if get_origin(annotation) is None:
        return annotation
    args = [a for a in get_args(annotation) if a is not type(None)]
    return args[0] if len(args) == 1 else annotation


class TestAddCommonArgs:
    def test_required_flags(self):
        parser = argparse.ArgumentParser()
        add_common_args(parser)
        with pytest.raises(SystemExit):
            parser.parse_args([])
