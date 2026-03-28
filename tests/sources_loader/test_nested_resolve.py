"""Tests for nested_resolve / nested_resolve_strategy (shared across env, envfile, docker_secrets)."""

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

import pytest

from dature import F, Source, load
from dature.errors.exceptions import DatureConfigError, FieldLoadError
from dature.sources_loader.docker_secrets import DockerSecretsLoader
from dature.sources_loader.env_ import EnvFileLoader, EnvLoader


@dataclass
class NestedVar:
    foo: str
    bar: str


@dataclass
class NestedConfig:
    var: NestedVar


@dataclass
class NestedIntVar:
    foo: int
    bar: int


@dataclass
class NestedIntConfig:
    var: NestedIntVar


@dataclass
class TwoNestedConfig:
    var1: NestedVar
    var2: NestedVar


@dataclass
class DeepSub:
    key: str


@dataclass
class DeepVar:
    sub: DeepSub


@dataclass
class DeepConfig:
    var: DeepVar


@dataclass
class FlatLoaderSetup:
    set_data: Callable[[dict[str, str]], None]
    make_metadata: Callable[..., Source]


@pytest.fixture(params=["env", "envfile", "docker_secrets"])
def flat_loader_setup(
    request: pytest.FixtureRequest,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> FlatLoaderSetup:
    loader_type = request.param

    def set_data(data: dict[str, str]) -> None:
        if loader_type == "env":
            for key, value in data.items():
                monkeypatch.setenv(f"MYAPP__{key.upper()}", value)
        elif loader_type == "envfile":
            content = "\n".join(f"MYAPP__{k.upper()}={v}" for k, v in data.items())
            (tmp_path / ".env").write_text(content)
        elif loader_type == "docker_secrets":
            for key, value in data.items():
                (tmp_path / key).write_text(value)

    def make_metadata(**kwargs: Any) -> Source:
        if loader_type == "env":
            return Source(loader=EnvLoader, prefix="MYAPP__", **kwargs)
        if loader_type == "envfile":
            return Source(file=tmp_path / ".env", loader=EnvFileLoader, prefix="MYAPP__", **kwargs)
        return Source(file=tmp_path, loader=DockerSecretsLoader, **kwargs)

    return FlatLoaderSetup(set_data=set_data, make_metadata=make_metadata)


def _strategy_kwargs(strategy: str, *, local: bool) -> dict[str, Any]:
    if local:
        return {"nested_resolve": {strategy: (F[NestedConfig],)}}
    return {"nested_resolve_strategy": strategy}


class TestNestedResolve:
    """Tests for nested variable conflict resolution across all flat-key loaders."""

    def test_json_only(self, flat_loader_setup: FlatLoaderSetup) -> None:
        flat_loader_setup.set_data({"var": '{"foo": "from_json", "bar": "from_json"}'})

        result = load(flat_loader_setup.make_metadata(), NestedConfig)

        assert result == NestedConfig(var=NestedVar(foo="from_json", bar="from_json"))

    def test_flat_only(self, flat_loader_setup: FlatLoaderSetup) -> None:
        flat_loader_setup.set_data({"var__foo": "from_flat", "var__bar": "from_flat"})

        result = load(flat_loader_setup.make_metadata(), NestedConfig)

        assert result == NestedConfig(var=NestedVar(foo="from_flat", bar="from_flat"))

    @pytest.mark.parametrize(
        ("strategy", "local", "expected_source"),
        [
            ("flat", False, "from_flat"),
            ("flat", True, "from_flat"),
            ("json", False, "from_json"),
            ("json", True, "from_json"),
        ],
        ids=["flat-global", "flat-local", "json-global", "json-local"],
    )
    def test_both_sources(
        self,
        flat_loader_setup: FlatLoaderSetup,
        strategy: str,
        local: bool,
        expected_source: str,
    ) -> None:
        flat_loader_setup.set_data(
            {
                "var": '{"foo": "from_json", "bar": "from_json"}',
                "var__foo": "from_flat",
                "var__bar": "from_flat",
            },
        )

        result = load(
            flat_loader_setup.make_metadata(**_strategy_kwargs(strategy, local=local)),
            NestedConfig,
        )

        assert result == NestedConfig(var=NestedVar(foo=expected_source, bar=expected_source))


class TestPartialNestedResolveEnv:
    """Partial records via env: JSON has foo, flat has bar — error depends on strategy."""

    @pytest.mark.parametrize(
        ("strategy", "local", "expected_field_err"),
        [
            ("flat", False, "  [var.foo]  Missing required field\n   └── ENV 'MYAPP__VAR__FOO'"),
            ("flat", True, "  [var.foo]  Missing required field\n   └── ENV 'MYAPP__VAR__FOO'"),
            (
                "json",
                False,
                "  [var.bar]  Missing required field\n   └── ENV 'MYAPP__VAR' = '{\"foo\": \"from_json\"}'",
            ),
            (
                "json",
                True,
                "  [var.bar]  Missing required field\n   └── ENV 'MYAPP__VAR' = '{\"foo\": \"from_json\"}'",
            ),
        ],
        ids=["flat-global", "flat-local", "json-global", "json-local"],
    )
    def test_partial_missing_field(
        self,
        monkeypatch: pytest.MonkeyPatch,
        strategy: str,
        local: bool,
        expected_field_err: str,
    ) -> None:
        monkeypatch.setenv("MYAPP__VAR", '{"foo": "from_json"}')
        monkeypatch.setenv("MYAPP__VAR__BAR", "from_flat")

        with pytest.raises(DatureConfigError) as exc_info:
            load(
                Source(loader=EnvLoader, prefix="MYAPP__", **_strategy_kwargs(strategy, local=local)),
                NestedConfig,
            )

        err = exc_info.value
        assert str(err) == "NestedConfig loading errors (1)"
        assert len(err.exceptions) == 1
        field_err = err.exceptions[0]
        assert isinstance(field_err, FieldLoadError)
        assert str(field_err) == expected_field_err


class TestPartialNestedResolveEnvFile:
    """Partial records via envfile: JSON has foo, flat has bar — error depends on strategy."""

    @pytest.mark.parametrize("local", [False, True], ids=["global", "local"])
    def test_partial_missing_field_flat(self, tmp_path: Path, local: bool) -> None:
        env_file = tmp_path / ".env"
        env_file.write_text('MYAPP__VAR={"foo": "from_json"}\nMYAPP__VAR__BAR=from_flat')

        with pytest.raises(DatureConfigError) as exc_info:
            load(
                Source(
                    file=env_file,
                    loader=EnvFileLoader,
                    prefix="MYAPP__",
                    **_strategy_kwargs("flat", local=local),
                ),
                NestedConfig,
            )

        err = exc_info.value
        assert str(err) == "NestedConfig loading errors (1)"
        assert len(err.exceptions) == 1
        field_err = err.exceptions[0]
        assert isinstance(field_err, FieldLoadError)
        assert str(field_err) == f"  [var.foo]  Missing required field\n   └── ENV FILE '{env_file}'"

    @pytest.mark.parametrize("local", [False, True], ids=["global", "local"])
    def test_partial_missing_field_json(self, tmp_path: Path, local: bool) -> None:
        env_file = tmp_path / ".env"
        env_file.write_text('MYAPP__VAR={"foo": "from_json"}\nMYAPP__VAR__BAR=from_flat')

        with pytest.raises(DatureConfigError) as exc_info:
            load(
                Source(
                    file=env_file,
                    loader=EnvFileLoader,
                    prefix="MYAPP__",
                    **_strategy_kwargs("json", local=local),
                ),
                NestedConfig,
            )

        err = exc_info.value
        assert str(err) == "NestedConfig loading errors (1)"
        assert len(err.exceptions) == 1
        field_err = err.exceptions[0]
        assert isinstance(field_err, FieldLoadError)
        assert str(field_err) == (
            "  [var.bar]  Missing required field\n"
            '   ├── MYAPP__VAR={"foo": "from_json"}\n'
            f"   └── ENV FILE '{env_file}', line 1"
        )


class TestPartialNestedResolveDockerSecrets:
    """Partial records via docker_secrets: JSON has foo, flat has bar — error depends on strategy."""

    @pytest.mark.parametrize("local", [False, True], ids=["global", "local"])
    def test_partial_missing_field_flat(self, tmp_path: Path, local: bool) -> None:
        (tmp_path / "var").write_text('{"foo": "from_json"}')
        (tmp_path / "var__bar").write_text("from_flat")

        with pytest.raises(DatureConfigError) as exc_info:
            load(
                Source(file=tmp_path, loader=DockerSecretsLoader, **_strategy_kwargs("flat", local=local)),
                NestedConfig,
            )

        err = exc_info.value
        assert str(err) == "NestedConfig loading errors (1)"
        assert len(err.exceptions) == 1
        field_err = err.exceptions[0]
        assert isinstance(field_err, FieldLoadError)
        assert str(field_err) == f"  [var.foo]  Missing required field\n   └── SECRET FILE '{tmp_path / 'var__foo'}'"

    @pytest.mark.parametrize("local", [False, True], ids=["global", "local"])
    def test_partial_missing_field_json(self, tmp_path: Path, local: bool) -> None:
        (tmp_path / "var").write_text('{"foo": "from_json"}')
        (tmp_path / "var__bar").write_text("from_flat")

        with pytest.raises(DatureConfigError) as exc_info:
            load(
                Source(file=tmp_path, loader=DockerSecretsLoader, **_strategy_kwargs("json", local=local)),
                NestedConfig,
            )

        err = exc_info.value
        assert str(err) == "NestedConfig loading errors (1)"
        assert len(err.exceptions) == 1
        field_err = err.exceptions[0]
        assert isinstance(field_err, FieldLoadError)
        assert str(field_err) == f"  [var.bar]  Missing required field\n   └── SECRET FILE '{tmp_path / 'var'}'"


class TestInvalidDataNestedResolveEnv:
    """Invalid data in one source, valid in the other — strategy picks the source, error reflects it."""

    def test_json_invalid_flat_strategy_succeeds(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("MYAPP__VAR", '{"foo": "not_a_number", "bar": "not_a_number"}')
        monkeypatch.setenv("MYAPP__VAR__FOO", "10")
        monkeypatch.setenv("MYAPP__VAR__BAR", "20")

        result = load(
            Source(loader=EnvLoader, prefix="MYAPP__", nested_resolve_strategy="flat"),
            NestedIntConfig,
        )

        assert result == NestedIntConfig(var=NestedIntVar(foo=10, bar=20))

    def test_json_invalid_json_strategy_errors(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("MYAPP__VAR", '{"foo": "not_a_number", "bar": "not_a_number"}')
        monkeypatch.setenv("MYAPP__VAR__FOO", "10")
        monkeypatch.setenv("MYAPP__VAR__BAR", "20")

        with pytest.raises(DatureConfigError) as exc_info:
            load(
                Source(loader=EnvLoader, prefix="MYAPP__", nested_resolve_strategy="json"),
                NestedIntConfig,
            )

        err = exc_info.value
        assert str(err) == "NestedIntConfig loading errors (2)"
        assert len(err.exceptions) == 2
        first = err.exceptions[0]
        assert isinstance(first, FieldLoadError)
        assert str(first) == (
            "  [var.foo]  invalid literal for int() with base 10: 'not_a_number'\n"
            '   └── ENV \'MYAPP__VAR\' = \'{"foo": "not_a_number", "bar": "not_a_number"}\''
        )
        second = err.exceptions[1]
        assert isinstance(second, FieldLoadError)
        assert str(second) == (
            "  [var.bar]  invalid literal for int() with base 10: 'not_a_number'\n"
            '   └── ENV \'MYAPP__VAR\' = \'{"foo": "not_a_number", "bar": "not_a_number"}\''
        )

    def test_flat_invalid_json_strategy_succeeds(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("MYAPP__VAR", '{"foo": 10, "bar": 20}')
        monkeypatch.setenv("MYAPP__VAR__FOO", "not_a_number")
        monkeypatch.setenv("MYAPP__VAR__BAR", "not_a_number")

        result = load(
            Source(loader=EnvLoader, prefix="MYAPP__", nested_resolve_strategy="json"),
            NestedIntConfig,
        )

        assert result == NestedIntConfig(var=NestedIntVar(foo=10, bar=20))

    def test_flat_invalid_flat_strategy_errors(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("MYAPP__VAR", '{"foo": 10, "bar": 20}')
        monkeypatch.setenv("MYAPP__VAR__FOO", "not_a_number")
        monkeypatch.setenv("MYAPP__VAR__BAR", "not_a_number")

        with pytest.raises(DatureConfigError) as exc_info:
            load(
                Source(loader=EnvLoader, prefix="MYAPP__", nested_resolve_strategy="flat"),
                NestedIntConfig,
            )

        err = exc_info.value
        assert str(err) == "NestedIntConfig loading errors (2)"
        assert len(err.exceptions) == 2
        first = err.exceptions[0]
        assert isinstance(first, FieldLoadError)
        assert str(first) == (
            "  [var.foo]  invalid literal for int() with base 10: 'not_a_number'\n   └── ENV 'MYAPP__VAR__FOO'"
        )
        second = err.exceptions[1]
        assert isinstance(second, FieldLoadError)
        assert str(second) == (
            "  [var.bar]  invalid literal for int() with base 10: 'not_a_number'\n   └── ENV 'MYAPP__VAR__BAR'"
        )


class TestInvalidDataNestedResolveEnvFile:
    """Invalid data in one source, valid in the other — envfile error messages."""

    def test_json_invalid_flat_strategy_succeeds(self, tmp_path: Path) -> None:
        env_file = tmp_path / ".env"
        env_file.write_text(
            'MYAPP__VAR={"foo": "not_a_number", "bar": "not_a_number"}\nMYAPP__VAR__FOO=10\nMYAPP__VAR__BAR=20',
        )

        result = load(
            Source(file=env_file, loader=EnvFileLoader, prefix="MYAPP__", nested_resolve_strategy="flat"),
            NestedIntConfig,
        )

        assert result == NestedIntConfig(var=NestedIntVar(foo=10, bar=20))

    def test_json_invalid_json_strategy_errors(self, tmp_path: Path) -> None:
        env_file = tmp_path / ".env"
        env_file.write_text(
            'MYAPP__VAR={"foo": "not_a_number", "bar": "not_a_number"}\nMYAPP__VAR__FOO=10\nMYAPP__VAR__BAR=20',
        )

        with pytest.raises(DatureConfigError) as exc_info:
            load(
                Source(file=env_file, loader=EnvFileLoader, prefix="MYAPP__", nested_resolve_strategy="json"),
                NestedIntConfig,
            )

        err = exc_info.value
        assert str(err) == "NestedIntConfig loading errors (2)"
        assert len(err.exceptions) == 2
        first = err.exceptions[0]
        assert isinstance(first, FieldLoadError)
        assert str(first) == (
            "  [var.foo]  invalid literal for int() with base 10: 'not_a_number'\n"
            '   ├── MYAPP__VAR={"foo": "not_a_number", "bar": "not_a_number"}\n'
            f"   │   {' ' * 43}^^^^^^^^^^^^\n"
            f"   └── ENV FILE '{env_file}', line 1"
        )
        second = err.exceptions[1]
        assert isinstance(second, FieldLoadError)
        assert str(second) == (
            "  [var.bar]  invalid literal for int() with base 10: 'not_a_number'\n"
            '   ├── MYAPP__VAR={"foo": "not_a_number", "bar": "not_a_number"}\n'
            f"   │   {' ' * 43}^^^^^^^^^^^^\n"
            f"   └── ENV FILE '{env_file}', line 1"
        )

    def test_flat_invalid_json_strategy_succeeds(self, tmp_path: Path) -> None:
        env_file = tmp_path / ".env"
        env_file.write_text(
            'MYAPP__VAR={"foo": 10, "bar": 20}\nMYAPP__VAR__FOO=not_a_number\nMYAPP__VAR__BAR=not_a_number',
        )

        result = load(
            Source(file=env_file, loader=EnvFileLoader, prefix="MYAPP__", nested_resolve_strategy="json"),
            NestedIntConfig,
        )

        assert result == NestedIntConfig(var=NestedIntVar(foo=10, bar=20))

    def test_flat_invalid_flat_strategy_errors(self, tmp_path: Path) -> None:
        env_file = tmp_path / ".env"
        env_file.write_text(
            'MYAPP__VAR={"foo": 10, "bar": 20}\nMYAPP__VAR__FOO=not_a_number\nMYAPP__VAR__BAR=not_a_number',
        )

        with pytest.raises(DatureConfigError) as exc_info:
            load(
                Source(file=env_file, loader=EnvFileLoader, prefix="MYAPP__", nested_resolve_strategy="flat"),
                NestedIntConfig,
            )

        err = exc_info.value
        assert str(err) == "NestedIntConfig loading errors (2)"
        assert len(err.exceptions) == 2
        first = err.exceptions[0]
        assert isinstance(first, FieldLoadError)
        assert str(first) == (
            "  [var.foo]  invalid literal for int() with base 10: 'not_a_number'\n"
            "   ├── MYAPP__VAR__FOO=not_a_number\n"
            "   │                   ^^^^^^^^^^^^\n"
            f"   └── ENV FILE '{env_file}', line 2"
        )
        second = err.exceptions[1]
        assert isinstance(second, FieldLoadError)
        assert str(second) == (
            "  [var.bar]  invalid literal for int() with base 10: 'not_a_number'\n"
            "   ├── MYAPP__VAR__BAR=not_a_number\n"
            "   │                   ^^^^^^^^^^^^\n"
            f"   └── ENV FILE '{env_file}', line 3"
        )


class TestInvalidDataNestedResolveDockerSecrets:
    """Invalid data in one source, valid in the other — docker_secrets error messages."""

    def test_json_invalid_flat_strategy_succeeds(self, tmp_path: Path) -> None:
        (tmp_path / "var").write_text('{"foo": "not_a_number", "bar": "not_a_number"}')
        (tmp_path / "var__foo").write_text("10")
        (tmp_path / "var__bar").write_text("20")

        result = load(
            Source(file=tmp_path, loader=DockerSecretsLoader, nested_resolve_strategy="flat"),
            NestedIntConfig,
        )

        assert result == NestedIntConfig(var=NestedIntVar(foo=10, bar=20))

    def test_json_invalid_json_strategy_errors(self, tmp_path: Path) -> None:
        (tmp_path / "var").write_text('{"foo": "not_a_number", "bar": "not_a_number"}')
        (tmp_path / "var__foo").write_text("10")
        (tmp_path / "var__bar").write_text("20")

        with pytest.raises(DatureConfigError) as exc_info:
            load(
                Source(file=tmp_path, loader=DockerSecretsLoader, nested_resolve_strategy="json"),
                NestedIntConfig,
            )

        err = exc_info.value
        assert str(err) == "NestedIntConfig loading errors (2)"
        assert len(err.exceptions) == 2
        first = err.exceptions[0]
        assert isinstance(first, FieldLoadError)
        assert str(first) == (
            "  [var.foo]  invalid literal for int() with base 10: 'not_a_number'\n"
            f"   └── SECRET FILE '{tmp_path / 'var'}'"
        )
        second = err.exceptions[1]
        assert isinstance(second, FieldLoadError)
        assert str(second) == (
            "  [var.bar]  invalid literal for int() with base 10: 'not_a_number'\n"
            f"   └── SECRET FILE '{tmp_path / 'var'}'"
        )

    def test_flat_invalid_json_strategy_succeeds(self, tmp_path: Path) -> None:
        (tmp_path / "var").write_text('{"foo": 10, "bar": 20}')
        (tmp_path / "var__foo").write_text("not_a_number")
        (tmp_path / "var__bar").write_text("not_a_number")

        result = load(
            Source(file=tmp_path, loader=DockerSecretsLoader, nested_resolve_strategy="json"),
            NestedIntConfig,
        )

        assert result == NestedIntConfig(var=NestedIntVar(foo=10, bar=20))

    def test_flat_invalid_flat_strategy_errors(self, tmp_path: Path) -> None:
        (tmp_path / "var").write_text('{"foo": 10, "bar": 20}')
        (tmp_path / "var__foo").write_text("not_a_number")
        (tmp_path / "var__bar").write_text("not_a_number")

        with pytest.raises(DatureConfigError) as exc_info:
            load(
                Source(file=tmp_path, loader=DockerSecretsLoader, nested_resolve_strategy="flat"),
                NestedIntConfig,
            )

        err = exc_info.value
        assert str(err) == "NestedIntConfig loading errors (2)"
        assert len(err.exceptions) == 2
        first = err.exceptions[0]
        assert isinstance(first, FieldLoadError)
        assert str(first) == (
            "  [var.foo]  invalid literal for int() with base 10: 'not_a_number'\n"
            f"   └── SECRET FILE '{tmp_path / 'var__foo'}'"
        )
        second = err.exceptions[1]
        assert isinstance(second, FieldLoadError)
        assert str(second) == (
            "  [var.bar]  invalid literal for int() with base 10: 'not_a_number'\n"
            f"   └── SECRET FILE '{tmp_path / 'var__bar'}'"
        )


class TestMultilineJsonNestedResolveEnv:
    """Multiline JSON in env variable — env_var_value preserves newlines."""

    def test_multiline_json_strategy_errors(self, monkeypatch: pytest.MonkeyPatch) -> None:
        multiline_json = '{"foo": "not_a_number",\n"bar": "not_a_number"}'
        monkeypatch.setenv("MYAPP__VAR", multiline_json)
        monkeypatch.setenv("MYAPP__VAR__FOO", "10")
        monkeypatch.setenv("MYAPP__VAR__BAR", "20")

        with pytest.raises(DatureConfigError) as exc_info:
            load(
                Source(loader=EnvLoader, prefix="MYAPP__", nested_resolve_strategy="json"),
                NestedIntConfig,
            )

        err = exc_info.value
        assert str(err) == "NestedIntConfig loading errors (2)"
        assert len(err.exceptions) == 2
        first = err.exceptions[0]
        assert isinstance(first, FieldLoadError)
        assert str(first) == (
            "  [var.foo]  invalid literal for int() with base 10: 'not_a_number'\n"
            '   └── ENV \'MYAPP__VAR\' = \'{"foo": "not_a_number",\n'
            '"bar": "not_a_number"}\''
        )
        second = err.exceptions[1]
        assert isinstance(second, FieldLoadError)
        assert str(second) == (
            "  [var.bar]  invalid literal for int() with base 10: 'not_a_number'\n"
            '   └── ENV \'MYAPP__VAR\' = \'{"foo": "not_a_number",\n'
            '"bar": "not_a_number"}\''
        )

    def test_multiline_flat_strategy_ignores_json(self, monkeypatch: pytest.MonkeyPatch) -> None:
        multiline_json = '{"foo": "not_a_number",\n"bar": "not_a_number"}'
        monkeypatch.setenv("MYAPP__VAR", multiline_json)
        monkeypatch.setenv("MYAPP__VAR__FOO", "10")
        monkeypatch.setenv("MYAPP__VAR__BAR", "20")

        result = load(
            Source(loader=EnvLoader, prefix="MYAPP__", nested_resolve_strategy="flat"),
            NestedIntConfig,
        )

        assert result == NestedIntConfig(var=NestedIntVar(foo=10, bar=20))


class TestPerFieldDifferentStrategies:
    """Two nested fields with different per-field strategies applied simultaneously."""

    @pytest.mark.parametrize(
        ("var1_strategy", "var2_strategy", "expected_var1", "expected_var2"),
        [
            ("json", "flat", NestedVar(foo="json1", bar="json1"), NestedVar(foo="flat2", bar="flat2")),
            ("flat", "json", NestedVar(foo="flat1", bar="flat1"), NestedVar(foo="json2", bar="json2")),
        ],
        ids=["var1-json-var2-flat", "var1-flat-var2-json"],
    )
    def test_different_strategies(
        self,
        monkeypatch: pytest.MonkeyPatch,
        var1_strategy: Literal["flat", "json"],
        var2_strategy: Literal["flat", "json"],
        expected_var1: NestedVar,
        expected_var2: NestedVar,
    ) -> None:
        monkeypatch.setenv("MYAPP__VAR1", '{"foo": "json1", "bar": "json1"}')
        monkeypatch.setenv("MYAPP__VAR1__FOO", "flat1")
        monkeypatch.setenv("MYAPP__VAR1__BAR", "flat1")
        monkeypatch.setenv("MYAPP__VAR2", '{"foo": "json2", "bar": "json2"}')
        monkeypatch.setenv("MYAPP__VAR2__FOO", "flat2")
        monkeypatch.setenv("MYAPP__VAR2__BAR", "flat2")

        result = load(
            Source(
                loader=EnvLoader,
                prefix="MYAPP__",
                nested_resolve={
                    var1_strategy: (F[TwoNestedConfig].var1,),
                    var2_strategy: (F[TwoNestedConfig].var2,),
                },
            ),
            TwoNestedConfig,
        )

        assert result == TwoNestedConfig(var1=expected_var1, var2=expected_var2)


class TestPerFieldOverridesGlobal:
    """Per-field nested_resolve overrides nested_resolve_strategy."""

    @pytest.mark.parametrize(
        ("global_strategy", "local_strategy", "expected_source"),
        [
            ("flat", "json", "from_json"),
            ("json", "flat", "from_flat"),
        ],
        ids=["global-flat-local-json", "global-json-local-flat"],
    )
    def test_local_overrides_global(
        self,
        monkeypatch: pytest.MonkeyPatch,
        global_strategy: Literal["flat", "json"],
        local_strategy: Literal["flat", "json"],
        expected_source: str,
    ) -> None:
        monkeypatch.setenv("MYAPP__VAR", '{"foo": "from_json", "bar": "from_json"}')
        monkeypatch.setenv("MYAPP__VAR__FOO", "from_flat")
        monkeypatch.setenv("MYAPP__VAR__BAR", "from_flat")

        result = load(
            Source(
                loader=EnvLoader,
                prefix="MYAPP__",
                nested_resolve_strategy=global_strategy,
                nested_resolve={local_strategy: (F[NestedConfig].var,)},
            ),
            NestedConfig,
        )

        assert result == NestedConfig(var=NestedVar(foo=expected_source, bar=expected_source))


class TestCustomSplitSymbolsConflict:
    """Custom split_symbols with conflict — error messages show correct variable names."""

    def test_flat_strategy_single_underscore(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("APP_VAR", '{"foo": "from_json", "bar": "from_json"}')
        monkeypatch.setenv("APP_VAR_FOO", "from_flat")
        monkeypatch.setenv("APP_VAR_BAR", "from_flat")

        result = load(
            Source(
                loader=EnvLoader,
                prefix="APP_",
                split_symbols="_",
                nested_resolve_strategy="flat",
            ),
            NestedConfig,
        )

        assert result == NestedConfig(var=NestedVar(foo="from_flat", bar="from_flat"))

    def test_json_strategy_single_underscore_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("APP_VAR", '{"foo": "not_int", "bar": "not_int"}')
        monkeypatch.setenv("APP_VAR_FOO", "10")
        monkeypatch.setenv("APP_VAR_BAR", "20")

        with pytest.raises(DatureConfigError) as exc_info:
            load(
                Source(
                    loader=EnvLoader,
                    prefix="APP_",
                    split_symbols="_",
                    nested_resolve_strategy="json",
                ),
                NestedIntConfig,
            )

        err = exc_info.value
        first = err.exceptions[0]
        assert isinstance(first, FieldLoadError)
        assert str(first) == (
            "  [var.foo]  invalid literal for int() with base 10: 'not_int'\n"
            '   └── ENV \'APP_VAR\' = \'{"foo": "not_int", "bar": "not_int"}\''
        )

    def test_flat_strategy_single_underscore_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("APP_VAR", '{"foo": 10, "bar": 20}')
        monkeypatch.setenv("APP_VAR_FOO", "not_int")
        monkeypatch.setenv("APP_VAR_BAR", "not_int")

        with pytest.raises(DatureConfigError) as exc_info:
            load(
                Source(
                    loader=EnvLoader,
                    prefix="APP_",
                    split_symbols="_",
                    nested_resolve_strategy="flat",
                ),
                NestedIntConfig,
            )

        err = exc_info.value
        first = err.exceptions[0]
        assert isinstance(first, FieldLoadError)
        assert str(first) == (
            "  [var.foo]  invalid literal for int() with base 10: 'not_int'\n   └── ENV 'APP_VAR_FOO'"
        )


class TestNoConflictWithStrategy:
    """Strategy is set but no conflict occurs — only one source present."""

    @pytest.mark.parametrize("strategy", ["flat", "json"])
    def test_only_json_no_conflict(
        self,
        flat_loader_setup: FlatLoaderSetup,
        strategy: str,
    ) -> None:
        flat_loader_setup.set_data({"var": '{"foo": "val1", "bar": "val2"}'})

        result = load(
            flat_loader_setup.make_metadata(nested_resolve_strategy=strategy),
            NestedConfig,
        )

        assert result == NestedConfig(var=NestedVar(foo="val1", bar="val2"))

    @pytest.mark.parametrize("strategy", ["flat", "json"])
    def test_only_flat_no_conflict(
        self,
        flat_loader_setup: FlatLoaderSetup,
        strategy: str,
    ) -> None:
        flat_loader_setup.set_data({"var__foo": "val1", "var__bar": "val2"})

        result = load(
            flat_loader_setup.make_metadata(nested_resolve_strategy=strategy),
            NestedConfig,
        )

        assert result == NestedConfig(var=NestedVar(foo="val1", bar="val2"))


class TestDeepNestedConflict:
    """Three-level nesting (var__sub__key) with conflict on var."""

    @pytest.mark.parametrize(
        ("strategy", "expected_key"),
        [("flat", "from_flat"), ("json", "from_json")],
        ids=["flat", "json"],
    )
    def test_deep_env(self, monkeypatch: pytest.MonkeyPatch, strategy: str, expected_key: str) -> None:
        monkeypatch.setenv("MYAPP__VAR", '{"sub": {"key": "from_json"}}')
        monkeypatch.setenv("MYAPP__VAR__SUB__KEY", "from_flat")

        result = load(
            Source(loader=EnvLoader, prefix="MYAPP__", nested_resolve_strategy=strategy),
            DeepConfig,
        )

        assert result == DeepConfig(var=DeepVar(sub=DeepSub(key=expected_key)))

    def test_flat_strategy_deep_envfile(self, tmp_path: Path) -> None:
        env_file = tmp_path / ".env"
        env_file.write_text(
            'MYAPP__VAR={"sub": {"key": "from_json"}}\nMYAPP__VAR__SUB__KEY=from_flat',
        )

        result = load(
            Source(
                file=env_file,
                loader=EnvFileLoader,
                prefix="MYAPP__",
                nested_resolve_strategy="flat",
            ),
            DeepConfig,
        )

        assert result == DeepConfig(var=DeepVar(sub=DeepSub(key="from_flat")))

    def test_json_strategy_deep_docker_secrets(self, tmp_path: Path) -> None:
        (tmp_path / "var").write_text('{"sub": {"key": "from_json"}}')
        (tmp_path / "var__sub__key").write_text("from_flat")

        result = load(
            Source(file=tmp_path, loader=DockerSecretsLoader, nested_resolve_strategy="json"),
            DeepConfig,
        )

        assert result == DeepConfig(var=DeepVar(sub=DeepSub(key="from_json")))


class TestPrefixDockerSecretsConflict:
    """Docker secrets with prefix — error shows correct secret file path."""

    def test_flat_strategy_error(self, tmp_path: Path) -> None:
        (tmp_path / "myapp__var").write_text('{"foo": "not_int", "bar": "not_int"}')
        (tmp_path / "myapp__var__foo").write_text("not_int")
        (tmp_path / "myapp__var__bar").write_text("not_int")

        with pytest.raises(DatureConfigError) as exc_info:
            load(
                Source(
                    file=tmp_path,
                    loader=DockerSecretsLoader,
                    prefix="myapp__",
                    nested_resolve_strategy="flat",
                ),
                NestedIntConfig,
            )

        err = exc_info.value
        assert len(err.exceptions) == 2
        first = err.exceptions[0]
        assert isinstance(first, FieldLoadError)
        assert str(first) == (
            "  [var.foo]  invalid literal for int() with base 10: 'not_int'\n"
            f"   └── SECRET FILE '{tmp_path / 'myapp__var__foo'}'"
        )

    def test_json_strategy_error(self, tmp_path: Path) -> None:
        (tmp_path / "myapp__var").write_text('{"foo": "not_int", "bar": "not_int"}')
        (tmp_path / "myapp__var__foo").write_text("10")
        (tmp_path / "myapp__var__bar").write_text("20")

        with pytest.raises(DatureConfigError) as exc_info:
            load(
                Source(
                    file=tmp_path,
                    loader=DockerSecretsLoader,
                    prefix="myapp__",
                    nested_resolve_strategy="json",
                ),
                NestedIntConfig,
            )

        err = exc_info.value
        assert len(err.exceptions) == 2
        first = err.exceptions[0]
        assert isinstance(first, FieldLoadError)
        assert str(first) == (
            "  [var.foo]  invalid literal for int() with base 10: 'not_int'\n"
            f"   └── SECRET FILE '{tmp_path / 'myapp__var'}'"
        )


class TestKeyOrderDoesNotAffectConflict:
    """JSON key arrives after flat keys — result is the same as when JSON comes first."""

    def test_flat_first_then_json(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("MYAPP__VAR__FOO", "from_flat")
        monkeypatch.setenv("MYAPP__VAR__BAR", "from_flat")
        monkeypatch.setenv("MYAPP__VAR", '{"foo": "from_json", "bar": "from_json"}')

        result_flat = load(
            Source(loader=EnvLoader, prefix="MYAPP__", nested_resolve_strategy="flat"),
            NestedConfig,
        )
        result_json = load(
            Source(loader=EnvLoader, prefix="MYAPP__", nested_resolve_strategy="json"),
            NestedConfig,
        )

        assert result_flat == NestedConfig(var=NestedVar(foo="from_flat", bar="from_flat"))
        assert result_json == NestedConfig(var=NestedVar(foo="from_json", bar="from_json"))

    def test_envfilereversed_order(self, tmp_path: Path) -> None:
        env_file = tmp_path / ".env"
        env_file.write_text(
            'MYAPP__VAR__FOO=from_flat\nMYAPP__VAR__BAR=from_flat\nMYAPP__VAR={"foo": "from_json", "bar": "from_json"}',
        )

        result_flat = load(
            Source(
                file=env_file,
                loader=EnvFileLoader,
                prefix="MYAPP__",
                nested_resolve_strategy="flat",
            ),
            NestedConfig,
        )
        result_json = load(
            Source(
                file=env_file,
                loader=EnvFileLoader,
                prefix="MYAPP__",
                nested_resolve_strategy="json",
            ),
            NestedConfig,
        )

        assert result_flat == NestedConfig(var=NestedVar(foo="from_flat", bar="from_flat"))
        assert result_json == NestedConfig(var=NestedVar(foo="from_json", bar="from_json"))


class TestEmptyNestedResolveDict:
    """Empty nested_resolve={} — falls back to global strategy."""

    @pytest.mark.parametrize(
        ("strategy", "expected_source"),
        [("flat", "from_flat"), ("json", "from_json")],
        ids=["flat", "json"],
    )
    def test_empty_dict_uses_global(
        self,
        monkeypatch: pytest.MonkeyPatch,
        strategy: str,
        expected_source: str,
    ) -> None:
        monkeypatch.setenv("MYAPP__VAR", '{"foo": "from_json", "bar": "from_json"}')
        monkeypatch.setenv("MYAPP__VAR__FOO", "from_flat")
        monkeypatch.setenv("MYAPP__VAR__BAR", "from_flat")

        result = load(
            Source(
                loader=EnvLoader,
                prefix="MYAPP__",
                nested_resolve_strategy=strategy,
                nested_resolve={},
            ),
            NestedConfig,
        )

        assert result == NestedConfig(var=NestedVar(foo=expected_source, bar=expected_source))
