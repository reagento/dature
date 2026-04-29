"""Tests for string-name resolution into strategy instances."""

import pytest

from dature.errors import DatureConfigError, SourceLoadError
from dature.strategies.field import (
    FieldAppend,
    FieldAppendUnique,
    FieldFirstWins,
    FieldLastWins,
    FieldPrepend,
    FieldPrependUnique,
    resolve_field_strategy,
)
from dature.strategies.source import (
    SourceFirstFound,
    SourceFirstWins,
    SourceLastWins,
    SourceRaiseOnConflict,
    resolve_source_strategy,
)


class TestResolveSourceStrategy:
    @pytest.mark.parametrize(
        ("name", "cls"),
        [
            ("last_wins", SourceLastWins),
            ("first_wins", SourceFirstWins),
            ("first_found", SourceFirstFound),
            ("raise_on_conflict", SourceRaiseOnConflict),
        ],
    )
    def test_string_resolves_to_class(self, name, cls):
        resolved = resolve_source_strategy(name)
        assert isinstance(resolved, cls)

    def test_instance_passes_through(self):
        my_strategy = SourceLastWins()
        assert resolve_source_strategy(my_strategy) is my_strategy

    def test_unknown_string_raises_with_full_message(self):
        expected = "invalid merge strategy: 'foo'. Available: last_wins, first_wins, first_found, raise_on_conflict"
        with pytest.raises(DatureConfigError) as exc_info:
            resolve_source_strategy("foo", dataclass_name="Config")

        (inner,) = exc_info.value.exceptions
        assert isinstance(inner, SourceLoadError)
        assert inner.message == expected


class TestResolveFieldStrategy:
    @pytest.mark.parametrize(
        ("name", "cls"),
        [
            ("first_wins", FieldFirstWins),
            ("last_wins", FieldLastWins),
            ("append", FieldAppend),
            ("append_unique", FieldAppendUnique),
            ("prepend", FieldPrepend),
            ("prepend_unique", FieldPrependUnique),
        ],
    )
    def test_string_resolves_to_class(self, name, cls):
        resolved = resolve_field_strategy(name)
        assert isinstance(resolved, cls)

    def test_instance_passes_through(self):
        my_strategy = FieldAppend()
        assert resolve_field_strategy(my_strategy) is my_strategy

    def test_unknown_string_raises_with_full_message(self):
        expected = (
            "invalid field merge strategy: 'foo'. "
            "Available: first_wins, last_wins, append, append_unique, prepend, prepend_unique"
        )
        with pytest.raises(DatureConfigError) as exc_info:
            resolve_field_strategy("foo", dataclass_name="Config")

        (inner,) = exc_info.value.exceptions
        assert isinstance(inner, SourceLoadError)
        assert inner.message == expected
