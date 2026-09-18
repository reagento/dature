"""Tests for strict mode — unknown-key detection after a successful load."""

import logging
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import cast

import pytest

from dature import Dature, EnvFileSource, EnvSource, F, JsonSource, Loader, load
from dature.errors import StrictModeError
from dature.errors.exceptions import UnknownKeyError
from dature.loading.strict.known_keys import known_key_tree


@dataclass
class _RecursiveNode:
    """Module-level (not locally scoped) self-referential schema — a legitimate recursive
    config shape, whose type hints must resolve without lru_cache/get_type_hints recursing
    unboundedly."""

    name: str = ""
    child: "_RecursiveNode | None" = None


@pytest.fixture(autouse=True)
def _no_masking(_no_global_masking: None) -> None:
    # Strict-mode assertions compare literal error text against the file/key content;
    # the default masking mode would redact anything that looks secret-shaped.
    pass


def _write_json(tmp_path: Path, content: str) -> Path:
    config_file = tmp_path / "config.json"
    config_file.write_text(content)
    return config_file


def _field_paths(group: StrictModeError) -> list[list[str]]:
    # ExceptionGroup.exceptions is typed as tuple[DatureError | ExceptionGroup[DatureError], ...]
    # by the stdlib stub — groups can nest arbitrarily in general — but StrictModeError only ever
    # holds flat UnknownKeyError leaves, so narrow once here instead of at every call site.
    return [cast("UnknownKeyError", e).field_path for e in group.exceptions]


@pytest.mark.parametrize("strict", ["off", None], ids=["explicit-off", "default"])
def test_unknown_keys_ignored(tmp_path: Path, strict: str | None):
    config_file = _write_json(tmp_path, '{"host": "localhost", "databse_host": "typo"}')

    @dataclass
    class Config:
        host: str

    kwargs = {} if strict is None else {"strict": strict}
    result = load(JsonSource(file=config_file), schema=Config, **kwargs)

    assert result.host == "localhost"


