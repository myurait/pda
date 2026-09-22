#!/bin/sh
set -eu
exec python -m "${PDA_MODULE:-pda_wrapper}"
