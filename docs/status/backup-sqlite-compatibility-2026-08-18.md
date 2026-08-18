# Backup SQLite compatibility transition — 2026-08-18

Status: verified
Scope: same-host local continuity backup

## Trigger

The scheduled 05:00 backup and a later manual retry failed while validating Hermes `state.db`. The live database itself was not generically corrupt: the result depended on which SQLite/FTS implementation opened it.

## Root cause evidence

- Host `/usr/bin/python3` used SQLite 3.45.1.
- Hermes managed Python used SQLite 3.53.1.
- Current live `~/.hermes/state.db` passed full integrity under 3.53.1 and reported a malformed FTS5 trigram index under 3.45.1.
- The preserved pre-update `state.db` and repair backup passed under 3.45.1 and reported the reverse compatibility under 3.53.1.
- A three-attempt online-backup reproduction copied the version-specific integrity result consistently; the failure was not a transient rsync or WAL race.

## Resolution

- The scheduled service now invokes the backup code with Hermes's managed Python so live Hermes databases are backed up and verified by the compatible SQLite implementation.
- The policy narrowly classifies `state-snapshots/*/state.db` and `state.db.malformed-backup-*` as historical opaque SQLite.
- Declared opaque databases and their regular WAL/SHM/journal sidecars are preserved byte-for-byte and checksum-verified, but are not opened by the current SQLite library.
- The prior successful generation remained immutable. Its `latest` pointer was removed only during a reversible migration; failure restored the pointer, and success published a new current generation while retaining the old target.

## Verification

Current route:

- The actual systemd service completed with exit status 0 using the fixed interpreter and policy.
- The timer remains active and waiting for the next 05:00 Asia/Tokyo event.
- The new latest generation passed full status verification.
- A full restore drill completed, and the restored current `state.db` passed integrity under SQLite 3.53.1.

Legacy route:

- The preserved generation `2026-08-17T224435+0900` was restored with `/usr/bin/python3` / SQLite 3.45.1.
- The restored legacy `state.db` passed full integrity under SQLite 3.45.1.
- The drill directory was removed only after the result was verified.

Code gates:

- Backup test suite passed.
- Ruff and mypy passed.
- systemd unit verification and Git whitespace checks passed.

## Recovery rule

Do not treat a version-specific FTS integrity failure as either corruption or permission to bypass verification. Use the interpreter compatibility evidence for that generation, restore in isolation, verify there, and migrate forward before production use. Never modify an already published generation to make it satisfy a newer verifier.

This remains same-host, same-disk protection and is not off-host disaster recovery.
