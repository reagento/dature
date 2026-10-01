from dataclasses import dataclass

import pytest

from dature.sources.base import RemoteSource, clone_source
from dature.type_aliases import ExpandEnvVarsMode, JSONValue


@dataclass(kw_only=True, repr=False)
class _FakeRemote(RemoteSource):
    """Fixed-data remote source — no external service."""

    data: JSONValue = None
    expand_env_vars: ExpandEnvVarsMode | None = "default"
    format_name: str = "_fake_remote"
    location_label: str = "FAKE"

    def remote_address(self) -> str:
        return "fake://test"

    def _fetch(self) -> JSONValue:
        return self.data


class TestRemoteSourceClone:
    def test_clone_reloads_on_load_raw(self):
        src = _FakeRemote(data={"key": "original"})
        src.load_raw()

        clone = clone_source(src, {"data": {"key": "updated"}})
        result = clone.load_raw()

        assert result.data == {"key": "updated"}
        assert result.loaded_data == {"key": "updated"}


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
            # Regression: json.dumps() raises TypeError on bytes (e.g. ConsulSource with
            # decode="raw"), which used to crash error rendering instead of showing the value.
            pytest.param(
                None,
                {"secret": b"s3cret"},
                ["secret"],
                "fake://test: secret = \"b's3cret'\"",
                id="bytes_value",
            ),
        ],
    )
    def test_resolve_location(self, prefix, data, field_path, expected):
        src = _FakeRemote(prefix=prefix, data=data)
        loaded_data = src.load_raw().loaded_data
        locations = src.resolve_location(field_path=field_path, nested_conflict=None, loaded_data=loaded_data)
        assert locations[0].line_content == [expected]

    def test_resolve_location_without_loaded_data(self):
        # When loaded_data is None (data never loaded or not available), renders key only.
        src = _FakeRemote(data={"db_password": "s3cret"})
        locations = src.resolve_location(field_path=["db_password"], nested_conflict=None, loaded_data=None)
        assert locations[0].line_content == ["fake://test: db_password"]


class TestRemoteSourceSharedRead:
    """``shared_read`` applied to a remote fetch — a clone made via ``.replace()`` still
    returns the first, shared fetch instead of hitting ``_fetch()`` again."""

    def test_shares_fetch_across_prefixed_clones(self):
        base = _FakeRemote(
            data={"module1": {"x": 1}, "module2": {"x": 2}},
            shared_read=True,
        )

        clone1 = base.replace(prefix="module1")
        result1 = clone1.load_raw()
        base.data = {"module1": {"x": 999}, "module2": {"x": 999}}
        clone2 = base.replace(prefix="module2")
        result2 = clone2.load_raw()

        assert clone1._read_slot is clone2._read_slot
        assert result1.data == {"x": 1}
        assert result2.data == {"x": 2}  # not 999 — same cached fetch as result1
