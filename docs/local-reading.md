---
title: Local Reading
description: Decrypt and query authorized WeCom data on macOS or Windows without depending on online history APIs.
---

# Local Reading

The local track reads data from the operator's own signed-in WeCom desktop installation. It supports historical chat search, contact and conversation views, statistics, media export, and local document discovery.

## Choose the platform entry point

| Platform | Entry point | Shared core |
|---|---|---|
| macOS | `decrypt/macos/` | `decrypt/wxwork_crypto.py` and `decrypt/export_wxwork.py` |
| Windows | `decrypt/windows/` | `decrypt/wxwork_crypto.py` and `decrypt/export_wxwork.py` |

The shared crypto module validates candidate keys before decrypting a database. The platform-specific layer locates the WeCom files and coordinates the workflow.

## macOS workflow

Only initial key capture requires a running, signed-in WeCom client. The first key-capture setup is documented in `docs/解密思路.md`; ordinary refreshes reuse existing keys and can run offline.

```bash
python3 decrypt/macos/read_wecom.py
# Only when existing keys are unavailable, after preparing the authorized client:
python3 decrypt/macos/find_key_fast.py
# Optional: all local databases, including local todos/calendars:
python3 decrypt/macos/decrypt_wxwork.py
# Optional: explicitly export all chat messages:
python3 decrypt/macos/read_wecom.py --export /private/path/export
# After querying, remove the derived chat snapshots:
python3 decrypt/macos/read_wecom.py --clean
```

`read_wecom.py` refreshes only `Messages1/Info.db` and `Messages1/Session.db`. It fails on missing/invalid keys without scanning memory, and does not export messages by default. **Migration:** the former automatic capture/decrypt/bulk-export behavior is now separated into the explicit commands above. Existing standalone decrypt and export commands remain available.

`--clean` unlinks only those two derived databases and their `-wal`, `-shm`, `-journal` sidecars. It preserves keys, exports, non-chat snapshots and unrelated files, and refuses source-directory overlap or paths escaping the decrypted root. It is intended for a completed task, not while another query is still using the same snapshot. Capture does not log key values; newly compiled native validators are temporary and removed automatically.

## Query local data

```bash
python3 decrypt/macos/wecom_local.py contacts [keyword]
python3 decrypt/macos/wecom_local.py conversations
python3 decrypt/macos/wecom_local.py members <conversation>
python3 decrypt/macos/wecom_local.py search <keyword>
python3 decrypt/macos/wecom_local.py search <keyword> --conversation <conversation-id> --days 30 --json
python3 decrypt/macos/wecom_local.py stats
python3 decrypt/macos/wecom_local.py todo
python3 decrypt/macos/wecom_local.py calendar
python3 decrypt/macos/wecom_local.py media
python3 decrypt/macos/wecom_local.py openfile <name-or-keyword>
python3 decrypt/macos/wecom_local.py conversations --limit 100 --offset 0 --json
python3 decrypt/macos/wecom_local.py chat <conversation-id> --days 7 --limit 50 --json
python3 decrypt/macos/wecom_local.py export <conversation-id> --out decrypt/macos/export/chat.html --with-media
```

| Command | Result |
|---|---|
| `contacts` | Local contact fields filtered by an optional keyword |
| `conversations` | Conversation names, message counts, and latest timestamps |
| `members` | Participants ranked by message count for a matched conversation |
| `search` | Message time, conversation, sender, and body matches |
| `stats` | Totals and rankings by sender, conversation, message type, hour, and day |
| `todo` / `calendar` | Locally available todo and calendar records |
| `media` | Copies readable cached images and files into an export directory |
| `openfile` | Locates a chat file and extracts text when the format is supported |
| `chat` | Reads one uniquely identified conversation, newest first, with full message bodies |
| `export` | Writes a scoped TXT, Markdown, HTML, JSON or CSV transcript, optionally with local media |

## Pagination and identity

