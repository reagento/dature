"""Debug-logging helpers for the loading pipeline.

All functions emit ``DEBUG``-level messages to the ``dature`` logger and have no
side-effects beyond logging — they do not mutate any state.
"""

import logging

from dature.config import MaskingConfig
from dature.loading.merge_runtime import MergeStepEvent
from dature.masking.masking import is_secret_path, mask_json_value, mask_value
from dature.report_types import FieldOrigin
from dature.type_aliases import JSONValue

logger = logging.getLogger("dature")


def log_merge_step(
    *,
    event: MergeStepEvent,
    dataclass_name: str,
    strategy_label: str,
    secret_paths: frozenset[str],
    masking: MaskingConfig,
) -> None:
    if isinstance(event.before, dict) and isinstance(event.source_data, dict):
        added = sorted(set(event.source_data.keys()) - set(event.before.keys()))
        overwritten = sorted(set(event.source_data.keys()) & set(event.before.keys()))
        logger.debug(
            "[%s] Merge step %d (strategy=%s): added=%s, overwritten=%s",
            dataclass_name,
            event.step_idx,
            strategy_label,
            added,
            overwritten,
        )
    masked = mask_json_value(event.after, secret_paths=secret_paths, masking=masking)
    logger.debug(
        "[%s] State after step %d: %s",
        dataclass_name,
        event.step_idx,
        masked,
    )


def log_field_origins(
    *,
    dataclass_name: str,
    field_origins: tuple[FieldOrigin, ...],
    masking: MaskingConfig,
    secret_paths: frozenset[str] = frozenset(),
) -> None:
    for origin in field_origins:
        if is_secret_path(origin.key, secret_paths=secret_paths, masking=masking):
            masked = mask_value(str(origin.value), masking)
            logger.debug(
                "[%s] Field '%s' = %r  <-- source %d (%s)",
                dataclass_name,
                origin.key,
                masked,
                origin.source_index,
                origin.source_file,
            )
        else:
            logger.debug(
                "[%s] Field '%s' = %r  <-- source %d (%s)",
                dataclass_name,
                origin.key,
                origin.value,
                origin.source_index,
                origin.source_file,
            )


def log_single_source_load(
    *,
    dataclass_name: str,
    loader_type: str,
    file_path: str,
    data: JSONValue,
    masking: MaskingConfig,
    secret_paths: frozenset[str] = frozenset(),
) -> None:
    logger.debug(
        "[%s] Single-source load: loader=%s, file=%s",
        dataclass_name,
        loader_type,
        file_path,
    )
    masked_data = mask_json_value(data, secret_paths=secret_paths, masking=masking)
    logger.info(
        "[%s] Loaded data: %s",
        dataclass_name,
        masked_data,
    )
