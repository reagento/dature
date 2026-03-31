"""Tests for field groups — all-or-nothing validation during merge."""

from dataclasses import dataclass
from pathlib import Path
from textwrap import dedent

import pytest

from dature import Source, load
from dature.errors import FieldGroupError
from dature.field_path import F


class TestFieldGroupAllChanged:
    def test_all_fields_changed_last_wins(self, tmp_path: Path):
        defaults = tmp_path / "defaults.json"
        defaults.write_text('{"host": "localhost", "port": 3000}')

        overrides = tmp_path / "overrides.json"
        overrides.write_text('{"host": "remote", "port": 9090}')

        @dataclass
        class Config:
            host: str
            port: int

        result = load(
            Source(file=defaults),
            Source(file=overrides),
            dataclass_=Config,
            strategy="last_wins",
            field_groups=((F[Config].host, F[Config].port),),
        )

        assert result.host == "remote"
        assert result.port == 9090

    def test_all_fields_changed_first_wins(self, tmp_path: Path):
        first = tmp_path / "first.json"
        first.write_text('{"host": "first-host", "port": 1000}')

        second = tmp_path / "second.json"
        second.write_text('{"host": "second-host", "port": 2000}')

        @dataclass
        class Config:
            host: str
            port: int

        result = load(
            Source(file=first),
            Source(file=second),
            dataclass_=Config,
            strategy="first_wins",
            field_groups=((F[Config].host, F[Config].port),),
        )

        assert result.host == "first-host"
        assert result.port == 1000


class TestFieldGroupNoneChanged:
    def test_no_fields_changed(self, tmp_path: Path):
        defaults = tmp_path / "defaults.json"
        defaults.write_text('{"host": "localhost", "port": 3000}')

        overrides = tmp_path / "overrides.json"
        overrides.write_text('{"host": "localhost", "port": 3000}')

        @dataclass
        class Config:
            host: str
            port: int

        result = load(
            Source(file=defaults),
            Source(file=overrides),
            dataclass_=Config,
            field_groups=((F[Config].host, F[Config].port),),
        )

        assert result.host == "localhost"
        assert result.port == 3000

    def test_source_missing_all_group_fields(self, tmp_path: Path):
        defaults = tmp_path / "defaults.json"
        defaults.write_text('{"host": "localhost", "port": 3000, "debug": false}')

        overrides = tmp_path / "overrides.json"
        overrides.write_text('{"debug": true}')

        @dataclass
        class Config:
            host: str
            port: int
            debug: bool

        result = load(
            Source(file=defaults),
            Source(file=overrides),
            dataclass_=Config,
            field_groups=((F[Config].host, F[Config].port),),
        )

        assert result.host == "localhost"
        assert result.port == 3000
        assert result.debug is True


