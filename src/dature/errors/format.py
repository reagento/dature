import traceback


def format_dature_error(exc: BaseException) -> str:
    """Render a DatureError / DatureConfigError (ExceptionGroup) as plain text."""
    if isinstance(exc, BaseExceptionGroup):
        return "".join(traceback.format_exception(type(exc), exc, None))
    return str(exc)