class TestStrictError:
    def test_unknown_key_at_root(self, tmp_path: Path):
        config_file = _write_json(tmp_path, '{"host": "localhost", "databse_host": "typo"}')

        @dataclass
        class Config:
            host: str

        with pytest.raises(StrictModeError) as exc_info:
            load(JsonSource(file=config_file), schema=Config, strict="error")

        assert str(exc_info.value) == "Config unknown config keys (1)"
        assert _field_paths(exc_info.value) == [["databse_host"]]
        assert str(exc_info.value.exceptions[0]) == (
            f"  [databse_host]  Config value 'databse_host' was unused (from json '{config_file}')\n"
            f'   ├── {{"host": "localhost", "databse_host": "typo"}}\n'
            f"   │                          ^^^^^^^^^^^^\n"
            f"   └── FILE '{config_file}', line 1"
        )  # fmt: skip

    def test_unknown_key_at_nested_level(self, tmp_path: Path):
        config_file = _write_json(tmp_path, '{"db": {"host": "localhost", "typo_field": 1}}')

        @dataclass
        class Db:
            host: str

        @dataclass
        class Config:
            db: Db

        with pytest.raises(StrictModeError) as exc_info:
            load(JsonSource(file=config_file), schema=Config, strict="error")

        assert str(exc_info.value) == "Config unknown config keys (1)"
        assert _field_paths(exc_info.value) == [["db", "typo_field"]]
        assert str(exc_info.value.exceptions[0]) == (
            f"  [db.typo_field]  Config value 'db.typo_field' was unused (from json '{config_file}')\n"
            f'   ├── {{"db": {{"host": "localhost", "typo_field": 1}}}}\n'
            f"   │                                 ^^^^^^^^^^\n"
            f"   └── FILE '{config_file}', line 1"
        )  # fmt: skip

    def test_error_text_has_file_and_line(self, tmp_path: Path):
        config_file = _write_json(tmp_path, '{\n  "host": "localhost",\n  "typo": 1\n}')

        @dataclass
        class Config:
            host: str

        with pytest.raises(StrictModeError) as exc_info:
            load(JsonSource(file=config_file), schema=Config, strict="error")

        assert str(exc_info.value) == "Config unknown config keys (1)"
        assert _field_paths(exc_info.value) == [["typo"]]
        assert str(exc_info.value.exceptions[0]) == (
            f"  [typo]  Config value 'typo' was unused (from json '{config_file}')\n"
            f'   ├── "typo": 1\n'
            f"   │    ^^^^\n"
            f"   └── FILE '{config_file}', line 3"
        )  # fmt: skip

    def test_multi_source_only_checks_loaded_sources(self, tmp_path: Path):
        broken = tmp_path / "broken.json"
        broken.write_text("not valid json")

        good = tmp_path / "good.json"
        good.write_text('{"host": "localhost"}')

        @dataclass
        class Config:
            host: str

        result = load(
            JsonSource(file=broken, skip_if_broken=True),
            JsonSource(file=good),
            schema=Config,
            strict="error",
        )

        assert result.host == "localhost"

    def test_multi_source_both_contribute_unknown_keys(self, tmp_path: Path):
        first = tmp_path / "first.json"
        first.write_text('{"host": "localhost", "typo_one": 1}')

        second = tmp_path / "second.json"
        second.write_text('{"port": 8080, "typo_two": 2}')

        @dataclass
        class Config:
            host: str
            port: int

        with pytest.raises(StrictModeError) as exc_info:
            load(JsonSource(file=first), JsonSource(file=second), schema=Config, strict="error")

        assert str(exc_info.value) == "Config unknown config keys (2)"
        assert _field_paths(exc_info.value) == [["typo_one"], ["typo_two"]]
        assert [str(e) for e in exc_info.value.exceptions] == [
            (
                f"  [typo_one]  Config value 'typo_one' was unused (from json '{first}')\n"
                f'   ├── {{"host": "localhost", "typo_one": 1}}\n'
                f"   │                          ^^^^^^^^\n"
                f"   └── FILE '{first}', line 1"
            ),
            (
                f"  [typo_two]  Config value 'typo_two' was unused (from json '{second}')\n"
                f'   ├── {{"port": 8080, "typo_two": 2}}\n'
                f"   │                   ^^^^^^^^\n"
                f"   └── FILE '{second}', line 1"
            ),
        ]  # fmt: skip


class TestStrictWarn:
    def test_warns_and_loads_successfully(self, tmp_path: Path, caplog: pytest.LogCaptureFixture):
        config_file = _write_json(tmp_path, '{"host": "localhost", "typo": 1}')

        @dataclass
        class Config:
            host: str

        with caplog.at_level(logging.WARNING, logger="dature"):
            result = load(JsonSource(file=config_file), schema=Config, strict="warn")

        assert result.host == "localhost"
        warning_messages = [r.getMessage() for r in caplog.records if r.levelno >= logging.WARNING]
        assert warning_messages == [
            (
                f"[Config]   [typo]  Config value 'typo' was unused (from json '{config_file}')\n"
                f'   ├── {{"host": "localhost", "typo": 1}}\n'
                f"   │                          ^^^^\n"
                f"   └── FILE '{config_file}', line 1"
            ),
        ]  # fmt: skip

    def test_cached_reload_does_not_re_warn(self, tmp_path: Path, caplog: pytest.LogCaptureFixture):
        # The strict check runs during the actual load, not on a cache hit — a warm
        # Loader that keeps returning cached data only warns once, on the load that
        # populated the cache. Documented in docs/advanced/strict-mode.md so this stays
        # a deliberate tradeoff (cheap hot path) rather than a silently-changing default.
        config_file = _write_json(tmp_path, '{"host": "localhost", "typo": 1}')

        @dataclass
        class Config:
            host: str

        loader = Loader(JsonSource(file=config_file), schema=Config, strict="warn", cache=True)

        with caplog.at_level(logging.WARNING, logger="dature"):
            loader.load()
            loader.load()

        warning_messages = [r.getMessage() for r in caplog.records if r.levelno >= logging.WARNING]
        assert len(warning_messages) == 1


