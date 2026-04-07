from dataclasses import dataclass
from typing import Annotated

from dature.type_utils import find_nested_dataclasses


class TestFindNestedDataclasses:
    def test_plain_dataclass(self):
        @dataclass
        class Inner:
            name: str

        result = find_nested_dataclasses(Inner)
        assert result == [Inner]

    def test_list_of_dataclasses(self):
        @dataclass
        class Inner:
            name: str

        result = find_nested_dataclasses(list[Inner])
        assert result == [Inner]

    def test_plain_type_no_dataclass(self):
        result = find_nested_dataclasses(str)
        assert result == []

    def test_optional_dataclass(self):
        @dataclass
        class Inner:
            name: str

        result = find_nested_dataclasses(Inner | None)
        assert result == [Inner]

    def test_annotated_dataclass(self):
        @dataclass
        class Inner:
            name: str

        result = find_nested_dataclasses(Annotated[Inner, "some_meta"])
        assert result == [Inner]

    def test_dict_value_dataclass(self):
        @dataclass
        class Inner:
            name: str

        result = find_nested_dataclasses(dict[str, Inner])
        assert result == [Inner]

    def test_nested_generic(self):
        @dataclass
        class Inner:
            name: str

        result = find_nested_dataclasses(list[Inner | None])
        assert result == [Inner]