`conversations`, `search`, and `chat` accept `--limit 1..2000 --offset N --json`. Results include `count`, `total`, `offset`, `limit`, and `next_offset`; the final page has a null `next_offset`. CLI conversations/search retain their unlimited behavior when `--limit` is omitted. MCP defaults to 100 conversations or 50 messages. Queries stream database rows and retain only the selected search page. Search order is chronological; chat order is newest first, with the local message ID breaking timestamp ties.

`--days` must be a positive integer; omitting it includes all dates. Text bodies, repeated protobuf text fields, whitespace and line breaks are preserved. Searches cover the full decoded body, including its tail. Message results include database table, conversation ID, local ID and server ID. Use conversation IDs when names are duplicated: ambiguous names return candidates before reading, exporting or listing members.

`search --conversation <id-or-unique-name>` filters at the database query before counting or reading message bodies. An explicitly empty or ambiguous conversation fails instead of becoming an account-wide search. Use conversation/contact metadata to locate people; only omit the scope when account-wide message search is intended. A missing or ID-only conversation name can fall back to the exact matching user identity; an existing group name is never replaced by a participant's name.

### Credentials in query output

`chat` and `search` mask recognizable credentials in their shared result serializer, before human-readable, JSON or MCP output. Changed rows include `content_redacted: true`; identity, sender, timestamp, pagination and noncredential text remain available. Search matching still uses the original text. The mask covers labelled API keys/passwords (including full-width colons), URL password fields/userinfo, common bearer/token forms and private-key blocks. It does not guarantee detection of arbitrary unlabelled or obfuscated secrets.

Explicit local exports retain the original body, including credentials if present. This keeps the source record available on the authorized machine without changing the database. Do not print or pass raw exports to an agent; inspect/redact required fields locally first. Output limiting such as `head` is not redaction.

## Conversation exports with media

```bash
python3 decrypt/macos/wecom_local.py export <conversation-id> --days 30 --out decrypt/macos/export/chat.md --with-media
python3 decrypt/macos/wecom_local.py export <conversation-id> --out decrypt/macos/export/chat.html --with-media
# Equivalent shared macOS exporter; legacy --db/--out-directory bulk JSON/CSV still works:
python3 decrypt/export_wxwork.py --db /path/to/Info.db --conversation <id> --out export/chat.html --with-media --cache-dir /path/to/Caches
```

The output extension selects the format (`.md`, `.html`/`.htm`, `.json`, `.csv`, otherwise TXT); `--format` can override it. `--with-media` adds a `<stem>.media.json` sidecar and a fresh `<stem>.assets-<export-id>/` directory when readable files exist. Move the transcript, sidecar and the exact directory named in `assets_directory` together. Earlier export directories remain available; a new date range never inherits the previous export's files. JSON/CSV rows can be joined to the sidecar by table, conversation ID and local message ID.

Each media entry records its database snapshot identity, message identity, kind, relative file paths, status and reason. It contains no raw message blob, remote URL, decryption key or absolute cache path. HTML escapes message text and displays readable images locally; Markdown embeds local images; TXT includes relative attachment paths. Files and voice are linked for local opening, without automatic playback or transcription. Files are copied with private permissions and atomic replacement; changing sources, traversal and cache symlinks are rejected.

The adapter uses these observed native payload profiles:

| Type | Payload | Local cache relation |
|---|---|---|
| 14, image | protobuf field 10 resource ID; field 2 optional original name | `Images/<month>/<resource-id>/<name>`; original preferred over thumbnail variants |
| 15, file | field 10 resource ID and field 2 original name | `Files/<month>/<resource-id>/<name>`; both ID and name must match |
| 16, voice | field 10 resource ID | `Voices` registered ID directory or filename |
| 29, emotion | field 6 resource ID | `Emotions` registered ID directory or filename |

Windows uses singular cache names (`Image`, `File`, `Voice`, `Emotion`) with the shared payload parser. Resource IDs are **not assumed to be content checksums**. Multiple distinct files matching the same resource are reported as `ambiguous`; byte-identical cached copies may share a resolution. Plain JPEG/PNG/GIF/WebP are detected by signature, including `.dat` names. An unreadable image is `encrypted_unsupported`; missing local files are `not_found`; malformed or unknown payloads are `unsupported`. Nested media inside forwarded/compound cards are not guessed from arbitrary strings. This implementation does not fetch remote files or add an encrypted-image decoder.