class TestFieldGroupPartialChange:
    def test_partial_change_raises(self, tmp_path: Path):
        defaults = tmp_path / "defaults.json"
        defaults.write_text('{"host": "localhost", "port": 3000}')

        overrides = tmp_path / "overrides.json"
        overrides.write_text('{"host": "remote"}')

        defaults_meta = Source(file=defaults)
        overrides_meta = Source(file=overrides)

        @dataclass
        class Config:
            host: str
            port: int

        with pytest.raises(FieldGroupError) as exc_info:
            load(
                defaults_meta,
                overrides_meta,
                dataclass_=Config,
                field_groups=((F[Config].host, F[Config].port),),
            )

        assert str(exc_info.value) == dedent(f"""\
            Config field group errors (1)

              Field group (host, port) partially overridden in source 1
                changed:   host (from source {overrides_meta!r})
                unchanged: port (from source {defaults_meta!r})
            """)

    def test_partial_change_field_present_but_equal(self, tmp_path: Path):
        defaults = tmp_path / "defaults.json"
        defaults.write_text('{"host": "localhost", "port": 3000}')

        overrides = tmp_path / "overrides.json"
        overrides.write_text('{"host": "remote", "port": 3000}')

        defaults_meta = Source(file=defaults)
        overrides_meta = Source(file=overrides)

        @dataclass
        class Config:
            host: str
            port: int

        with pytest.raises(FieldGroupError) as exc_info:
            load(
                defaults_meta,
                overrides_meta,
                dataclass_=Config,
                field_groups=((F[Config].host, F[Config].port),),
            )

        assert str(exc_info.value) == dedent(f"""\
            Config field group errors (1)

              Field group (host, port) partially overridden in source 1
                changed:   host (from source {overrides_meta!r})
                unchanged: port (from source {defaults_meta!r})
            """)

    def test_partial_change_with_first_wins(self, tmp_path: Path):
        defaults = tmp_path / "defaults.json"
        defaults.write_text('{"host": "localhost", "port": 3000}')

        overrides = tmp_path / "overrides.json"
        overrides.write_text('{"host": "remote"}')

        @dataclass
        class Config:
            host: str
            port: int

        with pytest.raises(FieldGroupError):
            load(
                Source(file=defaults),
                Source(file=overrides),
                dataclass_=Config,
                strategy="first_wins",
                field_groups=((F[Config].host, F[Config].port),),
            )

    def test_partial_change_with_raise_on_conflict(self, tmp_path: Path):
        defaults = tmp_path / "defaults.json"
        defaults.write_text('{"host": "localhost", "port": 3000}')

        overrides = tmp_path / "overrides.json"
        overrides.write_text('{"host": "remote"}')

        @dataclass
        class Config:
            host: str
            port: int

        with pytest.raises(FieldGroupError):
            load(
                Source(file=defaults),
                Source(file=overrides),
                dataclass_=Config,
                strategy="raise_on_conflict",
                field_groups=((F[Config].host, F[Config].port),),
            )


class TestFieldGroupAutoExpand:
    def test_auto_expand_nested_dataclass(self, tmp_path: Path):
        defaults = tmp_path / "defaults.json"
        defaults.write_text('{"database": {"host": "localhost", "port": 5432}}')

        overrides = tmp_path / "overrides.json"
        overrides.write_text('{"database": {"host": "remote"}}')

        defaults_meta = Source(file=defaults)
        overrides_meta = Source(file=overrides)

        @dataclass
        class Database:
            host: str
            port: int

        @dataclass
        class Config:
            database: Database

        with pytest.raises(FieldGroupError) as exc_info:
            load(
                defaults_meta,
                overrides_meta,
                dataclass_=Config,
                field_groups=((F[Config].database,),),
            )

        assert str(exc_info.value) == dedent(f"""\
            Config field group errors (1)

              Field group (database.host, database.port) partially overridden in source 1
                changed:   database.host (from source {overrides_meta!r})
                unchanged: database.port (from source {defaults_meta!r})
            """)

    def test_auto_expand_all_changed_ok(self, tmp_path: Path):
        defaults = tmp_path / "defaults.json"
        defaults.write_text('{"database": {"host": "localhost", "port": 5432}}')

        overrides = tmp_path / "overrides.json"
        overrides.write_text('{"database": {"host": "remote", "port": 3306}}')

        @dataclass
        class Database:
            host: str
            port: int

        @dataclass
        class Config:
            database: Database

        result = load(
            Source(file=defaults),
            Source(file=overrides),
            dataclass_=Config,
            field_groups=((F[Config].database,),),
        )

        assert result.database.host == "remote"
        assert result.database.port == 3306


class TestFieldGroupThreeSources:
    def test_three_sources_violation_on_second(self, tmp_path: Path):
        a = tmp_path / "a.json"
        a.write_text('{"host": "a-host", "port": 1000}')

        b = tmp_path / "b.json"
        b.write_text('{"host": "b-host"}')

        c = tmp_path / "c.json"
        c.write_text('{"host": "c-host", "port": 3000}')

        a_meta = Source(file=a)
        b_meta = Source(file=b)
        c_meta = Source(file=c)

        @dataclass
        class Config:
            host: str
            port: int

        with pytest.raises(FieldGroupError) as exc_info:
            load(
                a_meta,
                b_meta,
                c_meta,
                dataclass_=Config,
                field_groups=((F[Config].host, F[Config].port),),
            )

        assert str(exc_info.value) == dedent(f"""\
            Config field group errors (1)

              Field group (host, port) partially overridden in source 1
                changed:   host (from source {b_meta!r})
                unchanged: port (from source {a_meta!r})
            """)

    def test_three_sources_all_ok(self, tmp_path: Path):
        a = tmp_path / "a.json"
        a.write_text('{"host": "a-host", "port": 1000}')

        b = tmp_path / "b.json"
        b.write_text('{"host": "b-host", "port": 2000}')

        c = tmp_path / "c.json"
        c.write_text('{"host": "c-host", "port": 3000}')

        @dataclass
        class Config:
            host: str
            port: int

        result = load(
            Source(file=a),
            Source(file=b),
            Source(file=c),
            dataclass_=Config,
            field_groups=((F[Config].host, F[Config].port),),
        )

        assert result.host == "c-host"
        assert result.port == 3000


