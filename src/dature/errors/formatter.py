import types
from collections.abc import Callable
from typing import TYPE_CHECKING, Union, get_args

from adaptix.load_error import (
    AggregateLoadError,
    BadVariantLoadError,
    ExtraFieldsLoadError,
    LoadError,
    LoadExceptionGroup,
    NoRequiredFieldsLoadError,
    TypeLoadError,
    ValidationLoadError,
    ValueLoadError,
)
from adaptix.struct_trail import get_trail

from dature.errors.exceptions import (
    DatureConfigError,
    DatureError,
    EnvVarExpandError,
    FieldLoadError,
    MissingEnvVarError,
)
from dature.errors.location import ErrorContext, read_file_content, resolve_source_location
from dature.masking.masking import mask_value

if TYPE_CHECKING:
    from dature.loading.source_loading import SkippedFieldSource


def _describe_error(exc: BaseException, *, is_secret: bool = False) -> str:
    if isinstance(exc, (ValidationLoadError, ValueLoadError)):
        return str(exc.msg)

    if isinstance(exc, TypeLoadError):
        expected = exc.expected_type
        if isinstance(expected, types.UnionType) or getattr(expected, "__origin__", None) is Union:
            names = [arg.__name__ for arg in get_args(expected)]
            expected_name = " | ".join(names)
        else:
            expected_name = expected.__name__
        return f"Expected {expected_name}, got {type(exc.input_value).__name__}"

    if isinstance(exc, ExtraFieldsLoadError):
        field_names = ", ".join(sorted(exc.fields))
        return f"Unknown field(s): {field_names}"

    if isinstance(exc, BadVariantLoadError):
        if is_secret:
            masked = mask_value(str(exc.input_value))
            return f"Invalid variant: {masked!r}"
        return f"Invalid variant: {exc.input_value!r}"

    return str(exc)


def _walk_exception(
    exc: BaseException,
    parent_path: list[str],
    result: list[FieldLoadError],
    *,
    secret_paths: frozenset[str] = frozenset(),
) -> None:
    trail = list(get_trail(exc))
    current_path = parent_path + [str(elem) for elem in trail]

    if isinstance(exc, LoadExceptionGroup):
        for sub_exc in exc.exceptions:
            _walk_exception(sub_exc, current_path, result, secret_paths=secret_paths)
        return

    if isinstance(exc, NoRequiredFieldsLoadError):
        result.extend(
            FieldLoadError(
                field_path=[*current_path, field_name],
                message="Missing required field",
                input_value=None,
            )
            for field_name in sorted(exc.fields)
        )
        return

    is_secret = ".".join(current_path) in secret_paths
    input_value = getattr(exc, "input_value", None)
    if is_secret and input_value is not None:
        input_value = mask_value(str(input_value))

    result.append(
        FieldLoadError(
            field_path=current_path,
            message=_describe_error(exc, is_secret=is_secret),
            input_value=input_value,
        ),
    )


def extract_field_errors(
    exc: BaseException,
    *,
    secret_paths: frozenset[str] = frozenset(),
) -> list[FieldLoadError]:
    result: list[FieldLoadError] = []
    _walk_exception(exc, [], result, secret_paths=secret_paths)
    return result


def handle_load_errors[T](
    *,
    func: Callable[[], T],
    ctx: ErrorContext,
) -> T:
    try:
        return func()
    except EnvVarExpandError as exc:
        missing = [e for e in exc.exceptions if isinstance(e, MissingEnvVarError)]
        raise EnvVarExpandError(missing, dataclass_name=ctx.dataclass_name) from exc
    except (AggregateLoadError, LoadError) as exc:
        file_content = read_file_content(ctx.file_path)
        field_errors = extract_field_errors(exc, secret_paths=ctx.secret_paths)
        enriched: list[FieldLoadError] = []
        for fe in field_errors:
            location = resolve_source_location(fe.field_path, ctx, file_content)
            enriched.append(
                FieldLoadError(
                    field_path=fe.field_path,
                    message=fe.message,
                    input_value=fe.input_value,
                    locations=[location],
                ),
            )
        raise DatureConfigError(ctx.dataclass_name, enriched) from exc


def enrich_skipped_errors(
    err: DatureConfigError,
    skipped_fields: "dict[str, list[SkippedFieldSource]]",
) -> DatureConfigError:
    updated: list[DatureError] = []
    for exc in err.exceptions:
        if not isinstance(exc, FieldLoadError):
            if isinstance(exc, DatureError):
                updated.append(exc)
            continue

        if exc.message != "Missing required field":
            updated.append(exc)
            continue

        field_name = exc.field_path[-1] if exc.field_path else ""
        sources = skipped_fields.get(field_name)
        if sources is None:
            updated.append(exc)
            continue

        source_reprs = ", ".join(repr(s.metadata) for s in sources)
        locations = [resolve_source_location(exc.field_path, s.error_ctx, s.file_content) for s in sources]
        updated.append(
            FieldLoadError(
                field_path=exc.field_path,
                message=f"Missing required field (invalid in: {source_reprs})",
                input_value=exc.input_value,
                locations=locations,
            ),
        )
    return DatureConfigError(err.dataclass_name, updated)
