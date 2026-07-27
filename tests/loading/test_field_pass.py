"""Unit tests for dature.loading.field_pass — field-pass run, error merge, and decorator replay."""

from dataclasses import dataclass
from typing import Annotated, cast

import pytest

from dature import V
from dature.errors import DatureConfigError, FieldLoadError
from dature.errors.location import ErrorContext
from dature.loading.context import build_error_ctx
from dature.loading.field_pass import (
    build_revalidation,
    compute_default_fallback_errors,
    merge_root_and_field_errors,
    run_source_field_pass,
)
from dature.loading.retort import RetortCache
from dature.protocols import DataclassInstance
from dature.sources.base import IndexedSource, Source
from dature.type_aliases import JSONValue


@dataclass(kw_only=True)
class _MockSource(Source):
    format_name: str = "mock"
    location_label: str = "MOCK"
    test_data: JSONValue = None

    def __post_init__(self) -> None:
        super().__post_init__()
        if self.test_data is None:
            self.test_data = {}

    def _load(self) -> JSONValue:
        return self.test_data


def _make_field_error(path: list[str]) -> FieldLoadError:
    return FieldLoadError(field_path=path, message="bad")


class TestMergeRootAndFieldErrors:
    def test_disjoint_paths_both_kept(self):
        root = [_make_field_error(["port"])]
        field = [_make_field_error(["name"])]

        exc = merge_root_and_field_errors("Config", root, field)

        assert isinstance(exc, DatureConfigError)
        assert len(list(exc.exceptions)) == 2

    def test_root_errors_come_first(self):
        root = [_make_field_error(["port"])]
        field = [_make_field_error(["name"])]

        exc = merge_root_and_field_errors("Config", root, field)
        errors = [cast("FieldLoadError", e) for e in exc.exceptions]

        assert errors[0].field_path == ["port"]
        assert errors[1].field_path == ["name"]

    def test_overlapping_path_field_error_dropped(self):
        root = [_make_field_error(["port"])]
        field = [_make_field_error(["port"])]

        exc = merge_root_and_field_errors("Config", root, field)

        assert len(list(exc.exceptions)) == 1

    def test_schema_name_preserved(self):
        exc = merge_root_and_field_errors("MySchema", [_make_field_error(["x"])], [])

        assert exc.dataclass_name == "MySchema"

    def test_empty_field_errors(self):
        root = [_make_field_error(["port"])]

        exc = merge_root_and_field_errors("Config", root, [])

        assert len(list(exc.exceptions)) == 1

    def test_empty_root_errors(self):
        field = [_make_field_error(["port"])]

        exc = merge_root_and_field_errors("Config", [], field)

        assert len(list(exc.exceptions)) == 1


@dataclass
class _ConfigWithDefault:
    port: Annotated[int, V >= 0] = -1
    name: str = "default"


@dataclass
class _PlainDefault:
    value: int = 0


class TestComputeDefaultFallbackErrors:
    @pytest.mark.parametrize(
        ("schema", "result", "validated_field_names", "expected_paths"),
        [
            pytest.param(_ConfigWithDefault, _ConfigWithDefault(), set(), [["port"]], id="failing-default"),
            pytest.param(_ConfigWithDefault, _ConfigWithDefault(), {"port"}, [], id="field-in-validated-set-skipped"),
            pytest.param(_ConfigWithDefault, _ConfigWithDefault(port=5), set(), [], id="passing-default"),
            pytest.param(_PlainDefault, _PlainDefault(), set(), [], id="no-validator"),
        ],
    )
    def test_compute(
        self,
        schema: type,
        result: DataclassInstance,
        validated_field_names: set[str],
        expected_paths: list[list[str]],
    ):
        # annotated_default_fields is the schema's precomputed (field, predicates) map (W1).
        annotated_default_fields = RetortCache(schema).annotated_default_fields
        errors = compute_default_fallback_errors(annotated_default_fields, validated_field_names, result)

        assert [e.field_path for e in errors] == expected_paths


@dataclass
class _ConfigWithValidator:
    port: Annotated[int, V >= 0]
    name: str = "default"