class TestFieldGroupMultipleGroups:
    def test_one_ok_one_violated(self, tmp_path: Path):
        defaults = tmp_path / "defaults.json"
        defaults.write_text('{"host": "localhost", "port": 3000, "user": "admin", "password": "secret"}')

        overrides = tmp_path / "overrides.json"
        overrides.write_text('{"host": "remote", "port": 9090, "user": "root"}')

        defaults_meta = Source(file=defaults)
        overrides_meta = Source(file=overrides)

        @dataclass
        class Config:
            host: str
            port: int
            user: str
            password: str

        with pytest.raises(FieldGroupError) as exc_info:
            load(
                defaults_meta,
                overrides_meta,
                dataclass_=Config,
                field_groups=(
                    (F[Config].host, F[Config].port),
                    (F[Config].user, F[Config].password),
                ),
            )

        assert str(exc_info.value) == dedent(f"""\
            Config field group errors (1)

              Field group (user, password) partially overridden in source 1
                changed:   user (from source {overrides_meta!r})
                unchanged: password (from source {defaults_meta!r})
            """)


class TestFieldGroupWithFieldMerges:
    def test_compatible_with_field_merges(self, tmp_path: Path):
        defaults = tmp_path / "defaults.json"
        defaults.write_text('{"host": "localhost", "port": 3000, "tags": ["a"]}')

        overrides = tmp_path / "overrides.json"
        overrides.write_text('{"host": "remote", "port": 9090, "tags": ["b"]}')

        @dataclass
        class Config:
            host: str
            port: int
            tags: list[str]

        result = load(
            Source(file=defaults),
            Source(file=overrides),
            dataclass_=Config,
            field_merges={F[Config].tags: "append"},
            field_groups=((F[Config].host, F[Config].port),),
        )

        assert result.host == "remote"
        assert result.port == 9090
        assert result.tags == ["a", "b"]


class TestFieldGroupDecorator:
    def test_decorator_with_field_groups(self, tmp_path: Path):
        defaults = tmp_path / "defaults.json"
        defaults.write_text('{"host": "localhost", "port": 3000}')

        overrides = tmp_path / "overrides.json"
        overrides.write_text('{"host": "remote", "port": 9090}')

        @load(
            Source(file=defaults),
            Source(file=overrides),
            field_groups=((F["Config"].host, F["Config"].port),),
        )
        @dataclass
        class Config:
            host: str
            port: int

        config = Config()
        assert config.host == "remote"
        assert config.port == 9090

    def test_decorator_partial_change_raises(self, tmp_path: Path):
        defaults = tmp_path / "defaults.json"
        defaults.write_text('{"host": "localhost", "port": 3000}')

        overrides = tmp_path / "overrides.json"
        overrides.write_text('{"host": "remote"}')

        @load(
            Source(file=defaults),
            Source(file=overrides),
            field_groups=((F["Config"].host, F["Config"].port),),
        )
        @dataclass
        class Config:
            host: str
            port: int

        with pytest.raises(FieldGroupError):
            Config()


