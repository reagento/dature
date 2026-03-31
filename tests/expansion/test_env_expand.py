import pytest

from dature.errors import EnvVarExpandError
from dature.expansion.env_expand import expand_env_vars, expand_string
from dature.types import JSONValue


class TestExpandStringDisabled:
    @pytest.mark.parametrize(
        ("text", "expected"),
        [
            ("$HOME/path", "$HOME/path"),
            ("${HOME}/path", "${HOME}/path"),
            ("%HOME%/path", "%HOME%/path"),
            ("$$escaped", "$$escaped"),
        ],
        ids=["dollar", "braces", "percent", "escaped-dollar"],
    )
    def test_no_expansion(self, text: str, expected: str) -> None:
        result = expand_string(text, mode="disabled")

        assert result == expected


class TestExpandStringExistingVar:
    @pytest.mark.parametrize(
        ("text", "expected"),
        [
            ("$DATURE_TEST_VAR/path", "hello/path"),
            ("${DATURE_TEST_VAR}/path", "hello/path"),
            ("%DATURE_TEST_VAR%/path", "hello/path"),
            ("${DATURE_TEST_VAR:-fallback}/path", "hello/path"),
            ("${DATURE_TEST_VAR:-$OTHER}/path", "hello/path"),
        ],
        ids=["dollar", "braces", "percent", "braces-string-fallback-ignored", "braces-var-fallback-ignored"],
    )
    @pytest.mark.parametrize("mode", ["default", "empty", "strict"])
    def test_existing_var_expanded(
        self,
        monkeypatch: pytest.MonkeyPatch,
        text: str,
        expected: str,
        mode: str,
    ) -> None:
        monkeypatch.setenv("DATURE_TEST_VAR", "hello")

        result = expand_string(text, mode=mode)

        assert result == expected


class TestExpandStringMissingVarDefault:
    @pytest.mark.parametrize(
        ("text", "expected"),
        [
            ("$DATURE_MISSING/path", "$DATURE_MISSING/path"),
            ("${DATURE_MISSING}/path", "${DATURE_MISSING}/path"),
            ("%DATURE_MISSING%/path", "%DATURE_MISSING%/path"),
        ],
        ids=["dollar", "braces", "percent"],
    )
    def test_missing_var_kept(self, monkeypatch: pytest.MonkeyPatch, text: str, expected: str) -> None:
        monkeypatch.delenv("DATURE_MISSING", raising=False)

        result = expand_string(text, mode="default")

        assert result == expected


class TestExpandStringMissingVarEmpty:
    @pytest.mark.parametrize(
        ("text", "expected"),
        [
            ("$DATURE_MISSING/path", "/path"),
            ("${DATURE_MISSING}/path", "/path"),
            ("%DATURE_MISSING%/path", "/path"),
        ],
        ids=["dollar", "braces", "percent"],
    )
    def test_missing_var_becomes_empty(self, monkeypatch: pytest.MonkeyPatch, text: str, expected: str) -> None:
        monkeypatch.delenv("DATURE_MISSING", raising=False)

        result = expand_string(text, mode="empty")

        assert result == expected


