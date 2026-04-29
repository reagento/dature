"""Text predicates: ``V.matches(pattern)``."""

import re
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, final

from dature.errors.exceptions import ValidatorTypeError
from dature.validators.predicate import Predicate
from dature.validators.type_compat import format_type, is_str_type


@final
@dataclass(frozen=True, slots=True)
class MatchesPredicate(Predicate):
    pattern: str
    error_message: str | None = field(default=None, kw_only=True)

    def check_type(self, field_type: Any, *, field_path: list[str]) -> None:  # noqa: ANN401
        if not is_str_type(field_type):
            path = ".".join(field_path) or "<root>"
            msg = (
                f"V.matches(...) cannot be applied to field '{path}' "
                f"(type {format_type(field_type)}) — field must be str"
            )
            raise ValidatorTypeError(field_path=field_path, message=msg)

    def get_validator_func(self) -> Callable[[Any], bool]:
        compiled = re.compile(self.pattern)
        return lambda v: bool(compiled.match(v))

    def get_error_message(self) -> str:
        if self.error_message is not None:
            return self.error_message
        return f"Value must match pattern '{self.pattern}'"
