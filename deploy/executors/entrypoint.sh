#!/bin/sh
set -eu
if [ "$#" -gt 0 ]; then
    exec "$@"
fi
exec python -m "${PDA_MODULE:-pda_wrapper}"
