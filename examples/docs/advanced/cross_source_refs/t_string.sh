#!/usr/bin/env bash
# Only run the t-string example on Python 3.14+; silently skip on older versions.
if "${PYTHON:-python3}" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 14) else 1)' 2>/dev/null; then
    exec "${PYTHON:-python3}" "$(dirname "$0")/t_string.py" "$@"
fi
