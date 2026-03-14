from dature.config import config
from dature.load_report import FieldOrigin, SourceEntry
from dature.types import JSONValue

try:
    from random_string_detector import RandomStringDetector  # type: ignore[import-untyped]

    _heuristic_detector: RandomStringDetector | None = RandomStringDetector(allow_numbers=True)
except ImportError:
    _heuristic_detector = None


def mask_value(value: str) -> str:
    cfg = config.masking
    full_mask = cfg.mask_char * cfg.fixed_mask_length
    if len(value) < cfg.min_length_for_partial_mask:
        return full_mask
    return value[: cfg.min_visible_chars] + full_mask + value[-cfg.min_visible_chars :]


def mask_json_value(
    data: JSONValue,
    *,
    secret_paths: frozenset[str],
    _prefix: str = "",
) -> JSONValue:
    if isinstance(data, dict):
        masked: dict[str, JSONValue] = {}
        for key, value in data.items():
            if _prefix:
                child_path = f"{_prefix}.{key}"
            else:
                child_path = key

            if child_path in secret_paths:
                if isinstance(value, str):
                    masked[key] = mask_value(value)
                elif isinstance(value, dict):
                    masked[key] = mask_json_value(value, secret_paths=secret_paths, _prefix=child_path)
                else:
                    masked[key] = mask_value(str(value))
            elif isinstance(value, (dict, list)):
                masked[key] = mask_json_value(value, secret_paths=secret_paths, _prefix=child_path)
            elif isinstance(value, str) and is_random_string(value):
                masked[key] = mask_value(value)
            else:
                masked[key] = value
        return masked

    if isinstance(data, list):
        return [mask_json_value(item, secret_paths=secret_paths, _prefix=_prefix) for item in data]

    return data


def mask_env_line(line: str) -> str:
    for sep in ("=", ":"):
        if sep in line:
            key, raw_value = line.split(sep, 1)
            return f"{key}{sep}{_mask_raw_value(raw_value)}"

    return mask_value(line)


def _mask_raw_value(raw: str) -> str:
    stripped = raw.lstrip(" ")
    leading_spaces = raw[: len(raw) - len(stripped)]

    for quote in ('"', "'"):
        if stripped.startswith(quote):
            inner_start = 1
            end_idx = stripped.find(quote, inner_start)
            if end_idx == -1:
                continue
            inner = stripped[inner_start:end_idx]
            suffix = stripped[end_idx + 1 :]
            return f"{leading_spaces}{quote}{mask_value(inner)}{quote}{suffix}"

    return f"{leading_spaces}{mask_value(stripped)}"


def mask_field_origins(
    origins: tuple[FieldOrigin, ...],
    *,
    secret_paths: frozenset[str],
) -> tuple[FieldOrigin, ...]:
    result: list[FieldOrigin] = []
    for origin in origins:
        if origin.key in secret_paths:
            masked_value: JSONValue = mask_value(str(origin.value))
            result.append(
                FieldOrigin(
                    key=origin.key,
                    value=masked_value,
                    source_index=origin.source_index,
                    source_file=origin.source_file,
                    source_loader_type=origin.source_loader_type,
                ),
            )
        else:
            result.append(origin)
    return tuple(result)


def mask_source_entries(
    entries: tuple[SourceEntry, ...],
    *,
    secret_paths: frozenset[str],
) -> tuple[SourceEntry, ...]:
    result: list[SourceEntry] = []
    for entry in entries:
        masked_raw = mask_json_value(entry.raw_data, secret_paths=secret_paths)
        result.append(
            SourceEntry(
                index=entry.index,
                file_path=entry.file_path,
                loader_type=entry.loader_type,
                raw_data=masked_raw,
            ),
        )
    return tuple(result)


def is_random_string(value: str) -> bool:
    cfg = config.masking
    if len(value) < cfg.min_heuristic_length:
        return False

    if _heuristic_detector is None:
        return False

    word = value.lower()
    bigrams = [word[i : i + 2] for i in range(len(word) - 1)]
    if not bigrams:
        return False

    uncommon = sum(
        1 for b in bigrams if _heuristic_detector.bigrams.get(b, 0) <= _heuristic_detector.common_bigrams_threshold
    )
    return uncommon / len(bigrams) > cfg.heuristic_threshold