class TestStrictNamingVariants:
    @pytest.mark.parametrize(
        ("raw_key", "name_style"),
        [
            ("db_host", "lower_snake"),
            ("dbHost", "lower_camel"),
            ("DB-HOST", "upper_kebab"),
            ("DbHost", "upper_camel"),
            ("DB_HOST", "upper_snake"),
        ],
        ids=["lower_snake", "lower_camel", "upper_kebab", "upper_camel", "upper_snake"],
    )
    def test_naming_variant_not_reported(self, tmp_path: Path, raw_key: str, name_style: str):
        # The known-key tree stores canonical_name(f.name), so strict mode accepts *any*
        # NameStyle variant regardless of the source's own name_style — what actually
        # depends on name_style here is whether the *loader* resolves raw_key to db_host
        # at all (a mismatched name_style would leave db_host unset, not raise a strict
        # error), which is what this test's parametrization exercises.
        config_file = _write_json(tmp_path, f'{{"{raw_key}": "localhost"}}')

        @dataclass
        class Config:
            db_host: str

        result = load(JsonSource(file=config_file, name_style=name_style), schema=Config, strict="error")

        assert result.db_host == "localhost"


class TestStrictAliases:
    def test_field_mapping_alias_not_reported(self, tmp_path: Path):
        config_file = _write_json(tmp_path, '{"fullName": "Ann"}')

        @dataclass
        class Config:
            name: str

        result = load(
            JsonSource(file=config_file, field_mapping={F[Config].name: "fullName"}),
            schema=Config,
            strict="error",
        )

        assert result.name == "Ann"

    def test_cross_level_alias_not_reported(self, tmp_path: Path):
        # The cross-level alias moves the root-level "db_host" key into "db.host" — the
        # destination dict must already exist in the raw data for that move to happen.
        config_file = _write_json(tmp_path, '{"db": {}, "db_host": "localhost"}')

        @dataclass
        class Db:
            host: str

        @dataclass
        class Config:
            db: Db

        result = load(
            JsonSource(file=config_file, field_mapping={F[Config].db.host: "db_host"}),
            schema=Config,
            strict="error",
        )

        assert result.db.host == "localhost"


class TestStrictOpaqueContainers:
    @pytest.mark.parametrize(
        ("raw_json", "field_type", "expected"),
        [
            pytest.param(
                '{"extra": {"anything": "goes", "here": 1}}',
                dict[str, object],
                {"anything": "goes", "here": 1},
                id="dict-str-any",
            ),
            pytest.param('{"extra": ["a", "b", "c"]}', list[str], ["a", "b", "c"], id="list-str"),
        ],
    )
    def test_opaque_field_contents_not_scanned(
        self,
        tmp_path: Path,
        raw_json: str,
        field_type: type,
        expected: object,
    ):
        config_file = _write_json(tmp_path, raw_json)

        @dataclass
        class Config:
            extra: field_type  # type: ignore[valid-type]

        result = load(JsonSource(file=config_file), schema=Config, strict="error")

        assert result.extra == expected


