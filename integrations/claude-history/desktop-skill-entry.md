## PDA development Mac Desktop cache reader

Claude history has two different sources. For an unspecified "Claude history" request, query both `code` and `desktop-cache` and report them separately. Never call Code-only results "both". The Desktop source below is ordinary Claude Desktop Chat, not the Desktop Code tab or Cowork.

Use the same installed reader/connection with `--source=desktop-cache`:

```sh
python3 -B /home/user/.hermes/skills/autonomous-ai-agents/claude-code/scripts/claude_history.py list --source=desktop-cache --connection /home/user/.hermes/skills/autonomous-ai-agents/claude-code/references/main-connection.json --limit=20
python3 -B /home/user/.hermes/skills/autonomous-ai-agents/claude-code/scripts/claude_history.py search --source=desktop-cache --connection /home/user/.hermes/skills/autonomous-ai-agents/claude-code/references/main-connection.json --search='keyword'
python3 -B /home/user/.hermes/skills/autonomous-ai-agents/claude-code/scripts/claude_history.py read --source=desktop-cache --connection /home/user/.hermes/skills/autonomous-ai-agents/claude-code/references/main-connection.json --project='ORGANIZATION_ID_FROM_RESULT' --session-id='SESSION_ID_FROM_RESULT'
```

The source-specific default is `~/Library/Application Support/Claude/Cache/Cache_Data` on the selected Mac. `--project` means the organization UUID for Desktop, not the Code project directory. `source_kind=claude-desktop-cache` always has `coverage_complete=false`: this is only cached snapshots, not the entire cloud account or its current state. An absent hit means "not in the available cache", not "never discussed". Cached conversations may since have changed or been deleted online. `scan_complete` describes only whether matching cache entries parsed without warnings. Do not label this a complete Desktop history integration.

The reader opens raw files read-only; it never launches/resumes Claude, opens a writable Chromium DB, fetches cloud endpoints, reads cookies/Keychain, or changes Mac configuration. Chromium Simple Cache v5 headers, footer offsets, available CRCs, and key SHA256 are validated. Only exact Claude conversation-response keys are decoded; arbitrary cache entries and credentials are not returned. Zstd uses an already-installed native library (`/opt/homebrew/lib/libzstd.dylib` was verified on main), not a Mac dependency install.

The projection is user/assistant text across cached message-tree branches. Tool calls/results require `--include-tools`; thinking, attachments, rendered artifacts, and unknown blocks are omitted. Keep the same projection between list/search/read. Preserve `source`, `source_sha256`, organization/session IDs, message UUID/parent UUID, `source_message_index`, timestamp, and current leaf UUID. Follow `next_offset` and `text_next_offset`; confirm `source_sha256` is unchanged across search/read/pages. On a mismatch, disclose the changed snapshot and rerun rather than splice revisions. The newest cached `updated_at` revision wins, with file mtime/path as tie-breakers.

Limits: 30-second scan/search checks, 45-second SSH wall deadline, 50,000 directory entries, 64 MiB per raw entry, 32 MiB per decoded body, 256 MiB aggregate raw/decoded data, 1,000 warnings. An error is not a valid empty result and never triggers a local fallback.

Full cloud history remains a separate authentication/export boundary. An SSH-side attempt to access the existing Claude Safe Storage key failed; do not repeatedly probe or bypass OS authentication. The official alternative is owner-generated Claude Settings > Privacy > Export data, followed by explicit private-file handling. Team/Enterprise exports are restricted to the organization's Primary Owner; do not request an entire company's export just to read this user's chats. Full-account export ingestion/live browsing is not implemented by this cache source. Never put private/corporate transcripts in public PKB, Git, shared Kanban comments, or reviewer inputs.

Sources: https://support.claude.com/en/articles/9450526-export-your-claude-data and https://raw.githubusercontent.com/chromium/chromium/main/net/disk_cache/simple/simple_entry_format.h