class TestFieldGroupErrorFormat:
    def test_error_message_format(self, tmp_path: Path):
        defaults = tmp_path / "defaults.json"
        defaults.write_text('{"host": "localhost", "port": 3000, "debug": false}')

        overrides = tmp_path / "overrides.json"
        overrides.write_text('{"host": "remote", "debug": true}')

        defaults_meta = Source(file=defaults)
        overrides_meta = Source(file=overrides)

        @dataclass
        class Config:
            host: str
            port: int
            debug: bool

        with pytest.raises(FieldGroupError) as exc_info:
            load(
                defaults_meta,
                overrides_meta,
                dataclass_=Config,
                field_groups=((F[Config].host, F[Config].port),),
            )

        assert str(exc_info.value) == dedent(f"""\
            Config field group errors (1)

              Field group (host, port) partially overridden in source 1
                changed:   host (from source {overrides_meta!r})
                unchanged: port (from source {defaults_meta!r})
            """)

    def test_multiple_violations_message(self, tmp_path: Path):
        defaults = tmp_path / "defaults.json"
        defaults.write_text('{"host": "localhost", "port": 3000, "user": "admin", "password": "secret"}')

        overrides = tmp_path / "overrides.json"
        overrides.write_text('{"host": "remote", "user": "root"}')

        defaults_meta = Source(file=defaults)
        overrides_meta = Source(file=overrides)

        @dataclass
        class Config:
            host: str
            port: int
            user: str
            password: str

        with pytest.raises(FieldGroupError) as exc_info:
            load(
                defaults_meta,
                overrides_meta,
                dataclass_=Config,
                field_groups=(
                    (F[Config].host, F[Config].port),
                    (F[Config].user, F[Config].password),
                ),
            )

        assert str(exc_info.value) == dedent(f"""\
            Config field group errors (2)

              Field group (host, port) partially overridden in source 1
                changed:   host (from source {overrides_meta!r})
                unchanged: port (from source {defaults_meta!r})

              Field group (user, password) partially overridden in source 1
                changed:   user (from source {overrides_meta!r})
                unchanged: password (from source {defaults_meta!r})
            """)


class TestFieldGroupMixedExpandAndFlat:
    def test_all_changed_ok(self, tmp_path: Path):
        defaults = tmp_path / "defaults.json"
        defaults.write_text(
            '{"database": {"host": "localhost", "port": 5432}, "timeout": 30}',
        )

        overrides = tmp_path / "overrides.json"
        overrides.write_text(
            '{"database": {"host": "remote", "port": 3306}, "timeout": 60}',
        )

        @dataclass
        class Database:
            host: str
            port: int

        @dataclass
        class Config:
            database: Database
            timeout: int

        result = load(
            Source(file=defaults),
            Source(file=overrides),
            dataclass_=Config,
            field_groups=((F[Config].database, F[Config].timeout),),
        )

        assert result.database.host == "remote"
        assert result.database.port == 3306
        assert result.timeout == 60

    def test_none_changed_ok(self, tmp_path: Path):
        defaults = tmp_path / "defaults.json"
        defaults.write_text(
            '{"database": {"host": "localhost", "port": 5432}, "timeout": 30}',
        )

        overrides = tmp_path / "overrides.json"
        overrides.write_text(
            '{"database": {"host": "localhost", "port": 5432}, "timeout": 30}',
        )

        @dataclass
        class Database:
            host: str
            port: int

        @dataclass
        class Config:
            database: Database
            timeout: int

        result = load(
            Source(file=defaults),
            Source(file=overrides),
            dataclass_=Config,
            field_groups=((F[Config].database, F[Config].timeout),),
        )

        assert result.database.host == "localhost"
        assert result.database.port == 5432
        assert result.timeout == 30

    def test_flat_changed_nested_not(self, tmp_path: Path):
        defaults = tmp_path / "defaults.json"
        defaults.write_text(
            '{"database": {"host": "localhost", "port": 5432}, "timeout": 30}',
        )

        overrides = tmp_path / "overrides.json"
        overrides.write_text('{"timeout": 60}')

        defaults_meta = Source(file=defaults)
        overrides_meta = Source(file=overrides)

        @dataclass
        class Database:
            host: str
            port: int

        @dataclass
        class Config:
            database: Database
            timeout: int

        with pytest.raises(FieldGroupError) as exc_info:
            load(
                defaults_meta,
                overrides_meta,
                dataclass_=Config,
                field_groups=((F[Config].database, F[Config].timeout),),
            )

        assert str(exc_info.value) == dedent(f"""\
            Config field group errors (1)

              Field group (database.host, database.port, timeout) partially overridden in source 1
                changed:   timeout (from source {overrides_meta!r})
                unchanged: database.host (from source {defaults_meta!r}), database.port (from source {defaults_meta!r})
            """)

    def test_nested_partial_flat_not(self, tmp_path: Path):
        defaults = tmp_path / "defaults.json"
        defaults.write_text(
            '{"database": {"host": "localhost", "port": 5432}, "timeout": 30}',
        )

        overrides = tmp_path / "overrides.json"
        overrides.write_text('{"database": {"host": "remote"}}')

        defaults_meta = Source(file=defaults)
        overrides_meta = Source(file=overrides)

        @dataclass
        class Database:
            host: str
            port: int

        @dataclass
        class Config:
            database: Database
            timeout: int

        with pytest.raises(FieldGroupError) as exc_info:
            load(
                defaults_meta,
                overrides_meta,
                dataclass_=Config,
                field_groups=((F[Config].database, F[Config].timeout),),
            )

        assert str(exc_info.value) == dedent(f"""\
            Config field group errors (1)

              Field group (database.host, database.port, timeout) partially overridden in source 1
                changed:   database.host (from source {overrides_meta!r})
                unchanged: database.port (from source {defaults_meta!r}), timeout (from source {defaults_meta!r})
            """)

    def test_nested_all_changed_flat_not(self, tmp_path: Path):
        defaults = tmp_path / "defaults.json"
        defaults.write_text(
            '{"database": {"host": "localhost", "port": 5432}, "timeout": 30}',
        )

        overrides = tmp_path / "overrides.json"
        overrides.write_text('{"database": {"host": "remote", "port": 3306}}')

        defaults_meta = Source(file=defaults)
        overrides_meta = Source(file=overrides)
        d = repr(defaults_meta)
        o = repr(overrides_meta)

        @dataclass
        class Database:
            host: str
            port: int

        @dataclass
        class Config:
            database: Database
            timeout: int

        with pytest.raises(FieldGroupError) as exc_info:
            load(
                defaults_meta,
                overrides_meta,
                dataclass_=Config,
                field_groups=((F[Config].database, F[Config].timeout),),
            )

        assert str(exc_info.value) == dedent(f"""\
            Config field group errors (1)

              Field group (database.host, database.port, timeout) partially overridden in source 1
                changed:   database.host (from source {o}), database.port (from source {o})
                unchanged: timeout (from source {d})
            """)


