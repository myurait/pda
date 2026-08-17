# Local continuity backup

When installed and healthy, this operation preserves the declared PDA continuity state as a locally restorable snapshot. Its desired schedule is daily at 05:00 Asia/Tokyo with the newest successful generation for each of the latest seven local calendar days retained. Failed or incomplete runs do not delete a prior successful generation; Git records desired state, while runtime health is established only by the timer, a fresh current-policy snapshot, and a successful restore drill.

Canonical assets

- Policy and source inventory: `continuity/local-backup.json`
- Managed-habit declaration: `profiles/pda/managed-habits.json`
- Implementation: `src/pda/backup/`
- Runtime entry point: `operations/backup/pda_backup.py`
- Schedule: `infra/systemd/pda-local-backup.{service,timer}`

Snapshot scope

The declared snapshot scope includes the full Hermes home, the PDA repository working tree (including local changes), the Firecrawl runtime source/configuration, Open WebUI configuration and live data, the PDA Tailscale state, and installed user-level systemd units. Firecrawl queue/database volumes, container images, host packages, and the separately installed Tailscale binary are rebuild/discard dependencies rather than continuity state; they are not claimed as captured runtime state. SQLite databases in declared sources are copied with the online backup API, checked for integrity and foreign-key violations, and converted to standalone DELETE-journal snapshots. Each retained generation is an independent full copy so mutation of one generation cannot silently alter another.

Snapshots are stored under `~/pda-backups/local-continuity`. The directory is mode 0700 and may contain credentials and private conversations. Do not publish or add it to Git.

Installation

Unattended execution depends on the per-user systemd manager remaining available after logout and starting during boot. Verify it with `loginctl show-user "$USER" --property=Linger --value`; if the result is not `yes`, enable it explicitly with `sudo loginctl enable-linger "$USER"`.

Run `/usr/bin/python3 operations/backup/install.py` from the canonical PDA repository. The installer links the Git-managed service and timer into the user systemd manager, creates the private backup root, reloads systemd, and enables the timer. Then start one bounded initial run with `systemctl --user start pda-local-backup.service` and verify it with the status command below.

The 05:00 event runs at that time only when the host is running. Because the timer is persistent, systemd performs one catch-up activation after the host or user manager next starts. Within that single activation, the backup waits up to 30 minutes for Docker, the configured container, and container Python/SQLite readiness before copying multi-gigabyte sources. The service does not automatically restart after an activation failure: this prevents a late post-commit durability warning from immediately creating another generation. A readiness timeout is visible in the journal and may be rerun manually; the next scheduled event remains armed.

Verification

Run:

`/usr/bin/python3 operations/backup/pda_backup.py status --config continuity/local-backup.json`

A successful result verifies the snapshot manifest, the complete restored tree including file modes and empty directories, every file checksum, every SQLite database, alignment with the current Git-managed policy, and freshness within 36 hours. Detailed service logs are available through `journalctl --user -u pda-local-backup.service`.

Restore drill

Restore only into a new, empty drill location; the command refuses to overwrite an existing path:

`/usr/bin/python3 operations/backup/pda_backup.py restore --config continuity/local-backup.json --snapshot ~/pda-backups/local-continuity/latest --destination ~/pda-backups/restore-drill`

The restored snapshot is verified again after copying. Its `manifest.json` records each original source, and the restorable trees are under `data/`. Applying those trees over a live runtime is a separate, explicit recovery operation and is not performed automatically.

Limitation

This is a same-host recovery point. It does not protect against failure, loss, or destruction of the host or disk. Off-host export and custody are deferred and must not be reported as complete.
