# Claude Desktop history integration

Status: partial implementation, not completion of full Desktop/cloud history access.

The task adds ordinary Claude Desktop Chat cached response reading to the existing standalone read-only `history.py`. The existing `code` default and connection configuration are unchanged. The explicit `desktop-cache` source is not the Desktop Code tab or Cowork, and is not an authenticated cloud client.

## Verified before deployment

- macOS main, Claude Desktop 1.52386.0.
- 19 cached Chat conversation identities and 112 projected text messages read through actual SSH/CLI.
- All 28 matching response cache files had identical SHA256 and mtime before/after the verification.
- Cached source inventory identity set matched the complete paginated CLI list.
- Literal Japanese search returned 96 hits; search-to-read message UUID and source digest matched.
- 24 CLI operations, maximum 1.29 seconds.
- Standard Code regression: all 654 top-level session files listed; search/read succeeded; all source content digests and mtimes unchanged.
- 40 focused fixture/regression tests passed.

Counts above describe those point-in-time tests, not permanent bounds. See `desktop-mac-verification.json` and `desktop-code-regression.json`. Private text, titles and credentials were not persisted in these artifacts.

The first independent review rejected the live verifier's dependence on assertions under Python optimization. An explicit pre-I/O refusal of optimized Python was added with a failing-then-passing CLI regression test. The review also identified silently dropped string-form message content; a separate failing-then-passing fixture covers the one-line correction. The revised suite passed 42 tests. `desktop-mac-rerun.json` records the repeated real Desktop check against the revised reader: all 19 conversations / 112 text messages and all 28 source files' digests/mtimes verified again. The initial failure report is retained, not overwritten.

## Deliberate constraints

The cache may omit conversations, contain older revisions, or retain a conversation deleted from the cloud. Every result therefore carries `coverage_complete=false`; `scan_complete` describes parsing of available matching entries only. A cache miss is not proof of no prior discussion. No export ingestion, continuous sync, cloud API access, Mac restart/reboot recovery, attachments, or rendered artifacts is claimed.

`--include-tools` opts into stored tool text. Thinking is always omitted. Cached tree branches are preserved with UUIDs, parent UUIDs and `current_leaf_message_uuid`; they are not flattened into a fabricated single branch. Follow both message and text pagination and compare source digests across calls.

The authenticated-source discovery stopped before any cloud request: the single attempt to obtain the existing desktop key through the OS Keychain exited unsuccessfully. No credentials were obtained. Repeated probing, copying cookies/private keys, weakening Keychain controls, and starting/resuming Claude are not proposed remedies. No matching pre-existing Claude export was found in the top level of the user's Downloads or Documents directories.

Full history requires a suitable signed-in UI path or a user-owned export. Official individual account exports are under Settings > Privacy > Export data. Team/Enterprise exports require the organization's Primary Owner; do not obtain an entire organization's data simply to satisfy a request for this user's history.

## Operation and deployment

See `desktop-skill-entry.md` for exact CLI commands and limits. `desktop-finalization-plan.json` limits deployment to the existing runtime reader and the discovery/usage text in the existing Claude skill, with a baseline-bound rollback backup. No additional daemon, core tool, service restart, Mac setting change, key change, or stopped autonomy process is required.

This task remains open until the owner-requested Desktop scope is actually available. Installing the useful cache reader is not grounds to close the full-history requirement.

Sources inspected:

https://raw.githubusercontent.com/chromium/chromium/main/net/disk_cache/simple/simple_entry_format.h
https://support.claude.com/en/articles/9450526-export-your-claude-data
https://hermes-agent.nousresearch.com/docs/user-guide/features/skills
