"""Unit + integration tests for V.root — cross-field validation via root_validators=."""

from dataclasses import dataclass
from pathlib import Path
from typing import Annotated

import pytest

from dature import JsonSource, V, load
from dature.errors import DatureConfigError, FieldLoadError
from dature.validators.predicate import Predicate
from dature.validators.root import RootPredicate


@dataclass
class _PrivConfig:
    port: int
    user: str


def _privileged_port_requires_root(cfg: _PrivConfig) -> bool:
    if cfg.port < 1024:
        return cfg.user == "root"
    return True


class TestRootPredicateConstruction:
    def test_v_root_returns_root_predicate(self) -> None:
        def check(_cfg: object) -> bool:
            return True

        pred = V.root(check)
        assert isinstance(pred, RootPredicate)
        assert pred.func is check

    def test_default_message(self) -> None:
        pred = V.root(lambda _: True)
        assert pred.get_error_message() == "Root validation failed"

    def test_custom_message(self) -> None:
        pred = V.root(lambda _: True, error_message="privileged port requires root user")
        assert pred.get_error_message() == "privileged port requires root user"

    def test_not_a_predicate(self) -> None:
        # RootPredicate intentionally does NOT subclass Predicate — cannot be placed
        # in Annotated[...] metadata (enforced at extraction time).
        pred = V.root(lambda _: True)
        assert not isinstance(pred, Predicate)


class TestVRootHappyPath:
    def test_passes_with_valid_values(self, tmp_path: Path):
        json_file = tmp_path / "config.json"
        json_file.write_text('{"port": 8080, "user": "alice"}')

        result = load(
            JsonSource(file=json_file),
            schema=_PrivConfig,
            root_validators=(V.root(_privileged_port_requires_root),),
        )

        assert result.port == 8080
        assert result.user == "alice"

    def test_passes_with_privileged_root_user(self, tmp_path: Path):
        json_file = tmp_path / "config.json"
        json_file.write_text('{"port": 80, "user": "root"}')

        result = load(
            JsonSource(file=json_file),
            schema=_PrivConfig,
            root_validators=(V.root(_privileged_port_requires_root),),
        )

        assert result.port == 80
        assert result.user == "root"


class TestVRootFailure:
    def test_default_error_message(self, tmp_path: Path):
        json_file = tmp_path / "config.json"
        json_file.write_text('{"port": 80, "user": "alice"}')

        with pytest.raises(DatureConfigError) as exc_info:
            load(
                JsonSource(file=json_file),
                schema=_PrivConfig,
                root_validators=(V.root(_privileged_port_requires_root),),
            )

        err = exc_info.value
        assert len(err.exceptions) == 1

        exc = err.exceptions[0]
        assert isinstance(exc, FieldLoadError)
        assert exc.field_path == []
        assert exc.message == "Root validation failed"

    def test_custom_error_message(self, tmp_path: Path):
        json_file = tmp_path / "config.json"
        json_file.write_text('{"port": 80, "user": "alice"}')

        with pytest.raises(DatureConfigError) as exc_info:
            load(
                JsonSource(file=json_file),
                schema=_PrivConfig,
                root_validators=(
                    V.root(
                        _privileged_port_requires_root,
                        error_message="privileged ports require the root user",
                    ),
                ),
            )

        err = exc_info.value
        exc = err.exceptions[0]
        assert isinstance(exc, FieldLoadError)
        assert exc.message == "privileged ports require the root user"


class TestMultipleRootValidators:
    def test_both_validators_run(self, tmp_path: Path):
        def never_passes(_: _PrivConfig) -> bool:
            return False

        def always_passes(_: _PrivConfig) -> bool:
            return True

        json_file = tmp_path / "config.json"
        json_file.write_text('{"port": 8080, "user": "alice"}')

        with pytest.raises(DatureConfigError) as exc_info:
            load(
                JsonSource(file=json_file),
                schema=_PrivConfig,
                root_validators=(
                    V.root(never_passes, error_message="first check failed"),
                    V.root(always_passes),
                ),
            )

        err = exc_info.value
        field_errors = [exc for exc in err.exceptions if isinstance(exc, FieldLoadError)]
        assert [exc.field_path for exc in field_errors] == [[]]
        assert [exc.message for exc in field_errors] == ["first check failed"]


class TestRootValidatorsContainerShape:
    """root_validators accepts any iterable of RootPredicate; rejects scalars and string-likes."""

    @pytest.fixture
    def json_file(self, tmp_path: Path) -> Path:
        f = tmp_path / "config.json"
        f.write_text('{"port": 8080, "user": "alice"}')
        return f

    def test_accepts_list(self, json_file: Path):
        result = load(
            JsonSource(file=json_file),
            schema=_PrivConfig,
            root_validators=[V.root(_privileged_port_requires_root)],
        )
        assert result.port == 8080

    def test_accepts_tuple(self, json_file: Path):
        result = load(
            JsonSource(file=json_file),
            schema=_PrivConfig,
            root_validators=(V.root(_privileged_port_requires_root),),
        )
        assert result.port == 8080

    def test_rejects_bare_root_predicate_missing_comma(self, json_file: Path):
        with pytest.raises(TypeError, match=r"must be iterable"):
            load(
                JsonSource(file=json_file),
                schema=_PrivConfig,
                root_validators=V.root(_privileged_port_requires_root),
            )

    def test_rejects_dict(self, json_file: Path):
        with pytest.raises(TypeError, match=r"must be a sequence"):
            load(
                JsonSource(file=json_file),
                schema=_PrivConfig,
                root_validators={"a": V.root(_privileged_port_requires_root)},  # type: ignore[dict-item]
            )

    def test_rejects_string(self, json_file: Path):
        with pytest.raises(TypeError, match=r"must be a sequence"):
            load(
                JsonSource(file=json_file),
                schema=_PrivConfig,
                root_validators="not a container",
            )


