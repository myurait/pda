#!/bin/sh
# Offline restoration of an already-selected compatible checkpoint.
# Invocation belongs to the predeclared drill, not a running recovery service.
set -eu
cd "$(dirname "$0")"
: "${M2_PYTHON:?}" "${M2_ARCHIVE:?}"
docker compose -p m2proof --env-file .runtime/compose.env -f compose.yaml stop
docker compose -p m2proof --env-file .runtime/compose.env -f compose.yaml run --rm -T --no-deps --volume "$M2_ARCHIVE:/tmp/m2-recovery.zip:ro" hermes "$M2_PYTHON" -m hermes_cli.main import /tmp/m2-recovery.zip --force
docker compose -p m2proof --env-file .runtime/compose.env -f compose.yaml up -d --wait --wait-timeout 30
