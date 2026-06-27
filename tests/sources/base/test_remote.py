from dataclasses import dataclass

import pytest

from dature.sources.base import RemoteSource, clone_source
from dature.type_aliases import JSONValue


@dataclass(kw_only=True, repr=False)
class _FakeRemote(RemoteSource):
    """Fixed-data remote source — no external service, sets ``_loaded_cache`` from ``data``."""

    data: JSONValue = None
    format_name = "_fake_remote"
    location_label = "FAKE"

    def remote_address(self) -> str:
        return "fake://test"

    def _fetch(self) -> JSONValue:
        return self.data


class TestRemoteSourceClone:
    def test_clone_drops_loaded_cache(self):
        # Regression: clone_source used to inherit _loaded_cache via shallow copy, so a
        # clone produced after _load() would return stale data from resolve_location without
        # ever calling _fetch() again.
        src = _FakeRemote(data={"key": "value"})
        src.load_raw()  # populates _loaded_cache

        assert src._loaded_cache is not None

        clone = clone_source(src, {})

        assert clone._loaded_cache is None

    def test_clone_reloads_on_load_raw(self):
        src = _FakeRemote(data={"key": "original"})
        src.load_raw()

        clone = clone_source(src, {"data": {"key": "updated"}})
        result = clone.load_raw()

        assert result.data == {"key": "updated"}
        assert clone._loaded_cache == {"key": "updated"}


class TestRemoteSourceResolveLocation:
    @pytest.mark.parametrize(
        ("prefix", "data", "field_path", "expected"),
        [
            pytest.param(
                None,
                {"db_password": "s3cret"},
                ["db_password"],
                "fake://test: db_password = s3cret",
                id="top_level",
            ),
            # Regression: resolve_location used to look up field_path verbatim against the raw
            # _fetch() data, so a prefixed source rendered only the field key without its value.
            pytest.param(
                "app",
                {"app": {"db_password": "s3cret"}},
                ["db_password"],
                "fake://test: app.db_password = s3cret",
                id="with_prefix",
            ),
            pytest.param(
                None,
                {"other": "x"},
                ["missing"],
                "fake://test: missing",
                id="missing_field_key_only",
            ),
        ],
    )
    def test_resolve_location(self, prefix, data, field_path, expected):
        src = _FakeRemote(prefix=prefix, data=data)
        src.load_raw()
        locations = src.resolve_location(field_path=field_path, file_content=None, nested_conflict=None)
        assert locations[0].line_content == [expected]
