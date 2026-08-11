from dataclasses import dataclass
from typing import Annotated

import pytest

from dature.field_path import Absolute, F
from dature.fields.payment_card import PaymentCardNumber
from dature.fields.secret_str import SecretStr
from dature.masking.detection import (
    _is_secret_type,
    _matches_secret_pattern,
    build_secret_paths,
    canonical_name,
    canonical_secret_paths,
    matches_secret_name,
)

# --- module-level schemas for parametrize ---


@dataclass
class _SecretStrCfg:
    api_key: SecretStr
    host: str


@dataclass
class _PaymentCfg:
    card: PaymentCardNumber
    name: str


@dataclass
class _NameBasedCfg:
    password: str
    db_token: str
    host: str


@dataclass
class _AnnotatedCfg:
    key: Annotated[SecretStr, "some metadata"]
    host: str


@dataclass
class _OptionalCfg:
    key: SecretStr | None
    host: str


@dataclass
class _InnerCfg:
    secret: SecretStr
    host: str


@dataclass
class _OuterCfg:
    inner: _InnerCfg
    name: str


@dataclass
class _DbConfig:
    password: str
    host: str


@dataclass
class _DatabaseCfg:
    database: _DbConfig


@dataclass
class _ExtraPatternCfg:
    my_custom_field: str
    host: str


class TestBuildSecretPaths:
    @pytest.mark.parametrize(
        ("schema", "extra_patterns", "field_mappings", "expected"),
        [
            (_SecretStrCfg, (), (), frozenset({"api_key"})),
            (_PaymentCfg, (), (), frozenset({"card"})),
            (_NameBasedCfg, (), (), frozenset({"password", "db_token"})),
            (_AnnotatedCfg, (), (), frozenset({"key"})),
            (_OptionalCfg, (), (), frozenset({"key"})),
            (_OuterCfg, (), (), frozenset({"inner.secret"})),
            (_DatabaseCfg, (), (), frozenset({"database.password"})),
            (_ExtraPatternCfg, ("custom",), (), frozenset({"my_custom_field"})),
            (
                _SecretStrCfg,
                (),
                ({F[_SecretStrCfg].api_key: "API_KEY_ALIAS"},),
                frozenset({"api_key", "API_KEY_ALIAS"}),
            ),
            (
                _OuterCfg,
                (),
                ({F[_OuterCfg].inner.secret: "aliasedSecret"},),
                frozenset({"inner.secret", "aliasedSecret", "inner.aliasedSecret"}),
            ),
            (
                _SecretStrCfg,
                (),
                ({F[_SecretStrCfg].api_key: ("ALIAS1", "ALIAS2")},),
                frozenset({"api_key", "ALIAS1", "ALIAS2"}),
            ),
            (
                _SecretStrCfg,
                (),
                ({F[_SecretStrCfg].host: "HOST_ALIAS"},),
                frozenset({"api_key"}),
            ),
            (
                _SecretStrCfg,
                (),
                ({F[_SecretStrCfg].api_key: Absolute("APIKEY_ABS")},),
                frozenset({"api_key", "APIKEY_ABS"}),
            ),
        ],
        ids=[
            "secret-str",
            "payment-card",
            "name-based",
            "annotated",
            "optional",
            "nested-dc",
            "nested-name",
            "extra-patterns",
            "alias-root-string",
            "alias-nested",
            "alias-sequence",
            "alias-non-secret-field-ignored",
            "alias-absolute",
        ],
    )
    def test_schema_cases(
        self,
        schema: type,
        extra_patterns: tuple[str, ...],
        field_mappings: tuple[dict[object, str], ...],
        expected: frozenset[str],
    ) -> None:
        assert build_secret_paths(schema, extra_patterns=extra_patterns, field_mappings=field_mappings) == expected

    def test_caching(self):
        @dataclass
        class Cfg:
            password: str

        paths1 = build_secret_paths(Cfg)
        paths2 = build_secret_paths(Cfg)
        assert paths1 is paths2

    def test_non_dataclass_returns_empty(self):
        result = build_secret_paths(str)

        assert result == frozenset()

    def test_cache_differs_by_extra_patterns(self):
        @dataclass
        class Cfg2:
            my_field: str

        paths_without = build_secret_paths(Cfg2)
        paths_with = build_secret_paths(Cfg2, extra_patterns=("my_field",))

        assert paths_without == frozenset()
        assert paths_with == frozenset({"my_field"})


class TestIsSecretType:
    @pytest.mark.parametrize(
        ("field_type", "expected"),
        [
            (str, False),
            (SecretStr, True),
            (PaymentCardNumber, True),
            (SecretStr | None, True),
            (Annotated[SecretStr, "meta"], True),
            (Annotated[SecretStr | None, "meta"], True),
        ],
        ids=["plain-str", "secret-str", "payment-card", "optional", "annotated", "annotated-optional"],
    )
    def test_detection(self, field_type: type, expected: bool):
        assert _is_secret_type(field_type) is expected


class TestMatchesSecretPattern:
    @pytest.mark.parametrize(
        ("name", "patterns", "expected"),
        [
            ("DB_PASSWORD", ("password",), True),
            ("my_api_key_v2", ("api_key",), True),
            ("hostname", ("password", "secret"), False),
        ],
        ids=["case-insensitive", "substring", "no-match"],
    )
    def test_matching(self, name: str, patterns: tuple[str, ...], expected: bool):
        assert _matches_secret_pattern(name, patterns) is expected


class TestCanonicalName:
    @pytest.mark.parametrize(
        ("name", "expected"),
        [
            ("secret-key", "secretkey"),
            ("secret_key", "secretkey"),
            ("secretKey", "secretkey"),
            ("SecretKey", "secretkey"),
            ("SECRET_KEY", "secretkey"),
            ("SECRET-KEY", "secretkey"),
            ("db.secret-key", "db.secretkey"),
            ("", ""),
            ("host", "host"),
        ],
        ids=[
            "kebab",
            "snake",
            "lower-camel",
            "upper-camel",
            "upper-snake",
            "upper-kebab",
            "dotted-path",
            "empty",
            "unchanged",
        ],
    )
    def test_canonical_name(self, name: str, expected: str):
        assert canonical_name(name) == expected


class TestCanonicalSecretPaths:
    def test_contents(self):
        paths = frozenset({"db.secret_key", "password"})

        assert canonical_secret_paths(paths) == frozenset({"db.secretkey", "password"})

    def test_caching(self):
        paths = frozenset({"db.secret_key"})

        assert canonical_secret_paths(paths) is canonical_secret_paths(paths)


class TestMatchesSecretName:
    @pytest.mark.parametrize(
        ("name", "expected"),
        [
            ("secret-key", True),
            ("apiToken", True),
            ("AUTH_HEADER", True),
            ("db-url", True),
            ("host", False),
            ("port", False),
            ("timeout", False),
        ],
        ids=["secret-key", "apiToken", "AUTH_HEADER", "db-url", "host", "port", "timeout"],
    )
    def test_matches(self, name: str, expected: bool):
        assert matches_secret_name(name) is expected
