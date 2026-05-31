import sys

import pytest

from dature.refs import _RefProxy, ref, template_to_str


class TestRefProxy:
    @pytest.mark.parametrize(
        ("proxy", "expected_parts"),
        [
            (ref.cli, ("cli",)),
            (ref.cli.env, ("cli", "env")),
            (ref.env.db.host, ("env", "db", "host")),
        ],
        ids=["single-level", "two-levels", "three-levels"],
    )
    def test_parts(self, proxy: _RefProxy, expected_parts: tuple[str, ...]) -> None:
        assert isinstance(proxy, _RefProxy)
        assert proxy.parts == expected_parts

    @pytest.mark.parametrize(
        ("proxy", "expected_repr"),
        [
            (ref.cli.env, "ref.cli.env"),
            (ref.env.db.host, "ref.env.db.host"),
        ],
        ids=["two-levels", "three-levels"],
    )
    def test_repr(self, proxy: _RefProxy, expected_repr: str) -> None:
        assert repr(proxy) == expected_repr


class TestRefProxyToCrossRef:
    @pytest.mark.parametrize(
        ("proxy", "expected"),
        [
            (ref.cli.env, "${@cli.env}"),
            (ref.env.db.host, "${@env.db.host}"),
            (ref.vault.secret.token, "${@vault.secret.token}"),
        ],
        ids=["simple", "nested", "deeply-nested"],
    )
    def test_to_cross_ref_no_default(self, proxy: _RefProxy, expected: str) -> None:
        assert proxy.to_cross_ref() == expected

    @pytest.mark.parametrize(
        ("proxy", "default", "expected"),
        [
            (ref.cli.env, "dev", "${@cli.env:-dev}"),
            (ref.env.PORT, "8080", "${@env.PORT:-8080}"),
            (ref.cli.env, "", "${@cli.env:-}"),
        ],
        ids=["simple-default", "port-default", "empty-default"],
    )
    def test_to_cross_ref_with_default(self, proxy: _RefProxy, default: str, expected: str) -> None:
        assert proxy.to_cross_ref(default=default) == expected

    def test_too_few_parts_raises(self) -> None:
        proxy = _RefProxy(("cli",))
        with pytest.raises(ValueError, match=r"at least tag\.key"):
            proxy.to_cross_ref()


class TestTemplateToStr:
    @pytest.mark.skipif(sys.version_info >= (3, 14), reason="requires Python < 3.14")
    def test_import_error_on_old_python(self) -> None:
        with pytest.raises(ImportError, match=r"Python 3\.14"):
            template_to_str("not-a-template")

    def test_type_error_on_non_template(self) -> None:
        if sys.version_info < (3, 14):
            pytest.skip("requires Python 3.14+")
        with pytest.raises(TypeError, match="expected a t-string Template"):
            template_to_str("not-a-template")

    @pytest.mark.skipif(sys.version_info < (3, 14), reason="t-strings require Python 3.14+")
    @pytest.mark.parametrize(
        ("strings", "interps", "expected"),
        [
            (("plain text",), [], "plain text"),
            (("", ""), [(ref.cli.env, "ref.cli.env", "")], "${@cli.env}"),
            (("", ""), [(ref.cli.env, "ref.cli.env", "dev")], "${@cli.env:-dev}"),
            (("prefix-", "-suffix"), [(ref.env.HOST, "ref.env.HOST", "")], "prefix-${@env.HOST}-suffix"),
        ],
        ids=["plain-string", "single-ref", "ref-with-default", "mixed-static-and-ref"],
    )
    def test_template(
        self,
        strings: tuple[str, ...],
        interps: list[tuple[_RefProxy, str, str]],
        expected: str,
    ) -> None:
        from string.templatelib import Interpolation, Template  # type: ignore[import-not-found]  # noqa: PLC0415

        interpolations = tuple(Interpolation(proxy, expr, None, fmt) for proxy, expr, fmt in interps)
        t = Template(strings, interpolations)
        assert template_to_str(t) == expected

    @pytest.mark.skipif(sys.version_info < (3, 14), reason="t-strings require Python 3.14+")
    def test_non_proxy_interpolation_stringified(self) -> None:
        from string.templatelib import Interpolation, Template  # noqa: PLC0415

        interp = Interpolation(42, "42", None, "")
        t = Template(("value=", ""), (interp,))
        assert template_to_str(t) == "value=42"