class TestStrictNestedDataclassContainers:
    @pytest.mark.parametrize(
        "make_items_type",
        [lambda db: list[db], lambda db: tuple[db, ...]],  # type: ignore[valid-type]
        ids=["list", "tuple"],
    )
    def test_container_of_dataclass_typo_in_element_reports_index_path(
        self, tmp_path: Path, make_items_type: Callable[[type], type]
    ):
        config_file = _write_json(tmp_path, '{"items": [{"host": "a"}, {"host": "b", "hostt": "typo"}]}')

        @dataclass
        class Db:
            host: str

        items_type = make_items_type(Db)

        @dataclass
        class Config:
            items: items_type  # type: ignore[valid-type]

        with pytest.raises(StrictModeError) as exc_info:
            load(JsonSource(file=config_file), schema=Config, strict="error")

        assert str(exc_info.value) == "Config unknown config keys (1)"
        assert _field_paths(exc_info.value) == [["items", "1", "hostt"]]
        assert str(exc_info.value.exceptions[0]) == (
            f"  [items.1.hostt]  Config value 'items.1.hostt' was unused (from json '{config_file}')\n"
            f'   ├── {{"items": [{{"host": "a"}}, {{"host": "b", "hostt": "typo"}}]}}\n'
            f"   │                                            ^^^^^\n"
            f"   └── FILE '{config_file}', line 1"
        )  # fmt: skip

    def test_dict_of_dataclass_top_level_keys_arbitrary_nested_typo_reported(self, tmp_path: Path):
        config_file = _write_json(
            tmp_path,
            '{"envs": {"prod": {"host": "a"}, "staging": {"host": "b", "hostt": "typo"}}}',
        )

        @dataclass
        class Db:
            host: str

        @dataclass
        class Config:
            envs: dict[str, Db]

        with pytest.raises(StrictModeError) as exc_info:
            load(JsonSource(file=config_file), schema=Config, strict="error")

        assert str(exc_info.value) == "Config unknown config keys (1)"
        assert _field_paths(exc_info.value) == [["envs", "staging", "hostt"]]
        assert str(exc_info.value.exceptions[0]) == (
            f"  [envs.staging.hostt]  Config value 'envs.staging.hostt' was unused (from json '{config_file}')\n"
            f'   ├── {{"envs": {{"prod": {{"host": "a"}}, "staging": {{"host": "b", "hostt": "typo"}}}}}}\n'
            f"   │                                                              ^^^^^\n"
            f"   └── FILE '{config_file}', line 1"
        )  # fmt: skip

    def test_union_dataclass_field_typo_reported_at_field_path(self, tmp_path: Path):
        config_file = _write_json(tmp_path, '{"db": {"host": "a", "hostt": "typo"}}')

        @dataclass
        class Db:
            host: str

        @dataclass
        class Config:
            db: Db | None

        with pytest.raises(StrictModeError) as exc_info:
            load(JsonSource(file=config_file), schema=Config, strict="error")

        assert str(exc_info.value) == "Config unknown config keys (1)"
        assert _field_paths(exc_info.value) == [["db", "hostt"]]
        assert str(exc_info.value.exceptions[0]) == (
            f"  [db.hostt]  Config value 'db.hostt' was unused (from json '{config_file}')\n"
            f'   ├── {{"db": {{"host": "a", "hostt": "typo"}}}}\n'
            f"   │                         ^^^^^\n"
            f"   └── FILE '{config_file}', line 1"
        )  # fmt: skip


