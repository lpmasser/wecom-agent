---
title: Quickstart
description: Install the local dependencies, verify WecomTeam authentication, and run the first safe read.
---

# Quickstart

Start with a read-only local command. Add online operations only after the local path is working and the WecomTeam CLI is authenticated.

## Requirements

- Python 3.10+ on macOS or Windows.
- A running, signed-in WeCom desktop client for local data workflows.
- `pycryptodome` for Windows decryption workflows.
- Node.js and `@wecom/cli` only for online document and sheet operations.

## Clone and verify the project

```bash
git clone https://github.com/tzwkb/wecom-agent.git
cd wecom-agent
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m unittest discover -s tests
```

On Windows, replace `.venv/bin/python` with `.venv\Scripts\python.exe`.

## Run a local read on macOS

<Steps>
  <Step title="Prepare local data">Follow the repository's macOS key and decrypt procedure for your own signed-in WeCom account.</Step>
  <Step title="Refresh chat snapshots">Run `python3 decrypt/macos/read_wecom.py`. This reuses existing keys and does not capture keys or export all messages.</Step>
  <Step title="Query and clean">Run `python3 decrypt/macos/wecom_local.py stats` or a read-only search. After the task, run `python3 decrypt/macos/read_wecom.py --clean` to remove derived chat snapshots while keeping keys.</Step>
</Steps>

```bash
python3 decrypt/macos/wecom_local.py contacts Jackson
python3 decrypt/macos/wecom_local.py conversations
python3 decrypt/macos/wecom_local.py search quarterly
python3 decrypt/macos/wecom_local.py stats
```

See [local reading](/local-reading) for the full command surface and Windows entry points.

## Enable online operations

Install and authenticate the official WecomTeam CLI:

```bash
npm install -g @wecom/cli
wecom-cli auth init
wecom-cli auth show --status
python3 -m online.selfcheck
```

The self-check reports the CLI generation, authentication state, service availability, and Python-wrapper coverage. CLI `1.1+` uses a breaking nested command model; see the [`wecom-cli` migration note](/wecom-cli-migration). An authenticated session does not guarantee that every API category is permitted by the current enterprise.

## Call a confirmed write

```python
from online.docs import create_document

result = create_document("Operations Notes", confirmed=True)
print(result)
```

Without `confirmed=True`, the wrapper raises `PermissionError` before invoking `wecom-cli`.

## Optional MCP facade

On macOS, `bash setup.sh` installs only the local CLI dependencies. Add `--mcp` to install the MCP dependency and register the local server when Claude Code is available. A default install never removes existing MCP packages or registrations. The full `requirements.txt` also remains available for manual MCP/development installations.

```bash
bash setup.sh --mcp
.venv/bin/python server.py
```

Use direct Python or CLI calls when you need the most transparent execution path.
