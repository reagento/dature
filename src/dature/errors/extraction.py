import types
from collections.abc import Callable
from dataclasses import replace
from typing import Union, get_args

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

from dature.config import MaskingConfig
from dature.errors.exceptions import (
    ConfigEnvVarExpandError,
    DatureConfigError,
    EnvVarExpandError,
    FieldLoadError,
    MissingEnvVarError,
)
from dature.errors.location import ErrorContext, read_file_content, resolve_source_location
from dature.masking.masking import is_random_string, is_secret_path, mask_value
from dature.sources.protocol import FileSourceProtocol
from dature.type_aliases import JSONValue


def _describe_error(exc: BaseException, *, masking: MaskingConfig, is_secret: bool = False) -> str:
    if isinstance(exc, (ValidationLoadError, ValueLoadError)):
        message = str(exc.msg)
    elif isinstance(exc, TypeLoadError):
        expected = exc.expected_type
        if isinstance(expected, types.UnionType) or getattr(expected, "__origin__", None) is Union:
            names = [arg.__name__ for arg in get_args(expected)]
            expected_name = " | ".join(names)
        else:
            expected_name = expected.__name__
        message = f"Expected {expected_name}, got {type(exc.input_value).__name__}"
    elif isinstance(exc, ExtraFieldsLoadError):
        field_names = ", ".join(sorted(exc.fields))
        message = f"Unknown field(s): {field_names}"
    elif isinstance(exc, BadVariantLoadError):
        message = f"Invalid variant: {exc.input_value!r}"
    else:
        message = str(exc)

    raw_value = str(getattr(exc, "input_value", None))
    if is_secret and raw_value and raw_value in message:
        message = message.replace(raw_value, mask_value(raw_value, masking))
    return message


def _walk_exception(
    exc: BaseException,
    parent_path: list[str],
    result: list[FieldLoadError],
    *,
    masking: MaskingConfig,
    secret_paths: frozenset[str] = frozenset(),
    heuristic_secret_paths: set[str] | None = None,
) -> None:
    trail = list(get_trail(exc))
    current_path = parent_path + [str(elem) for elem in trail]

    if isinstance(exc, LoadExceptionGroup):
        for sub_exc in exc.exceptions:
            _walk_exception(
                sub_exc,
                current_path,
                result,
                secret_paths=secret_paths,
                heuristic_secret_paths=heuristic_secret_paths,
                masking=masking,
            )
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

    is_secret = is_secret_path(current_path, secret_paths=secret_paths, masking=masking)
    input_value = getattr(exc, "input_value", None)
    if (
        masking.masking_mode == "secrets_only"
        and not is_secret
        and isinstance(input_value, str)
        and is_random_string(input_value, masking)
    ):
        is_secret = True
        if heuristic_secret_paths is not None:
            heuristic_secret_paths.add(".".join(current_path))
    if is_secret and input_value is not None:
        input_value = mask_value(str(input_value), masking)

    result.append(
        FieldLoadError(
            field_path=current_path,
            message=_describe_error(exc, is_secret=is_secret, masking=masking),
            input_value=input_value,
        ),
    )


def extract_field_errors(
    exc: BaseException,
    *,
    masking: MaskingConfig,
    secret_paths: frozenset[str] = frozenset(),
) -> list[FieldLoadError]:
    result: list[FieldLoadError] = []
    _walk_exception(exc, [], result, secret_paths=secret_paths, masking=masking)
    return result


def handle_load_errors[T](
    *,
    func: Callable[[], T],
    ctx: ErrorContext,
    loaded_data: "JSONValue | None" = None,
) -> T:
    try:
        return func()
    except EnvVarExpandError as exc:
        if isinstance(ctx.source, FileSourceProtocol):
            file_content = read_file_content(ctx.source.file_path_for_errors(), ctx.source.encoding)
        else:
            file_content = None
        enriched_env: list[MissingEnvVarError] = []
        for e in exc.exceptions:
            if not isinstance(e, MissingEnvVarError):
                continue
            locations = resolve_source_location(e.field_path, ctx, file_content, loaded_data=loaded_data)
            e.location = locations[0] if locations else None
            e.error_display = ctx.error_display
            enriched_env.append(e)
        raise ConfigEnvVarExpandError(ctx.dataclass_name, enriched_env) from exc
    except (AggregateLoadError, LoadError) as exc:
        if isinstance(ctx.source, FileSourceProtocol):
            file_content = read_file_content(ctx.source.file_path_for_errors(), ctx.source.encoding)
        else:
            file_content = None
        heuristic_paths: set[str] = set()
        field_errors: list[FieldLoadError] = []
        _walk_exception(
            exc,
            [],
            field_errors,
            secret_paths=ctx.secret_paths,
            heuristic_secret_paths=heuristic_paths,
            masking=ctx.masking,
        )
        location_ctx = ctx
        if heuristic_paths:
            location_ctx = replace(ctx, secret_paths=ctx.secret_paths | heuristic_paths)
        enriched: list[FieldLoadError] = []
        for fe in field_errors:
            locations = resolve_source_location(
                fe.field_path, location_ctx, file_content, input_value=fe.input_value, loaded_data=loaded_data
            )
            enriched.append(
                FieldLoadError(
                    field_path=fe.field_path,
                    message=fe.message,
                    input_value=fe.input_value,
                    locations=locations,
                    error_display=ctx.error_display,
                ),
            )
        raise DatureConfigError(ctx.dataclass_name, enriched) from None