class TestFieldGroupSameFieldNameNested:
    def test_all_changed_ok(self, tmp_path: Path):
        defaults = tmp_path / "defaults.json"
        defaults.write_text(
            '{"user_name": "root-old", "inner": {"user_name": "nested-old"}}',
        )

        overrides = tmp_path / "overrides.json"
        overrides.write_text(
            '{"user_name": "root-new", "inner": {"user_name": "nested-new"}}',
        )

        @dataclass
        class Inner:
            user_name: str

        @dataclass
        class Config:
            user_name: str
            inner: Inner

        result = load(
            Source(file=defaults),
            Source(file=overrides),
            dataclass_=Config,
            field_groups=((F[Config].user_name, F[Config].inner.user_name),),
        )

        assert result.user_name == "root-new"
        assert result.inner.user_name == "nested-new"

    def test_only_root_changed_raises(self, tmp_path: Path):
        defaults = tmp_path / "defaults.json"
        defaults.write_text(
            '{"user_name": "root-old", "inner": {"user_name": "nested-old"}}',
        )

        overrides = tmp_path / "overrides.json"
        overrides.write_text('{"user_name": "root-new"}')

        defaults_meta = Source(file=defaults)
        overrides_meta = Source(file=overrides)

        @dataclass
        class Inner:
            user_name: str

        @dataclass
        class Config:
            user_name: str
            inner: Inner

        with pytest.raises(FieldGroupError) as exc_info:
            load(
                defaults_meta,
                overrides_meta,
                dataclass_=Config,
                field_groups=((F[Config].user_name, F[Config].inner.user_name),),
            )

        assert str(exc_info.value) == dedent(f"""\
            Config field group errors (1)

              Field group (user_name, inner.user_name) partially overridden in source 1
                changed:   user_name (from source {overrides_meta!r})
                unchanged: inner.user_name (from source {defaults_meta!r})
            """)
