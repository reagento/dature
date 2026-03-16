from dataclasses import dataclass

from adaptix import Retort
from adaptix.load_error import AggregateLoadError, LoadError

from dature.errors.formatter import extract_field_errors


class TestExtractFieldErrors:
    def test_type_error(self):
        @dataclass
        class Config:
            timeout: int

        r = Retort(strict_coercion=True)
        try:
            r.load({"timeout": "abc"}, Config)
        except (AggregateLoadError, LoadError) as exc:
            errors = extract_field_errors(exc)
            assert len(errors) == 1
            assert errors[0].field_path == ["timeout"]
            assert errors[0].message == "Expected int, got str"

    def test_missing_field(self):
        @dataclass
        class Config:
            timeout: int
            name: str

        r = Retort(strict_coercion=True)
        try:
            r.load({"timeout": 123}, Config)
        except (AggregateLoadError, LoadError) as exc:
            errors = extract_field_errors(exc)
            assert len(errors) == 1
            assert errors[0].field_path == ["name"]
            assert errors[0].message == "Missing required field"

    def test_nested_errors(self):
        @dataclass
        class DB:
            host: str
            port: int

        @dataclass
        class Config:
            timeout: int
            db: DB

        r = Retort(strict_coercion=True)
        try:
            r.load({"timeout": "abc", "db": {"host": "ok", "port": "xyz"}}, Config)
        except (AggregateLoadError, LoadError) as exc:
            errors = extract_field_errors(exc)
            assert len(errors) == 2
            paths = sorted(e.field_path for e in errors)
            assert paths == [["db", "port"], ["timeout"]]

    def test_multiple_missing_fields(self):
        @dataclass
        class Config:
            a: int
            b: str
            c: float

        r = Retort(strict_coercion=True)
        try:
            r.load({}, Config)
        except (AggregateLoadError, LoadError) as exc:
            errors = extract_field_errors(exc)
            assert len(errors) == 3
            paths = sorted([e.field_path[0] for e in errors])
            assert paths == ["a", "b", "c"]
