---
title: wecom-cli 1.1+ Migration
description: Understand the breaking command-model change and the repository's version-aware compatibility boundary.
---

# `wecom-cli` 1.1+ Migration

The official CLI changed its command and authentication model in `1.1.0`. The latest release verified during this maintenance pass was `1.2.0` on 2026-09-01. See the official [WecomTeam repository](https://github.com/WecomTeam/wecom-cli) and [npm package](https://www.npmjs.com/package/@wecom/cli) for newer releases.

## Breaking changes

| Legacy `0.1.x` | Current `1.1+` |
|---|---|
| `wecom-cli init` | `wecom-cli auth init` |
| `wecom-cli auth show --auth-status` | `wecom-cli auth show --status` |
| `doc create_doc` | `doc create` |
| `doc edit_doc_content` | `doc contents overwrite` |
| no online document-body read | `doc contents get` |
| `doc sheet_get_info` | `sheet get` |
| `doc sheet_append_data` | `sheet rows append` |
| `doc sheet_update_range_data` | `sheet contents update` |
| no standard-sheet cell read | `sheet ranges get` |
| flat `doc smartsheet_*` methods | native `smartsheet <resource> <method>` service |
| `msg` / `schedule` services | `message` / `calendar` services |

Payloads also changed. Smart-sheet operations now commonly identify child resources by readable titles rather than the legacy IDs accepted by this repository's old wrappers. Do not translate only the command name and reuse the old payload.

## Repository behavior

The Python layer detects the installed semantic version before choosing a command path.

| Area | Legacy `0.1.x` | Current `1.1+` |
|---|---|---|
| Normal document create/write | Supported | Supported |
| Normal document latest-body read | Unsupported | Supported |
| Standard sheet structure/write | Supported | Supported |
| Standard sheet cell-range read | Unsupported | Supported |
| Smart-page empty create / Markdown import | Legacy create only | Supported |
| Smart-page structured legacy `pages` payload | Supported | Fails closed; cannot map losslessly |
| Smart-sheet child sheets, fields, and records | Supported, except record reads | Supported |

Failing closed prevents an old payload from reaching a newly named write endpoint. `python3 -m online.selfcheck` reports the detected generation, authorization state, available services, and wrapper coverage.

## Upgrade safely

```bash
npm install -g @wecom/cli
wecom-cli --version
wecom-cli auth show --status
python3 -m online.selfcheck
```

The repository never upgrades the global CLI automatically. On 2026-09-01 the local CLI was explicitly upgraded from `0.1.9` to `1.2.0`; authorization remained valid. The Python/MCP wrappers now cover current normal documents, standard sheets, smart-page create/import, and smart-sheet sheet/field/record operations.

No online write should be used as a version probe. Inspect `--help`, `--doc`, or `--schema`, then test command construction locally; perform a real write only after confirming its target, content, and impact.