class TestExpandStringMissingVarStrict:
    @pytest.mark.parametrize(
        ("text", "expected_error"),
        [
            (
                "$DATURE_MISSING/path",
                "Missing environment variables (1)\n\n  [<root>]  Missing environment variable 'DATURE_MISSING'\n",
            ),
            (
                "${DATURE_MISSING}/path",
                "Missing environment variables (1)\n\n  [<root>]  Missing environment variable 'DATURE_MISSING'\n",
            ),
            (
                "%DATURE_MISSING%/path",
                "Missing environment variables (1)\n\n  [<root>]  Missing environment variable 'DATURE_MISSING'\n",
            ),
        ],
        ids=["dollar", "braces", "percent"],
    )
    def test_missing_var_raises(
        self,
        monkeypatch: pytest.MonkeyPatch,
        text: str,
        expected_error: str,
    ) -> None:
        monkeypatch.delenv("DATURE_MISSING", raising=False)

        with pytest.raises(EnvVarExpandError) as exc_info:
            expand_string(text, mode="strict")

        assert str(exc_info.value) == expected_error

    def test_multiple_missing_vars(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("DATURE_A", raising=False)
        monkeypatch.delenv("DATURE_B", raising=False)

        with pytest.raises(EnvVarExpandError) as exc_info:
            expand_string("$DATURE_A and ${DATURE_B}", mode="strict")

        assert str(exc_info.value) == (
            "Missing environment variables (2)\n\n"
            "  [<root>]  Missing environment variable 'DATURE_A'\n\n"
            "  [<root>]  Missing environment variable 'DATURE_B'\n"
        )


class TestExpandStringFallback:
    @pytest.mark.parametrize(
        ("text", "expected"),
        [
            ("${VAR:-}", ""),
            ("${VAR:-default}", "default"),
            ("${VAR:-with spaces}", "with spaces"),
            ("${VAR:-with:colon}", "with:colon"),
        ],
        ids=["empty-fallback", "simple-fallback", "spaces-fallback", "colon-fallback"],
    )
    @pytest.mark.parametrize("mode", ["default", "empty", "strict"])
    def test_fallback_on_missing_var(
        self,
        monkeypatch: pytest.MonkeyPatch,
        text: str,
        expected: str,
        mode: str,
    ) -> None:
        monkeypatch.delenv("VAR", raising=False)

        result = expand_string(text, mode=mode)

        assert result == expected

    @pytest.mark.parametrize("mode", ["default", "empty", "strict"])
    def test_fallback_expands_nested_var(self, monkeypatch: pytest.MonkeyPatch, mode: str) -> None:
        monkeypatch.delenv("DATURE_MISSING", raising=False)
        monkeypatch.setenv("DATURE_FALLBACK", "resolved")

        result = expand_string("${DATURE_MISSING:-$DATURE_FALLBACK}", mode=mode)

        assert result == "resolved"

    def test_fallback_with_missing_nested_var_strict_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("DATURE_MISSING", raising=False)
        monkeypatch.delenv("DATURE_ALSO_MISSING", raising=False)

        with pytest.raises(EnvVarExpandError) as exc_info:
            expand_string("${DATURE_MISSING:-$DATURE_ALSO_MISSING}", mode="strict")

        assert str(exc_info.value) == (
            "Missing environment variables (1)\n\n  [<root>]  Missing environment variable 'DATURE_ALSO_MISSING'\n"
        )

    @pytest.mark.parametrize(
        ("mode", "expected"),
        [
            ("default", "$DATURE_ALSO_MISSING"),
            ("empty", ""),
        ],
        ids=["default-keeps", "empty-blank"],
    )
    def test_fallback_with_missing_nested_var(
        self,
        monkeypatch: pytest.MonkeyPatch,
        mode: str,
        expected: str,
    ) -> None:
        monkeypatch.delenv("DATURE_MISSING", raising=False)
        monkeypatch.delenv("DATURE_ALSO_MISSING", raising=False)

        result = expand_string("${DATURE_MISSING:-$DATURE_ALSO_MISSING}", mode=mode)

        assert result == expected


class TestExpandStringEscaping:
    @pytest.mark.parametrize(
        ("text", "expected"),
        [
            ("$$", "$"),
            ("%%", "%"),
            ("$$HOME", "$HOME"),
            ("100%%", "100%"),
            ("$$$$", "$$"),
            ("%%%%", "%%"),
        ],
        ids=["dollar", "percent", "dollar-before-name", "percent-after-number", "double-dollar", "double-percent"],
    )
    @pytest.mark.parametrize("mode", ["default", "empty", "strict"])
    def test_escape_sequences(self, text: str, expected: str, mode: str) -> None:
        result = expand_string(text, mode=mode)

        assert result == expected


class TestExpandStringMixed:
    @pytest.mark.parametrize(
        ("env_vars", "text", "expected"),
        [
            (
                {"DATURE_HOST": "localhost", "DATURE_PORT": "8080"},
                "http://$DATURE_HOST:$DATURE_PORT/api",
                "http://localhost:8080/api",
            ),
            (
                {"DATURE_A": "alpha", "DATURE_B": "beta"},
                "$DATURE_A and ${DATURE_B}",
                "alpha and beta",
            ),
        ],
        ids=["multiple-vars", "mixed-syntaxes"],
    )
    def test_multiple_vars(
        self,
        monkeypatch: pytest.MonkeyPatch,
        env_vars: dict[str, str],
        text: str,
        expected: str,
    ) -> None:
        for key, value in env_vars.items():
            monkeypatch.setenv(key, value)

        result = expand_string(text, mode="default")

        assert result == expected

    @pytest.mark.parametrize(
        ("text", "expected"),
        [
            ("no variables here", "no variables here"),
            ("", ""),
        ],
        ids=["plain-text", "empty-string"],
    )
    def test_no_vars(self, text: str, expected: str) -> None:
        result = expand_string(text, mode="default")

        assert result == expected


class TestExpandEnvVars:
    def test_disabled_returns_data_as_is(self) -> None:
        data: JSONValue = {"key": "$VAR", "list": ["$VAR"]}

        result = expand_env_vars(data, mode="disabled")

        assert result == data

    @pytest.mark.parametrize(
        ("data", "env_vars", "expected"),
        [
            (
                {"host": "$DATURE_HOST", "port": 8080},
                {"DATURE_HOST": "localhost"},
                {"host": "localhost", "port": 8080},
            ),
            (
                ["$DATURE_ITEM", "static", 42],
                {"DATURE_ITEM": "value"},
                ["value", "static", 42],
            ),
            (
                {"database": {"host": "$DATURE_DB_HOST", "port": 5432}},
                {"DATURE_DB_HOST": "db.example.com"},
                {"database": {"host": "db.example.com", "port": 5432}},
            ),
        ],
        ids=["dict", "list", "nested-dict"],
    )
    def test_expand_structures(
        self,
        monkeypatch: pytest.MonkeyPatch,
        data: JSONValue,
        env_vars: dict[str, str],
        expected: JSONValue,
    ) -> None:
        for key, value in env_vars.items():
            monkeypatch.setenv(key, value)

        result = expand_env_vars(data, mode="default")

        assert result == expected

    @pytest.mark.parametrize(
        ("data", "expected"),
        [
            (42, 42),
            (3.14, 3.14),
            (None, None),
            (True, True),
        ],
        ids=["int", "float", "none", "bool"],
    )
    def test_non_string_passthrough(self, data: JSONValue, expected: JSONValue) -> None:
        result = expand_env_vars(data, mode="default")

        assert result == expected

    def test_strict_nested_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("DATURE_MISSING", raising=False)
        data: JSONValue = {"key": {"nested": "$DATURE_MISSING"}}

        with pytest.raises(EnvVarExpandError):
            expand_env_vars(data, mode="strict")