The corrected macOS type labels (14=image, 16=voice) and native cache relations were checked on WeCom 5.0.12. A temporary local smoke run decrypted Info.db/Session.db, including the live Session WAL, and checked 60 media messages: 33 resolved, 27 not cached. Only aggregate counts were recorded, and temporary private outputs were removed. Windows adapters and Win32 shared WAL reading are covered by synthetic fixtures in CI; no current native Windows account was used for this change.

## Relocated data and multiple accounts

| Variable | Purpose |
|---|---|
| `WECOM_PROFILE` | macOS profile directory or its name under the default Profiles root |
| `WECOM_DATA_DIR` | Windows directory containing `message.db` |
| `WECOM_STATE_DIR` | macOS runtime parent; a subdirectory for the selected profile holds keys and decrypted data |
| `WECOM_KEYS_FILE` | Explicit macOS key JSON path shared by capture, decrypt, refresh and monitor commands |
| `WECOM_DECRYPTED_DIR` | Relocated decrypted root (macOS includes `Messages1/`; Windows contains `message.db`) |
| `WECOM_CACHE_DIR` | Explicit cache root containing the platform's media subdirectories |

Multiple native accounts require an explicit selection. Invalid overrides fail instead of silently selecting another account. Offline macOS queries can read the configured decrypted root without a running client or an available native profile; media resolution additionally needs its corresponding cache root.

New macOS state defaults to `~/.local/share/wecom-agent/<profile>/`. With no explicit state/key/decrypted override, existing `decrypt/macos/wxwork_keys.json` and `decrypt/macos/decrypted/` are still read in place; no automatic data migration or duplicate backup is made. Explicit overrides take priority, including when the configured key file is missing or invalid.

## Database snapshots and incremental reads

Both platform decryptors read a stable main/WAL pair, validate WAL checksums, salts and commit boundaries, and apply only committed frames before decrypting native wxSQLite3 pages. Partial ciphertext pages are rejected rather than padded. SQLite integrity checks cover ordinary tables; custom ICU FTS virtual tables and their shadows are excluded because the desktop tokenizer is unavailable in standard Python. Any key, snapshot or structural integrity failure preserves the previous decrypted output. Plain SQLite inputs use the same snapshot path. Local queries open databases in read-only mode.

WeCom's wxSQLite3 AES-128 format has no page HMAC. WAL and b-tree checks detect transport/structural failures but do **not** authenticate arbitrary message contents. SQLCipher HMAC changes from wechat-decrypt are therefore not copied into this format.

The macOS monitor watches main-file and WAL changes, persists a profile-scoped local LID cursor only after output succeeds, and includes messages inserted later with the same or an earlier send time. This assumes native monotonically assigned LIDs; use `--all` after restoring or rebuilding a database. A legacy timestamp-only state replays its final timestamp boundary once when migrating. Windows monitoring retains its existing timestamp behavior; the new bounded queries and conversation exports are shared on both platforms.

## Windows workflow

Install Python and `pycryptodome`, then use the PowerShell coordinator or the Python reader directly:

```powershell
powershell -ExecutionPolicy Bypass -File decrypt/windows/run.ps1 <command>
powershell -ExecutionPolicy Bypass -File decrypt/windows/run_test.ps1
powershell -ExecutionPolicy Bypass -File decrypt/windows/find_key.ps1
python decrypt/windows/wecom_win.py <key> <command>
```

## Document and media behavior

`openfile` and `decrypt/read_doc.py` support plain text, CSV, Markdown, JSON, Excel workbooks, Word documents, and text-based PDFs when the optional parser dependency is available. Image files and scanned PDFs return a visual marker and path instead of fabricated text.

Optional parsing packages include `openpyxl`, `pdfplumber`, and `python-docx`. Optional voice transcription uses the separate `decrypt/macos/voice_transcribe.py` workflow.

## Data handling

Decrypted databases, key files, exports, and local runtime data are ignored by Git. Keep them on the authorized device and review the [security rules](/security) before sharing diagnostics.