class TestStrictEnvSourcePrefixWarning:
    def test_no_prefix_env_source_warns(self, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture):
        monkeypatch.setenv("HOST", "localhost")

        @dataclass
        class Config:
            host: str

        with caplog.at_level(logging.WARNING, logger="dature"):
            result = load(EnvSource(), schema=Config, strict="warn")

        assert result.host == "localhost"
        # on_prepared() runs before key scanning, so this warning is always first —
        # scanning itself may add more (real process env vars beyond HOST), which this
        # test isn't about.
        warning_messages = [r.getMessage() for r in caplog.records if r.levelno >= logging.WARNING]
        assert warning_messages[0] == (
            "env has no prefix — strict mode treats the whole process environment as "
            "candidate keys. Set prefix=... and use your own prefixed variables instead."
        )

    def test_prefixed_env_source_does_not_warn(self, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture):
        monkeypatch.setenv("APP_HOST", "localhost")

        @dataclass
        class Config:
            host: str

        with caplog.at_level(logging.WARNING, logger="dature"):
            result = load(EnvSource(prefix="APP_"), schema=Config, strict="warn")

        assert result.host == "localhost"
        warning_messages = [r.getMessage() for r in caplog.records if r.levelno >= logging.WARNING]
        assert warning_messages == []

    def test_env_file_source_never_warns_about_prefix(self, tmp_path: Path, caplog: pytest.LogCaptureFixture):
        env_file = tmp_path / ".env"
        env_file.write_text("HOST=localhost\n")

        @dataclass
        class Config:
            host: str

        with caplog.at_level(logging.WARNING, logger="dature"):
            result = load(EnvFileSource(file=env_file), schema=Config, strict="warn")

        assert result.host == "localhost"
        warning_messages = [r.getMessage() for r in caplog.records if r.levelno >= logging.WARNING]
        assert warning_messages == []

    def test_no_prefix_env_source_does_not_warn_when_strict_off(
        self, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
    ):
        monkeypatch.setenv("HOST", "localhost")

        @dataclass
        class Config:
            host: str

        with caplog.at_level(logging.WARNING, logger="dature"):
            result = load(EnvSource(), schema=Config, strict="off")

        assert result.host == "localhost"
        warning_messages = [r.getMessage() for r in caplog.records if r.levelno >= logging.WARNING]
        assert warning_messages == []

    def test_non_env_source_never_warns_about_prefix(self, tmp_path: Path, caplog: pytest.LogCaptureFixture):
        # EnvFileSource opts out of EnvSource's ambient-environment warning by overriding
        # on_prepared back to Source's no-op — a .env file is a document the caller
        # authored, not the ambient environment. strict="error" here (vs "warn" above)
        # covers the opt-out under the stricter mode too.
        env_file = tmp_path / ".env"
        env_file.write_text("HOST=localhost\n")

        @dataclass
        class Config:
            host: str

        with caplog.at_level(logging.WARNING, logger="dature"):
            result = load(EnvFileSource(file=env_file), schema=Config, strict="error")

        assert result.host == "localhost"
        warning_messages = [r.getMessage() for r in caplog.records if r.levelno >= logging.WARNING]
        assert warning_messages == []


class TestStrictPerSourceOverride:
    def test_source_level_error_overrides_disabled_load_level(self, tmp_path: Path):
        config_file = _write_json(tmp_path, '{"host": "localhost", "typo": 1}')

        @dataclass
        class Config:
            host: str

        with pytest.raises(StrictModeError):
            load(JsonSource(file=config_file, strict="error"), schema=Config, strict="off")

    def test_source_level_off_overrides_enabled_load_level(self, tmp_path: Path):
        config_file = _write_json(tmp_path, '{"host": "localhost", "typo": 1}')

        @dataclass
        class Config:
            host: str

        result = load(JsonSource(file=config_file, strict="off"), schema=Config, strict="error")

        assert result.host == "localhost"

    def test_only_offending_source_reported_when_others_are_off(self, tmp_path: Path):
        strict_file = tmp_path / "strict.json"
        strict_file.write_text('{"host": "localhost", "typo_one": 1}')

        lenient_file = tmp_path / "lenient.json"
        lenient_file.write_text('{"port": 8080, "typo_two": 2}')

        @dataclass
        class Config:
            host: str
            port: int

        with pytest.raises(StrictModeError) as exc_info:
            load(
                JsonSource(file=strict_file, strict="error"),
                JsonSource(file=lenient_file, strict="off"),
                schema=Config,
            )

        assert str(exc_info.value) == "Config unknown config keys (1)"
        assert _field_paths(exc_info.value) == [["typo_one"]]