class TestRunSourceFieldPass:
    def _setup(self) -> tuple[IndexedSource, RetortCache, ErrorContext]:
        source = _MockSource()
        indexed = IndexedSource(source, 0)
        cache = RetortCache(_ConfigWithValidator)
        ctx = build_error_ctx(source, "Config")
        return indexed, cache, ctx

    def test_valid_raw_returns_dict_and_empty_errors(self):
        indexed, cache, ctx = self._setup()

        result_dict, errors = run_source_field_pass(
            indexed=indexed,
            raw={"port": 5},
            schema=_ConfigWithValidator,
            retort_cache=cache,
            resolved_type_loaders=None,
            error_ctx=ctx,
            loaded_data={"port": 5},
        )

        assert errors == []
        assert isinstance(result_dict, dict)

    def test_invalid_raw_returns_none_and_errors(self):
        indexed, cache, ctx = self._setup()

        result_dict, errors = run_source_field_pass(
            indexed=indexed,
            raw={"port": -1},
            schema=_ConfigWithValidator,
            retort_cache=cache,
            resolved_type_loaders=None,
            error_ctx=ctx,
            loaded_data={"port": -1},
        )

        assert result_dict is None
        assert len(errors) == 1
        assert errors[0].field_path == ["port"]


@dataclass
class _ConfigRequired:
    port: Annotated[int, V >= 0]
    name: str


class TestBuildRevalidation:
    def _source_and_cache(self, schema: type) -> tuple[IndexedSource, RetortCache]:
        source = _MockSource()
        indexed = IndexedSource(source, 0)
        cache = RetortCache(schema)
        return indexed, cache

    def test_no_validators_loader_builds_instance(self):
        @dataclass
        class Plain:
            port: int
            name: str

        indexed, cache = self._source_and_cache(Plain)
        loader, ctx = build_revalidation(
            indexed=indexed,
            schema=Plain,
            retort_cache=cache,
            type_loaders=None,
            secret_paths=frozenset(),
            mask_secrets=False,
        )

        assert isinstance(ctx, ErrorContext)
        result = loader({"port": 8080, "name": "app"})
        assert result == Plain(port=8080, name="app")

    def test_with_validator_valid_data_returns_instance(self):
        indexed, cache = self._source_and_cache(_ConfigRequired)
        loader, _ = build_revalidation(
            indexed=indexed,
            schema=_ConfigRequired,
            retort_cache=cache,
            type_loaders=None,
            secret_paths=frozenset(),
            mask_secrets=False,
        )

        result = loader({"port": 5, "name": "ok"})
        assert result == _ConfigRequired(port=5, name="ok")

    def test_with_validator_invalid_data_raises(self):
        indexed, cache = self._source_and_cache(_ConfigRequired)
        loader, _ = build_revalidation(
            indexed=indexed,
            schema=_ConfigRequired,
            retort_cache=cache,
            type_loaders=None,
            secret_paths=frozenset(),
            mask_secrets=False,
        )

        with pytest.raises(DatureConfigError, match=r"_ConfigRequired") as exc_info:
            loader({"port": -1, "name": "ok"})
        assert str(exc_info.value) == "_ConfigRequired loading errors (1)"

    def test_combined_root_and_field_errors_deduped(self):
        # port=-1: field_pass fails (V>=0); root_retort succeeds on coercion but name is absent
        indexed, cache = self._source_and_cache(_ConfigRequired)
        loader, _ = build_revalidation(
            indexed=indexed,
            schema=_ConfigRequired,
            retort_cache=cache,
            type_loaders=None,
            secret_paths=frozenset(),
            mask_secrets=False,
        )

        with pytest.raises(DatureConfigError, match=r"_ConfigRequired") as exc_info:
            loader({"port": -1})
        assert str(exc_info.value) == "_ConfigRequired loading errors (2)"

        errors = [cast("FieldLoadError", e) for e in exc_info.value.exceptions]
        assert {tuple(e.field_path) for e in errors} == {("name",), ("port",)}
