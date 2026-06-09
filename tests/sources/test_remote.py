from dataclasses import dataclass

import pytest

from dature.sources.remote import RemoteSource
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
