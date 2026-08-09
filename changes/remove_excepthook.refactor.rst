Removed the global ``sys.excepthook`` patch installed on ``import dature``. Instead,
``DatureError`` and ``DatureErrorGroup`` hide dature's own internal frames from their
``__traceback__`` directly, so unhandled dature errors now print a traceback that
stops at your own call site instead of showing zero frames. This also fixes tracebacks
in contexts the old hook never reached — ``logging.exception``, ``traceback.print_exc``,
pytest failures — and no longer eats the traceback of a ``DatureError`` raised by your
own code outside dature.
