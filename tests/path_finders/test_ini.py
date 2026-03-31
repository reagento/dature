from dature.errors import LineRange
from dature.path_finders.ini_ import TablePathFinder


class TestIniFindLineRange:
    def test_key_not_confused_by_continuation_line(self):
        content = "[section]\nstr1 = line1\n  x = 1\nx = real\n"
        finder = TablePathFinder(content)

        assert finder.find_line_range(["section", "x"]) == LineRange(start=4, end=4)

    def test_key_with_colon_separator(self):
        content = "[app]\nstr1: line1\n  host: fake\nhost: production\n"
        finder = TablePathFinder(content)

        assert finder.find_line_range(["app", "host"]) == LineRange(start=4, end=4)

    def test_scalar_value(self):
        content = "[section]\nkey = value\n"
        finder = TablePathFinder(content)

        assert finder.find_line_range(["section", "key"]) == LineRange(start=2, end=2)

    def test_continuation_lines(self):
        content = "[section]\nkey = line1\n  line2\n  line3\n"
        finder = TablePathFinder(content)

        assert finder.find_line_range(["section", "key"]) == LineRange(start=2, end=4)

    def test_not_found(self):
        content = "[section]\nkey = value\n"
        finder = TablePathFinder(content)

        assert finder.find_line_range(["section", "missing"]) is None

    def test_no_continuation(self):
        content = "[app]\nhost = localhost\nport = 8080\n"
        finder = TablePathFinder(content)

        assert finder.find_line_range(["app", "host"]) == LineRange(start=2, end=2)
