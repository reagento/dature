from dature.errors import LineRange
from dature.path_finders.json5_ import Json5PathFinder


class TestJson5FindLineRange:
    def test_key_not_confused_by_newline_in_value(self):
        content = "{\n  str1: 'line1\\nkey=1',\n  key: 'real'\n}"
        finder = Json5PathFinder(content)

        assert finder.find_line_range(["key"]) == LineRange(start=3, end=3)

    def test_key_not_confused_by_escaped_quotes(self):
        content = '{\n  str1: "he said \\"key\\": value",\n  key: 42\n}'
        finder = Json5PathFinder(content)

        assert finder.find_line_range(["key"]) == LineRange(start=3, end=3)

    def test_scalar_value(self):
        content = "{\n  timeout: 30\n}"
        finder = Json5PathFinder(content)

        assert finder.find_line_range(["timeout"]) == LineRange(start=2, end=2)

    def test_multiline_dict(self):
        content = '{\n  db: {\n    host: "localhost",\n    port: 5432\n  }\n}'
        finder = Json5PathFinder(content)

        assert finder.find_line_range(["db"]) == LineRange(start=2, end=5)

    def test_multiline_array(self):
        content = '{\n  tags: [\n    "a",\n    "b"\n  ]\n}'
        finder = Json5PathFinder(content)

        assert finder.find_line_range(["tags"]) == LineRange(start=2, end=5)

    def test_not_found(self):
        content = '{\n  name: "test"\n}'
        finder = Json5PathFinder(content)

        assert finder.find_line_range(["missing"]) is None

    def test_inline_dict(self):
        content = '{\n  db: {host: "localhost"}\n}'
        finder = Json5PathFinder(content)

        assert finder.find_line_range(["db"]) == LineRange(start=2, end=2)

    def test_inline_array(self):
        content = '{\n  tags: ["a", "b"]\n}'
        finder = Json5PathFinder(content)

        assert finder.find_line_range(["tags"]) == LineRange(start=2, end=2)
