"""Unit tests for the When condition DSL (src/dature/conditions.py)."""

import pytest

from dature import When
from dature.conditions import AndCondition, Match, NotCondition, OrCondition
from dature.loading.cross_source import evaluate_when_eager, evaluate_when_lazy
from dature.sources.env_ import EnvSource


class TestWhenEntryPoint:
    def test_eq_returns_match(self) -> None:
        c = When("${APP_ENV}") == "prod"

        assert isinstance(c, Match)
        assert c.template == "${APP_ENV}"
        assert c.expected == ("prod",)

    def test_ne_returns_not_match(self) -> None:
        c = When("${APP_ENV}") != "prod"

        assert isinstance(c, NotCondition)
        assert isinstance(c.inner, Match)
        assert c.inner.expected == ("prod",)

    def test_in_returns_match_with_multiple(self) -> None:
        c = When("${APP_ENV}").in_("dev", "local")

        assert isinstance(c, Match)
        assert c.expected == ("dev", "local")

    def test_not_in_returns_not_condition(self) -> None:
        c = When("${APP_ENV}").not_in("prod")

        assert isinstance(c, NotCondition)
        assert isinstance(c.inner, Match)
        assert c.inner.expected == ("prod",)

    def test_and_operator(self) -> None:
        c = (When("${A}") == "1") & (When("${B}") == "2")

        assert isinstance(c, AndCondition)

    def test_or_operator(self) -> None:
        c = (When("${A}") == "1") | (When("${A}") == "2")

        assert isinstance(c, OrCondition)

    def test_invert_operator(self) -> None:
        c = ~(When("${APP_ENV}") == "prod")

        assert isinstance(c, NotCondition)

    def test_nested_and_or(self) -> None:
        c = ((When("${A}") == "1") & (When("${B}") == "2")) | (When("${C}") == "3")

        assert isinstance(c, OrCondition)
        assert isinstance(c.left, AndCondition)

    @pytest.mark.parametrize(
        ("call", "match"),
        [
            (lambda: When("${A}") == When("${B}"), "When-DSL object"),
            (lambda: When("${A}") != When("${B}"), "When-DSL object"),
            (lambda: When("${A}").in_(When("${B}")), "When-DSL object"),
            (lambda: When("${A}").in_(), "at least one value"),
            (lambda: When("${A}") == 42, "expects a str"),
            (lambda: When(42), "expects a str template"),
        ],
        ids=["eq-dsl", "ne-dsl", "in-dsl", "in-empty", "eq-non-str", "template-non-str"],
    )
    def test_construction_errors(self, call, match: str) -> None:
        with pytest.raises(TypeError, match=match):
            call()


class TestRefTags:
    @pytest.mark.parametrize(
        ("condition", "expected_tags", "has_cross"),
        [
            (When("${APP_ENV}") == "prod", set(), False),
            (When("${@cfg.env}") == "prod", {"cfg"}, True),
            (
                (When("${APP_ENV}") == "prod") & (When("${@cfg.env}") == "prod"),
                {"cfg"},
                True,
            ),
            (
                (When("${APP_ENV}") == "dev") | (When("${@cfg.region}") == "eu"),
                {"cfg"},
                True,
            ),
            (~(When("${@cfg.env}") == "prod"), {"cfg"}, True),
            ((When("${@a.x}") == "1") & (When("${@b.y}") == "2"), {"a", "b"}, True),
        ],
        ids=["no-refs", "single-ref", "and-with-ref", "or-with-ref", "not-with-ref", "two-refs"],
    )
    def test_ref_tags(self, condition, expected_tags: set[str], has_cross: bool) -> None:
        assert condition.ref_tags() == expected_tags
        assert condition.has_cross_refs() is has_cross


class TestEvaluate:
    @pytest.mark.parametrize(
        ("env", "condition", "expected"),
        [
            ({"APP_ENV": "prod"}, When("${APP_ENV}") == "prod", True),
            ({"APP_ENV": "dev"}, When("${APP_ENV}") == "prod", False),
            ({"APP_ENV": "dev"}, When("${APP_ENV}") != "prod", True),
            ({"APP_ENV": "prod"}, When("${APP_ENV}") != "prod", False),
            ({"APP_ENV": "staging"}, When("${APP_ENV}").in_("prod", "staging"), True),
            ({"APP_ENV": "dev"}, When("${APP_ENV}").in_("prod", "staging"), False),
            ({"APP_ENV": "dev"}, When("${APP_ENV}").not_in("prod"), True),
            ({"APP_ENV": "prod"}, When("${APP_ENV}").not_in("prod"), False),
            ({"A": "1", "B": "2"}, (When("${A}") == "1") & (When("${B}") == "2"), True),
            ({"A": "1", "B": "x"}, (When("${A}") == "1") & (When("${B}") == "2"), False),
            (
                {"APP_ENV": "prod"},
                (When("${APP_ENV}") == "prod") | (When("${APP_ENV}") == "staging"),
                True,
            ),
            (
                {"APP_ENV": "dev"},
                (When("${APP_ENV}") == "prod") | (When("${APP_ENV}") == "staging"),
                False,
            ),
            ({"APP_ENV": "dev"}, ~(When("${APP_ENV}") == "prod"), True),
            ({"APP_ENV": "prod"}, ~(When("${APP_ENV}") == "prod"), False),
        ],
        ids=[
            "eq-true",
            "eq-false",
            "ne-true",
            "ne-false",
            "in-true",
            "in-false",
            "not_in-true",
            "not_in-false",
            "and-true",
            "and-false",
            "or-true",
            "or-false",
            "not-true",
            "not-false",
        ],
    )
    def test_eager_evaluate(
        self, monkeypatch: pytest.MonkeyPatch, env: dict[str, str], condition, expected: bool
    ) -> None:
        for k, v in env.items():
            monkeypatch.setenv(k, v)
        assert evaluate_when_eager(condition) is expected

    @pytest.mark.parametrize(
        ("context", "condition", "expected"),
        [
            ({"cfg": {"env": "prod"}}, When("${@cfg.env}") == "prod", True),
            ({"cfg": {"env": "dev"}}, When("${@cfg.env}") == "prod", False),
            (
                {"cfg": {"region": "eu"}},
                (When("${@cfg.region}") == "eu") | (When("${@cfg.region}") == "us"),
                True,
            ),
            ({"cfg": {"env": "dev"}}, ~(When("${@cfg.env}") == "prod"), True),
        ],
        ids=["cross-ref-true", "cross-ref-false", "or-cross-ref", "not-cross-ref"],
    )
    def test_lazy_evaluate(self, context: dict[str, dict[str, str]], condition, expected: bool) -> None:
        assert evaluate_when_lazy(condition, context) is expected


class TestDictRejection:
    def test_dict_when_raises_type_error(self) -> None:
        with pytest.raises(TypeError, match="When\\(\\)"):
            EnvSource(when={"${APP_ENV}": "prod"})
