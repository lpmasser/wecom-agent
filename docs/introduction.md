---
title: WeCom Agent
description: Local WeCom history access and confirmed online document operations from one Python project.
---

# WeCom Agent

WeCom Agent combines local access to a user's own WeCom data with a thin operation layer over the official WecomTeam CLI. Use the local track for historical chat search, exports, statistics, and file discovery. Use the online track for supported document and sheet operations.

<CardGroup cols={2}>
  <Card title="Local reading" icon="magnifying-glass" href="/local-reading">Search chats, inspect conversations, export media, and locate downloaded documents on the current device.</Card>
  <Card title="Online documents" icon="document-text" href="/online-documents">Create, read, and update supported WeCom documents through an authenticated WecomTeam CLI session.</Card>
  <Card title="Sheets" icon="chart-bar" href="/online-sheets">Create sheets, read cell ranges, append rows, and update values.</Card>
  <Card title="Safety model" icon="shield-check" href="/security">Keep reads local and require explicit confirmation for every online write.</Card>
</CardGroup>

## Two operating tracks

| Track | Default implementation | Best for |
|---|---|---|
| Local reading | `decrypt/` | Historical chats, contacts, conversations, full-text search, statistics, media export, and local file discovery |
| Online operations | `online/` plus `wecom-cli` | Documents, online sheets, smart sheets, and other APIs permitted by the current enterprise |

The legacy self-built application under `legacy/self-built-app/` is retained for reference, but it is not the primary path.

## Current capability boundary

The repository wraps document, online sheet, and smart sheet operations. The exact online surface still depends on the installed `wecom-cli` version and the permissions granted by the user's enterprise.

CLI `1.1+` introduced a breaking nested command model and added online reads for normal document bodies, sheet cells, and smart-sheet records. The repository translates current document, standard-sheet, smart-page, and smart-sheet operations. Structured legacy smart-page `pages` still fail closed because the new service only supports an empty create or Markdown import. See the [`wecom-cli` migration note](/wecom-cli-migration).

## Non-negotiable safety rule

Use the project only with data and accounts the operator is authorized to access. Every wrapped online write rejects execution until the caller passes `confirmed=True` after confirming the target, content, and impact.

## Project layout

```text
decrypt/                 Local decrypt, parse, search, and export tools
online/                  WecomTeam CLI wrappers
server.py                MCP facade for local and online tools
legacy/self-built-app/   Historical experiments
docs/                    Design notes and user documentation
tests/                   Unit tests
```

Continue with the [quickstart](/quickstart) for a minimal verified setup.
