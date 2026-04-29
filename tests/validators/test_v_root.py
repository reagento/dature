"""Unit + integration tests for V.root — cross-field validation via source.root_validators."""

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
            JsonSource(
                file=json_file,
                root_validators=(V.root(_privileged_port_requires_root),),
            ),
            schema=_PrivConfig,
        )

        assert result.port == 8080
        assert result.user == "alice"

    def test_passes_with_privileged_root_user(self, tmp_path: Path):
        json_file = tmp_path / "config.json"
        json_file.write_text('{"port": 80, "user": "root"}')

        result = load(
            JsonSource(
                file=json_file,
                root_validators=(V.root(_privileged_port_requires_root),),
            ),
            schema=_PrivConfig,
        )

        assert result.port == 80
        assert result.user == "root"


class TestVRootFailure:
    def test_default_error_message(self, tmp_path: Path):
        json_file = tmp_path / "config.json"
        json_file.write_text('{"port": 80, "user": "alice"}')

        with pytest.raises(DatureConfigError) as exc_info:
            load(
                JsonSource(
                    file=json_file,
                    root_validators=(V.root(_privileged_port_requires_root),),
                ),
                schema=_PrivConfig,
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
                JsonSource(
                    file=json_file,
                    root_validators=(
                        V.root(
                            _privileged_port_requires_root,
                            error_message="privileged ports require the root user",
                        ),
                    ),
                ),
                schema=_PrivConfig,
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
                JsonSource(
                    file=json_file,
                    root_validators=(
                        V.root(never_passes, error_message="first check failed"),
                        V.root(always_passes),
                    ),
                ),
                schema=_PrivConfig,
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
            JsonSource(
                file=json_file,
                root_validators=[V.root(_privileged_port_requires_root)],
            ),
            schema=_PrivConfig,
        )
        assert result.port == 8080

    def test_accepts_tuple(self, json_file: Path):
        result = load(
            JsonSource(
                file=json_file,
                root_validators=(V.root(_privileged_port_requires_root),),
            ),
            schema=_PrivConfig,
        )
        assert result.port == 8080

    def test_rejects_bare_root_predicate_missing_comma(self, json_file: Path):
        with pytest.raises(TypeError, match=r"must be iterable"):
            load(
                JsonSource(
                    file=json_file,
                    root_validators=V.root(_privileged_port_requires_root),
                ),
                schema=_PrivConfig,
            )

    def test_rejects_dict(self, json_file: Path):
        with pytest.raises(TypeError, match=r"must be a sequence"):
            load(
                JsonSource(
                    file=json_file,
                    root_validators={"a": V.root(_privileged_port_requires_root)},  # type: ignore[dict-item]
                ),
                schema=_PrivConfig,
            )

    def test_rejects_string(self, json_file: Path):
        with pytest.raises(TypeError, match=r"must be a sequence"):
            load(
                JsonSource(
                    file=json_file,
                    root_validators="not a container",
                ),
                schema=_PrivConfig,
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
                JsonSource(
                    file=json_file,
                    root_validators=(V >= 1,),
                ),
                schema=_PrivConfig,
            )

    def test_rejects_unrelated_object(self, json_file: Path):
        with pytest.raises(TypeError, match=r"must contain V\.root"):
            load(
                JsonSource(
                    file=json_file,
                    root_validators=("not a root predicate",),
                ),
                schema=_PrivConfig,
            )


class TestRootPredicateRejectedInAnnotated:
    def test_root_in_annotated_raises(self, tmp_path: Path):
        # RootPredicate placed in Annotated[...] is a schema error, not a data error.
        @dataclass
        class Bad:
            port: Annotated[int, V.root(lambda _: True)]

        json_file = tmp_path / "config.json"

        with pytest.raises(TypeError, match=r"source\.root_validators"):
            load(JsonSource(file=json_file), schema=Bad)

    def test_root_in_source_validators_raises(self, tmp_path: Path):
        @dataclass
        class Cfg:
            port: int

        from dature.field_path import F  # noqa: PLC0415

        json_file = tmp_path / "config.json"
        json_file.write_text('{"port": 8080}')

        with pytest.raises(TypeError, match=r"source\.root_validators"):
            load(
                JsonSource(
                    file=json_file,
                    validators={F[Cfg].port: V.root(lambda _: True)},  # type: ignore[dict-item]
                ),
                schema=Cfg,
            )
