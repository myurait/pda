#!/bin/sh
# One-shot standard deployment declaration, not a daemon or business-state machine.
# Run inside the docker Unix group. No inference/diagnosis is invoked on failure.
set -eu
cd "$(dirname "$0")"
: "${M2_BAD_SOURCE:?synthetic bad release path required}"
if HERMES_SOURCE="$M2_BAD_SOURCE" docker compose -p m2proof --env-file .runtime/compose.env -f compose.yaml up -d --wait --wait-timeout 30; then
  printf '%s\n' 'UNEXPECTED_BAD_RELEASE_HEALTHY'
  exit 2
fi
docker inspect -f '{{.State.Status}} exit={{.State.ExitCode}} restarts={{.RestartCount}}' m2proof-hermes
docker logs --tail 12 m2proof-hermes
printf '%s\n' 'CANDIDATE_REJECTED_RESTORE_PINNED_GOOD'
docker compose -p m2proof --env-file .runtime/compose.env -f compose.yaml up -d --wait --wait-timeout 30