class TestRootValidatorsElementTypeChecks:
    @pytest.fixture
    def json_file(self, tmp_path: Path) -> Path:
        f = tmp_path / "config.json"
        f.write_text('{"port": 8080, "user": "alice"}')
        return f

    def test_rejects_field_level_predicate(self, json_file: Path):
        with pytest.raises(TypeError, match=r"field-level predicate"):
            load(
                JsonSource(file=json_file),
                schema=_PrivConfig,
                root_validators=(V >= 1,),
            )

    def test_rejects_unrelated_object(self, json_file: Path):
        with pytest.raises(TypeError, match=r"must contain V\.root"):
            load(
                JsonSource(file=json_file),
                schema=_PrivConfig,
                root_validators=("not a root predicate",),
            )


class TestRootPredicateRejectedInAnnotated:
    def test_root_in_annotated_raises(self, tmp_path: Path):
        # RootPredicate placed in Annotated[...] is a schema error, not a data error.
        @dataclass
        class Bad:
            port: Annotated[int, V.root(lambda _: True)]

        json_file = tmp_path / "config.json"

        with pytest.raises(TypeError, match=r"root_validators="):
            load(JsonSource(file=json_file), schema=Bad)

    def test_root_in_source_validators_raises(self, tmp_path: Path):
        @dataclass
        class Cfg:
            port: int

        from dature.field_path import F  # noqa: PLC0415

        json_file = tmp_path / "config.json"
        json_file.write_text('{"port": 8080}')

        with pytest.raises(TypeError, match=r"root_validators="):
            load(
                JsonSource(
                    file=json_file,
                    validators={F[Cfg].port: V.root(lambda _: True)},  # type: ignore[dict-item]
                ),
                schema=Cfg,
            )


class TestSchemaLevelRootValidatorSemantics:
    def test_root_validator_fires_on_final_merged_state(self, tmp_path: Path):
        base_file = tmp_path / "base.json"
        base_file.write_text('{"min_conns": 1, "max_conns": 10}')
        env_file = tmp_path / "env.json"
        env_file.write_text('{"max_conns": 0}')

        @dataclass
        class Pool:
            min_conns: int
            max_conns: int

        with pytest.raises(DatureConfigError) as exc_info:
            load(
                JsonSource(file=base_file),
                JsonSource(file=env_file),
                schema=Pool,
                root_validators=(V.root(lambda c: c.min_conns <= c.max_conns, error_message="min<=max"),),
            )

        err = exc_info.value
        assert len(err.exceptions) == 1
        exc = err.exceptions[0]
        assert isinstance(exc, FieldLoadError)
        assert exc.message == "min<=max"

    def test_root_validator_passes_when_final_state_valid(self, tmp_path: Path):
        base_file = tmp_path / "base.json"
        base_file.write_text('{"min_conns": 1, "max_conns": 10}')
        env_file = tmp_path / "env.json"
        env_file.write_text('{"max_conns": 5}')

        @dataclass
        class Pool:
            min_conns: int
            max_conns: int

        result = load(
            JsonSource(file=base_file),
            JsonSource(file=env_file),
            schema=Pool,
            root_validators=(V.root(lambda c: c.min_conns <= c.max_conns, error_message="min<=max"),),
        )

        assert result == Pool(min_conns=1, max_conns=5)

    def test_root_validator_fires_on_single_source(self, tmp_path: Path):
        json_file = tmp_path / "config.json"
        json_file.write_text('{"x": 5, "y": 2}')

        @dataclass
        class Cfg:
            x: int
            y: int

        with pytest.raises(DatureConfigError) as exc_info:
            load(
                JsonSource(file=json_file),
                schema=Cfg,
                root_validators=(V.root(lambda c: c.x < c.y, error_message="x<y"),),
            )

        exc = exc_info.value.exceptions[0]
        assert isinstance(exc, FieldLoadError)
        assert exc.message == "x<y"

    def test_multiple_sources_all_root_validators_run(self, tmp_path: Path):
        a_file = tmp_path / "a.json"
        a_file.write_text('{"x": 1, "y": 2, "z": 3}')
        b_file = tmp_path / "b.json"
        b_file.write_text('{"z": 0}')

        @dataclass
        class Cfg:
            x: int
            y: int
            z: int

        with pytest.raises(DatureConfigError) as exc_info:
            load(
                JsonSource(file=a_file),
                JsonSource(file=b_file),
                schema=Cfg,
                root_validators=(
                    V.root(lambda c: c.x < c.y, error_message="x<y"),
                    V.root(lambda c: c.z > 0, error_message="z>0"),
                ),
            )

        messages = [e.message for e in exc_info.value.exceptions if isinstance(e, FieldLoadError)]
        assert messages == ["z>0"]
