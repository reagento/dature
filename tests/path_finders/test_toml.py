from dature.errors import LineRange
from dature.path_finders.toml_ import Toml10PathFinder, Toml11PathFinder


class TestToml10FindLineRange:
    def test_key_after_multiline_double_quotes(self):
        content = 'str1 = """\nx=1\nViolets are blue"""\nx = 1\n'
        finder = Toml10PathFinder(content)

        assert finder.find_line_range(["x"]) == LineRange(start=4, end=4)

    def test_key_inside_multiline_not_matched_as_real_key(self):
        content = 'str1 = """\nhost = localhost\n"""\nhost = "production"\n'
        finder = Toml10PathFinder(content)

        assert finder.find_line_range(["host"]) == LineRange(start=4, end=4)

    def test_key_after_multiline_single_quotes(self):
        content = "str1 = '''\nport = 8080\n'''\nport = 3000\n"
        finder = Toml10PathFinder(content)

        assert finder.find_line_range(["port"]) == LineRange(start=4, end=4)

    def test_key_only_inside_multiline_returns_not_found(self):
        content = 'str1 = """\nx = 1\n"""\n'
        finder = Toml10PathFinder(content)

        assert finder.find_line_range(["x"]) is None

    def test_scalar_value(self):
        content = "timeout = 30\n"
        finder = Toml10PathFinder(content)

        assert finder.find_line_range(["timeout"]) == LineRange(start=1, end=1)

    def test_multiline_double_quote_string(self):
        content = 'key = """\nline1\nline2\n"""\n'
        finder = Toml10PathFinder(content)

        assert finder.find_line_range(["key"]) == LineRange(start=1, end=4)

    def test_multiline_single_quote_string(self):
        content = "key = '''\nline1\nline2\n'''\n"
        finder = Toml10PathFinder(content)

        assert finder.find_line_range(["key"]) == LineRange(start=1, end=4)

    def test_single_line_triple_quote_string(self):
        content = 'key = """single-line"""\n'
        finder = Toml10PathFinder(content)

        assert finder.find_line_range(["key"]) == LineRange(start=1, end=1)

    def test_multiline_array(self):
        content = 'tags = [\n  "a",\n  "b"\n]\n'
        finder = Toml10PathFinder(content)

        assert finder.find_line_range(["tags"]) == LineRange(start=1, end=4)

    def test_not_found(self):
        content = 'name = "test"\n'
        finder = Toml10PathFinder(content)

        assert finder.find_line_range(["missing"]) is None

    def test_inline_array(self):
        content = 'tags = ["a", "b"]\n'
        finder = Toml10PathFinder(content)

        assert finder.find_line_range(["tags"]) == LineRange(start=1, end=1)

    def test_inline_table(self):
        content = 'db = {host = "localhost", port = 5432}\n'
        finder = Toml10PathFinder(content)

        assert finder.find_line_range(["db", "host"]) == LineRange(start=1, end=1)

    def test_array_of_tables_nested_key(self):
        content = (
            '[[product]]\nname = "Hammer"\nsku = 738594937\n\n'
            "[[product]]\n\n"
            '[[product]]\nname = "Nail"\nsku = 284758393\n\n'
            'color = "gray"\n'
        )
        finder = Toml10PathFinder(content)

        assert finder.find_line_range(["product", "0", "name"]) == LineRange(start=2, end=2)
        assert finder.find_line_range(["product", "0", "sku"]) == LineRange(start=3, end=3)
        assert finder.find_line_range(["product", "2", "name"]) == LineRange(start=8, end=8)
        assert finder.find_line_range(["product", "2", "sku"]) == LineRange(start=9, end=9)
        assert finder.find_line_range(["product", "2", "color"]) == LineRange(start=11, end=11)


class TestToml11FindLineRange:
    def test_key_after_multiline_double_quotes(self):
        content = 'str1 = """\nx=1\nViolets are blue"""\nx = 1\n'
        finder = Toml11PathFinder(content)

        assert finder.find_line_range(["x"]) == LineRange(start=4, end=4)

    def test_key_inside_multiline_not_matched_as_real_key(self):
        content = 'str1 = """\nhost = localhost\n"""\nhost = "production"\n'
        finder = Toml11PathFinder(content)

        assert finder.find_line_range(["host"]) == LineRange(start=4, end=4)

    def test_key_after_multiline_single_quotes(self):
        content = "str1 = '''\nport = 8080\n'''\nport = 3000\n"
        finder = Toml11PathFinder(content)

        assert finder.find_line_range(["port"]) == LineRange(start=4, end=4)

    def test_key_only_inside_multiline_returns_not_found(self):
        content = 'str1 = """\nx = 1\n"""\n'
        finder = Toml11PathFinder(content)

        assert finder.find_line_range(["x"]) is None

    def test_scalar_value(self):
        content = "timeout = 30\n"
        finder = Toml11PathFinder(content)

        assert finder.find_line_range(["timeout"]) == LineRange(start=1, end=1)

    def test_multiline_double_quote_string(self):
        content = 'key = """\nline1\nline2\n"""\n'
        finder = Toml11PathFinder(content)

        assert finder.find_line_range(["key"]) == LineRange(start=1, end=4)

    def test_multiline_single_quote_string(self):
        content = "key = '''\nline1\nline2\n'''\n"
        finder = Toml11PathFinder(content)

        assert finder.find_line_range(["key"]) == LineRange(start=1, end=4)

    def test_single_line_triple_quote_string(self):
        content = 'key = """single-line"""\n'
        finder = Toml11PathFinder(content)

        assert finder.find_line_range(["key"]) == LineRange(start=1, end=1)

    def test_multiline_array(self):
        content = 'tags = [\n  "a",\n  "b"\n]\n'
        finder = Toml11PathFinder(content)

        assert finder.find_line_range(["tags"]) == LineRange(start=1, end=4)

    def test_not_found(self):
        content = 'name = "test"\n'
        finder = Toml11PathFinder(content)

        assert finder.find_line_range(["missing"]) is None

    def test_inline_array(self):
        content = 'tags = ["a", "b"]\n'
        finder = Toml11PathFinder(content)

        assert finder.find_line_range(["tags"]) == LineRange(start=1, end=1)

    def test_inline_table(self):
        content = 'db = {host = "localhost", port = 5432}\n'
        finder = Toml11PathFinder(content)

        assert finder.find_line_range(["db", "host"]) == LineRange(start=1, end=1)

    def test_multiline_inline_table(self):
        content = 'db = {\n  host = "localhost",\n  port = 5432\n}\n'
        finder = Toml11PathFinder(content)

        assert finder.find_line_range(["db"]) == LineRange(start=1, end=4)
