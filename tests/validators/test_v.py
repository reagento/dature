"""Unit tests for the ``V`` singleton itself — DSL-value rejection, unhashability.

Predicate-specific tests live next to each predicate:

- ``test_compare.py`` — ``ComparePredicate`` / ``LengthComparePredicate``
- ``test_text.py`` — ``MatchesPredicate``
- ``test_collection.py`` — ``In`` / ``UniqueItems`` / ``Each``
- ``test_composition.py`` — ``And`` / ``Or`` / ``Not``
- ``test_custom.py`` — ``V.check``
- ``test_v_root.py`` — ``V.root`` (unit + integration)
"""

import pytest

from dature import V


class TestDslValueRejection:
    def test_v_compared_with_v_raises(self) -> None:
        with pytest.raises(TypeError, match="V-DSL object as a value"):
            _ = V == V  # noqa: PLR0124

    def test_v_ge_v_raises(self) -> None:
        with pytest.raises(TypeError, match="V-DSL object as a value"):
            _ = V >= V  # noqa: PLR0124

    def test_v_len_eq_v_len_raises(self) -> None:
        with pytest.raises(TypeError, match="V-DSL object as a value"):
            _ = V.len() == V.len()

    def test_v_compared_with_predicate_raises(self) -> None:
        with pytest.raises(TypeError, match="V-DSL object as a value"):
            _ = (V >= 1) == V


class TestVIsUnhashable:
    def test_v_unhashable(self) -> None:
        with pytest.raises(TypeError):
            hash(V)

    def test_length_accessor_unhashable(self) -> None:
        with pytest.raises(TypeError):
            hash(V.len())
