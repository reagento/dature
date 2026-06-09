import pytest

from dature.errors import CrossRefExpandError
from dature.expansion.cross_source import (
    expand_cross_refs,
    find_refs,
)
from dature.type_aliases import JSONValue


class TestFindRefs:
    @pytest.mark.parametrize(
        ("text", "expected"),
        [
            ("${@cli.env}", [("cli", "env")]),
            ("${@env.db.host}", [("env", "db.host")]),
            ("${@vault.secret.key.nested}", [("vault", "secret.key.nested")]),
            ("${@env.HOST:-default}", [("env", "HOST")]),
            ("${@env.HOST:-}", [("env", "HOST")]),
            ("${@cli.env} and ${@env.HOST}", [("cli", "env"), ("env", "HOST")]),
            ("no refs here", []),
            ("$HOME", []),
            ("${HOME}", []),
        ],
        ids=[
            "single-simple",
            "nested-key",
            "deeply-nested-key",
            "with-default",
            "with-empty-default",
            "multiple-refs",
            "no-refs",
            "dollar-var",
            "brace-var",
        ],
    )
    def test_find_refs(self, text: str, expected: list[tuple[str, str]]) -> None:
        assert find_refs(text) == expected

    @pytest.mark.parametrize(
        "text",
        [
            "$${@cli.env}",
            "$${@cli.env}/path",
            "prefix/$${@cli.env}/suffix",
        ],
        ids=["just-escaped", "escaped-slash", "surrounded"],
    )
    def test_escaped_refs_not_returned(self, text: str) -> None:
        assert find_refs(text) == []

    def test_escaped_and_real_ref_together(self) -> None:
        result = find_refs("$${@cli.env}/${@env.HOST}")
        assert result == [("env", "HOST")]


class TestExpandCrossRefs:
    @pytest.mark.parametrize(
        ("text", "context", "expected"),
        [
            ("${@cli.env}", {"cli": {"env": "prod"}}, "prod"),
            ("${@env.db.host}", {"env": {"db": {"host": "localhost"}}}, "localhost"),
            ("${@cli.env}.json", {"cli": {"env": "prod"}}, "prod.json"),
            ("prefix-${@cli.env}-suffix", {"cli": {"env": "staging"}}, "prefix-staging-suffix"),
            (
                "${@cli.env} ${@env.HOST}",
                {"cli": {"env": "prod"}, "env": {"HOST": "example.com"}},
                "prod example.com",
            ),
            ("${@cli.port}", {"cli": {"port": 8080}}, "8080"),
            ("${@cli.enabled}", {"cli": {"enabled": True}}, "true"),
            ("${@cli.enabled}", {"cli": {"enabled": False}}, "false"),
            ("plain text", {}, "plain text"),
            ("", {}, ""),
        ],
        ids=[
            "simple",
            "nested-key",
            "with-suffix",
            "surrounded",
            "two-refs",
            "int-value",
            "bool-true",
            "bool-false",
            "no-refs-passthrough",
            "empty-string",
        ],
    )
    def test_basic_expansion(self, text: str, context: dict[str, dict[str, JSONValue]], expected: str) -> None:
        assert expand_cross_refs(text, context=context) == expected

    @pytest.mark.parametrize(
        ("text", "context", "expected"),
        [
            ("${@cli.missing:-fallback}", {"cli": {}}, "fallback"),
            ("${@cli.missing:-}", {"cli": {}}, ""),
            ("${@cli.missing:-with:colon}", {"cli": {}}, "with:colon"),
            ("${@cli.missing:-with spaces}", {"cli": {}}, "with spaces"),
        ],
        ids=["simple-default", "empty-default", "colon-in-default", "spaces-in-default"],
    )
    def test_default_on_missing_key(self, text: str, context: dict[str, dict[str, JSONValue]], expected: str) -> None:
        assert expand_cross_refs(text, context=context) == expected

    @pytest.mark.parametrize(
        ("text", "expected"),
        [
            ("$$", "$"),
            ("$${@cli.env}", "${@cli.env}"),
            ("$$HOME", "$HOME"),
            ("$$$$", "$$"),
        ],
        ids=["simple-escape", "escape-before-cross-ref", "escape-before-dollar-var", "double-escape"],
    )
    def test_escape_sequences(self, text: str, expected: str) -> None:
        assert expand_cross_refs(text, context={"cli": {"env": "prod"}}) == expected

    @pytest.mark.parametrize(
        ("text", "context", "expected_str"),
        [
            (
                "${@unknown.key}",
                {"cli": {}},
                "Cross-source reference errors (1)\n\n  '${@unknown.key}': unknown tag 'unknown'; known tags: 'cli'\n",
            ),
            (
                "${@cli.missing}",
                {"cli": {}},
                "Cross-source reference errors (1)\n\n"
                "  '${@cli.missing}': key 'missing' not found in 'cli' data and no default provided\n",
            ),
            (
                "${@cli.nested}",
                {"cli": {"nested": {"a": 1}}},
                "Cross-source reference errors (1)\n\n"
                "  '${@cli.nested}': key 'nested' in 'cli' is a dict;"
                " only scalar values (str, int, float, bool) are supported\n",
            ),
            (
                "${@unknown1.key} ${@unknown2.key}",
                {},
                "Cross-source reference errors (2)\n\n"
                "  '${@unknown1.key}': unknown tag 'unknown1'; known tags: none\n\n"
                "  '${@unknown2.key}': unknown tag 'unknown2'; known tags: none\n",
            ),
        ],
        ids=["unknown-tag", "missing-key", "non-scalar-value", "multiple-errors"],
    )
    def test_raises(self, text: str, context: dict[str, dict[str, JSONValue]], expected_str: str) -> None:
        with pytest.raises(CrossRefExpandError) as exc_info:
            expand_cross_refs(text, context=context)
        assert str(exc_info.value) == expected_str