class TestStrictTruncation:
    def test_max_errors_truncates_unknown_key_blocks(self, tmp_path: Path):
        config_file = _write_json(
            tmp_path,
            '{"host": "localhost", "typo_a": 1, "typo_b": 2, "typo_c": 3, "typo_d": 4}',
        )

        @dataclass
        class Config:
            host: str

        conf = Dature(error_display={"max_errors": 2})

        with pytest.raises(StrictModeError) as exc_info:
            conf.load(JsonSource(file=config_file), schema=Config, strict="error")

        assert str(exc_info.value) == "Config unknown config keys (2)"
        assert _field_paths(exc_info.value) == [["typo_a"], ["typo_b"]]
        assert exc_info.value.__notes__ == ["... and 2 more unknown config keys (4 total)"]

    def test_note_survives_subgroup(self, tmp_path: Path):
        """add_note()'s remainder note must still be present after BaseExceptionGroup.subgroup()
        / except* splits the group — this is why the remainder isn't tracked as a plain field."""
        config_file = _write_json(
            tmp_path,
            '{"host": "localhost", "typo_a": 1, "typo_b": 2, "typo_c": 3}',
        )

        @dataclass
        class Config:
            host: str

        conf = Dature(error_display={"max_errors": 1})

        with pytest.raises(StrictModeError) as exc_info:
            conf.load(JsonSource(file=config_file), schema=Config, strict="error")

        notes = ["... and 2 more unknown config keys (3 total)"]
        assert exc_info.value.__notes__ == notes
        subgroup = exc_info.value.subgroup(UnknownKeyError)
        assert subgroup is not None
        assert subgroup.__notes__ == notes


class TestStrictRecursiveSchema:
    def test_deep_unknown_key_reported_without_recursion_error(self, tmp_path: Path):
        config_file = _write_json(
            tmp_path,
            '{"name": "a", "child": {"name": "b", "child": {"name": "c", "typo": 1}}}',
        )

        with pytest.raises(StrictModeError) as exc_info:
            load(JsonSource(file=config_file), schema=_RecursiveNode, strict="error")

        assert _field_paths(exc_info.value) == [["child", "child", "typo"]]


class TestStrictUnresolvableHints:
    def test_locally_scoped_forward_ref_warns_but_own_keys_still_known(self, caplog: pytest.LogCaptureFixture):
        # A dataclass declared inside a function, referring to itself by name in a string
        # annotation: get_type_hints() can't resolve "_Local" because it isn't a module-level
        # global — a real, supported pattern (adaptix loads it fine), not a schema bug.
        # Exercised directly against known_key_tree (rather than through load()) because
        # that's the layer whose warn-and-continue behavior this covers; the full loader
        # pipeline resolves type hints of its own accord for unrelated reasons (validators).
        def _make_schema() -> type:
            @dataclass
            class _Local:
                host: str
                child: "_Local | None" = None

            return _Local

        schema = _make_schema()

        with caplog.at_level(logging.WARNING, logger="dature"):
            tree = known_key_tree(schema)

        assert tree.keys == frozenset({"host", "child"})
        assert tree.children == {}
        warning_messages = [r.getMessage() for r in caplog.records if r.levelno >= logging.WARNING]
        assert warning_messages == [
            (
                "strict mode: cannot resolve type hints of "
                "TestStrictUnresolvableHints.test_locally_scoped_forward_ref_warns_but_own_keys_still_known"
                ".<locals>._make_schema.<locals>._Local (NameError: name '_Local' is not defined) — its "
                "own keys are still checked, but nested keys under it are not. Ensure forward references "
                "are importable at module level."
            )
        ]


class TestStrictDatureDefault:
    def test_dature_instance_sets_default_strict_mode(self, tmp_path: Path):
        config_file = _write_json(tmp_path, '{"host": "localhost", "typo": 1}')

        @dataclass
        class Config:
            host: str

        conf = Dature(loading={"strict": "error"})

        with pytest.raises(StrictModeError):
            conf.load(JsonSource(file=config_file), schema=Config)
