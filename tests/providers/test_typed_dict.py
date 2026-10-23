"""Tests for TypedDict support (PEP 728 ``closed`` / ``extra_items``)."""

import json
import typing
from dataclasses import dataclass
from pathlib import Path
from typing import cast

import pytest
import typing_extensions

import dature
from dature import load
from dature.errors import DatureConfigError
from dature.errors.exceptions import FieldLoadError
from dature.providers.typed_dict import is_typed_dict

# -- schemas ---------------------------------------------------------------------------------


class Plain(typing_extensions.TypedDict):
    user: str
    password: str


class StdlibPlain(typing.TypedDict):
    user: str
    password: str


class ExtraStr(typing_extensions.TypedDict, extra_items=str):
    user: str


class ExtraInt(typing_extensions.TypedDict, extra_items=int):
    user: str


class ExtraObject(typing_extensions.TypedDict, extra_items=object):
    user: str


class Open(typing_extensions.TypedDict, closed=False):
    user: str


class Closed(typing_extensions.TypedDict, closed=True):
    user: str


class Credentials(typing_extensions.TypedDict, extra_items=str):
    user: str
    password: str


@dataclass
class PlainConfig:
    creds: Plain


@dataclass
class StdlibPlainConfig:
    creds: StdlibPlain


@dataclass
class ExtraStrConfig:
    creds: ExtraStr


@dataclass
class ExtraIntConfig:
    creds: ExtraInt


@dataclass
class ExtraObjectConfig:
    creds: ExtraObject


@dataclass
class OpenConfig:
    creds: Open


@dataclass
class ClosedConfig:
    creds: Closed


@dataclass
class NestedConfig:
    name: str
    credentials: Credentials


def _load(tmp_path: Path, config_class: type, creds: dict[str, object]) -> object:
    path = tmp_path / "config.json"
    path.write_text(json.dumps({"creds": creds}))
    return load(dature.JsonSource(file=path), schema=config_class)


# -- tests -----------------------------------------------------------------------------------


@pytest.mark.parametrize("config_class", [PlainConfig, StdlibPlainConfig], ids=["typing_extensions", "stdlib"])
class TestWithoutExtras:
    def test_extra_keys_are_dropped(self, config_class: type, tmp_path: Path):
        result = _load(tmp_path, config_class, {"user": "admin", "password": "secret", "host": "localhost"})

        assert result == config_class(creds={"user": "admin", "password": "secret"})

    def test_missing_required_key_fails(self, config_class: type, tmp_path: Path):
        with pytest.raises(DatureConfigError):
            _load(tmp_path, config_class, {})


@pytest.mark.parametrize(
    ("config_class", "creds", "expected"),
    [
        (
            ExtraStrConfig,
            {"user": "admin", "host": "localhost", "region": "eu"},
            {"user": "admin", "host": "localhost", "region": "eu"},
        ),
        (ExtraIntConfig, {"user": "admin", "port": "8080"}, {"user": "admin", "port": 8080}),
        (ExtraObjectConfig, {"user": "admin", "flag": 1}, {"user": "admin", "flag": 1}),
    ],
    ids=["str", "int-coerced", "object"],
)
class TestExtraItems:
    def test_extras_are_kept(
        self, config_class: type, creds: dict[str, object], expected: dict[str, object], tmp_path: Path
    ):
        result = _load(tmp_path, config_class, creds)

        assert result == config_class(creds=expected)

    def test_missing_required_key_still_fails(
        self,
        config_class: type,
        creds: dict[str, object],
        expected: dict[str, object],  # noqa: ARG002
        tmp_path: Path,
    ):
        without_user = {key: value for key, value in creds.items() if key != "user"}

        with pytest.raises(DatureConfigError):
            _load(tmp_path, config_class, without_user)


class TestOpen:
    def test_closed_false_keeps_extras_uncoerced(self, tmp_path: Path):
        result = _load(tmp_path, OpenConfig, {"user": "admin", "port": "8080"})

        assert result == OpenConfig(creds={"user": "admin", "port": "8080"})  # type: ignore[typeddict-unknown-key]


class TestClosed:
    def test_extra_key_raises_with_field_path(self, tmp_path: Path):
        with pytest.raises(DatureConfigError) as exc_info:
            _load(tmp_path, ClosedConfig, {"user": "admin", "host": "localhost"})

        errors = [cast("FieldLoadError", error) for error in exc_info.value.exceptions]
        assert len(errors) == 1
        assert errors[0].field_path == ["creds"]
        assert str(errors[0]).splitlines()[0] == "  [creds]  Unknown field(s): host"

    def test_known_keys_only_passes(self, tmp_path: Path):
        result = _load(tmp_path, ClosedConfig, {"user": "admin"})

        assert result == ClosedConfig(creds={"user": "admin"})


class TestNested:
    def test_extra_items_inside_nested_typeddict(self, tmp_path: Path):
        path = tmp_path / "config.json"
        path.write_text(
            json.dumps(
                {
                    "name": "app",
                    "credentials": {"user": "admin", "password": "secret", "host": "localhost", "region": "eu"},
                },
            ),
        )

        result = load(dature.JsonSource(file=path), schema=NestedConfig)

        assert result.credentials == {
            "user": "admin",
            "password": "secret",
            "host": "localhost",
            "region": "eu",
        }


class _LooksLikeTypedDict:
    __required_keys__ = frozenset({"user"})
    __optional_keys__ = frozenset[str]()
    __closed__ = True


@pytest.mark.parametrize(
    ("tp", "expected"),
    [
        (Plain, True),
        (StdlibPlain, True),
        (dict, False),
        (_LooksLikeTypedDict, False),
        ("Plain", False),
        (None, False),
    ],
    ids=["typing_extensions", "stdlib", "dict", "duck-typed-class", "string", "none"],
)
def test_is_typed_dict(tp: object, expected: bool):
    assert is_typed_dict(tp) is expected


class TestWithoutTypingExtensions:
    """``typing_extensions`` is not a dependency: loading must not need it imported.

    ``Plain`` was created through ``typing_extensions`` and therefore carries its
    ``NoExtraItems`` sentinel in ``__extra_items__``. Making the module unimportable must not
    change how such a class loads.
    """

    def test_plain_typeddict_loads(self, block_import, tmp_path: Path):
        path = tmp_path / "config.json"
        path.write_text(json.dumps({"creds": {"user": "admin", "password": "secret", "host": "localhost"}}))

        with block_import("typing_extensions", clean_dature=False):
            result = load(dature.JsonSource(file=path), schema=PlainConfig)

        assert result == PlainConfig(creds={"user": "admin", "password": "secret"})
