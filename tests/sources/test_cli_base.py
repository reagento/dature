"""Tests for the abstract CliSource base class."""

from dataclasses import dataclass, field
from typing import ClassVar

import pytest

from dature import CliSource
from dature.errors import CaretSpan
from dature.types import JSONValue


@dataclass(kw_only=True, repr=False)
class _DictCliSource(CliSource):
    """Minimal CliSource for testing — emits a user-supplied flat dict."""

    format_name: ClassVar[str] = "mock"
    data: dict[str, JSONValue] = field(default_factory=dict)

    def _parse_argv(self) -> dict[str, JSONValue]:
        return self.data


class TestCliSourceAbstract:
    def test_cannot_instantiate_base(self):
        with pytest.raises(TypeError):
            CliSource()  # type: ignore[abstract]


class TestCliSourceCasePreservation:
    def test_build_var_name_preserves_case(self):
        src = _DictCliSource(data={})
        assert src._build_var_name("db") == "db"
        assert src._build_var_name("db--host") == "db--host"

    def test_build_var_name_with_prefix(self):
        src = _DictCliSource(data={}, prefix="myapp_")
        assert src._build_var_name("db") == "myapp_db"

    def test_nested_conflict_used_var_preserves_case(self):
        """A top-level string clashing with a nested key produces a NestedConflict
        whose ``used_var`` must be case-preserving so that
        :meth:`CliSource._resolve_flag_name` can compare it against the
        case-preserving flag name and pick the right display form.
        """
        # Top-level "db" set to a string + nested "db--host" → conflict (resolved to nested).
        src = _DictCliSource(
            data={"db": "raw_value", "db--host": "localhost"},
            nested_resolve_strategy="flat",
        )
        result = src.load_raw()

        conflict = result.nested_conflicts["db"]
        assert conflict.used_var == "db--host"
        assert conflict.ignored_var == "db"

    def test_resolve_flag_name_uses_top_level_when_conflict_resolved_to_json(self):
        """When the conflict's ``used_var`` matches the top-level form, the
        flag display should be the top-level name (e.g. ``--db``), not the
        full nested path (``--db--host``).
        """
        src = _DictCliSource(
            data={"db": "scalar_wins", "db--host": "localhost"},
            nested_resolve_strategy="json",
        )
        result = src.load_raw()
        conflict = result.nested_conflicts["db"]
        assert conflict.used_var == "db"  # case-preserving — would have been "DB" before fix

        locations = src.resolve_location(
            field_path=["db", "host"],
            file_content=None,
            nested_conflict=conflict,
        )
        assert locations[0].env_var_name == "--db"

    def test_resolve_flag_name_uses_full_path_when_no_conflict(self):
        src = _DictCliSource(data={})
        locations = src.resolve_location(
            field_path=["db", "host"],
            file_content=None,
            nested_conflict=None,
        )
        assert locations[0].env_var_name == "--db--host"


class TestCliSourceResolveLocation:
    @pytest.mark.parametrize(
        ("input_value", "expected_line_content", "expected_carets"),
        [
            (
                None,
                ["--host"],
                [CaretSpan(start=0, end=6)],
            ),
            (
                "localhost",
                ["--host localhost"],
                [CaretSpan(start=7, end=16)],
            ),
            (
                "line1\nline2",
                ["--host line1", "line2"],
                [CaretSpan(start=7, end=12), CaretSpan(start=0, end=5)],
            ),
        ],
        ids=["no-value", "scalar-value", "multiline-value"],
    )
    def test_resolve_location_line_content(
        self,
        input_value: JSONValue,
        expected_line_content: list[str],
        expected_carets: list[CaretSpan],
    ) -> None:
        src = _DictCliSource(data={})
        locations = src.resolve_location(
            field_path=["host"],
            file_content=None,
            nested_conflict=None,
            input_value=input_value,
        )
        assert locations[0].line_content == expected_line_content
        assert locations[0].line_carets == expected_carets


class TestCliSourceEnvExpansionDefault:
    def test_default_is_disabled(self):
        """Shell has already expanded ``$VAR`` by the time the value reaches
        Python; re-expanding turns quoted literals like ``'$ecret'`` into ``''``.
        ``CliSource`` opts out of env-var expansion by default.
        """
        src = _DictCliSource(data={"password": "$ecret_value"})
        result = src.load_raw()
        assert result.data == {"password": "$ecret_value"}

    def test_can_opt_in(self, monkeypatch: pytest.MonkeyPatch):
        """Users who want CLI values re-expanded set ``expand_env_vars`` explicitly."""
        monkeypatch.setenv("DB_PASS", "actual_secret")
        src = _DictCliSource(data={"password": "$DB_PASS"}, expand_env_vars="default")
        result = src.load_raw()
        assert result.data == {"password": "actual_secret"}
