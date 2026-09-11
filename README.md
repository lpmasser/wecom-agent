# WeCom Agent

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Agent Skill](https://img.shields.io/badge/Agent%20Skill-Codex-blue.svg)](SKILL.md)
[![Python](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)
[![CI](https://github.com/tzwkb/wecom-agent/actions/workflows/ci.yml/badge.svg)](https://github.com/tzwkb/wecom-agent/actions/workflows/ci.yml)

[Documentation](https://wecom-agent.readthedocs.io/en/latest/) | English | [中文](README_ZH.md)

Agent Skill — WeCom local-decrypt reading plus WecomTeam CLI/Bot operations for chat search, media/file discovery, todos, and online documents/sheets.

## Capabilities

| Track | Capability | Status |
|---|---|---|
| B local reading | Decrypt/export local chats, contacts, conversations, full-text search, stats, media export, local file discovery | Available |
| A online operations | WecomTeam `wecom-cli` wrapper for documents, online sheets, smart sheets, todos, and other supported online APIs | Partially available, permission-dependent |
| Realtime interaction | WecomTeam Bot SDK WebSocket receive/reply path | Planned |

The legacy self-built app HTTP API is no longer the main path. Historical chat reading defaults to local decrypt; online write operations go through WecomTeam `wecom-cli`.

## Local Reading

```bash
PY=/opt/homebrew/bin/python3
$PY decrypt/macos/read_wecom.py
$PY decrypt/macos/wecom_local.py stats
$PY decrypt/macos/wecom_local.py contacts <name>
$PY decrypt/macos/wecom_local.py search <query>
$PY decrypt/macos/wecom_local.py conversations|members <conversation>|todo|calendar|media
$PY decrypt/macos/monitor.py --poll 30
$PY decrypt/macos/voice_transcribe.py
```

## Online Documents And Sheets

```bash
npm install -g @wecom/cli
wecom-cli auth init
wecom-cli auth show --status

$PY -m online.selfcheck
```

Implemented wrappers:

- `online.docs`: create/read normal documents, overwrite Markdown content, and create/import smart pages; structured legacy smart-page payloads remain limited to CLI `0.1.x`.
- `online.local_docs`: read locally cached/downloaded documents as a fallback when online content APIs are unavailable.
- `online.sheets`: create online sheets, read metadata and cell ranges, add/delete subsheets, append rows, and update ranges.
- `online.smartsheets`: create smart sheets, manage child sheets/fields/records, and read records across legacy and current CLI generations.

`wecom-cli 1.1+` introduced a breaking nested command model and added online document, sheet, smart-page, and smart-sheet services. The wrappers detect the installed generation and translate current payloads. Structured legacy smart-page `pages` remain fail-closed because they cannot be mapped losslessly; use Markdown import instead. See [the migration note](docs/wecom-cli-migration.md).

## MCP

```bash
bash setup.sh
```

MCP keeps local tools (`wecom_contacts`, `wecom_search`, `wecom_openfile`, etc.), adds local document fallback tools (`wecom_local_doc_read_path`, `wecom_local_doc_search`), and exposes current online reads including `wecom_doc_read`, `wecom_sheet_get_range`, and `wecom_smartsheet_records`. Online write tools require `confirmed=True`.

`setup.sh` creates an isolated `.venv` from the pinned [requirements](requirements.txt). Optional local document parsers are listed in [requirements-documents.txt](requirements-documents.txt).

## Development

```bash
python3 -m pip install -r requirements-dev.txt
python3 -m unittest discover -s tests -v
python3 -m compileall -q server.py online decrypt tests
ruff check online server.py tests
pip-audit -r requirements.txt
npm ci && npm run docs:build -- --output /tmp/wecom-agent-docs --quiet
```

## Structure

```text
decrypt/                          Track B local decrypt/read core
online/                           Track A WecomTeam CLI wrappers
server.py                         MCP thin facade
legacy/self-built-app/            legacy self-built app experiments
docs/                             design notes, status, and development docs
tests/                            unit tests
```

## Safety

- Read only the user's own device/account.
- Decryption outputs, keys, credentials, and runtime data stay gitignored.
- Every online write operation must confirm target, content, and impact before execution.
