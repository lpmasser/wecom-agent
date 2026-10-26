# WeCom Agent

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Agent Skill](https://img.shields.io/badge/Agent%20Skill-Codex-blue.svg)](SKILL.md)
[![Python](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)
[![CI](https://github.com/tzwkb/wecom-agent/actions/workflows/ci.yml/badge.svg)](https://github.com/tzwkb/wecom-agent/actions/workflows/ci.yml)

[Documentation](https://wecom-agent.readthedocs.io/en/latest/) | [English](README.md) | 中文

**Agent Skill** — 企业微信本地解密读取 + WecomTeam 官方 CLI/Bot 操作助手，支持历史聊天读取、通讯录/会话搜索、媒体/文档定位、待办和在线文档/表格流程。

## 能力

| 线 | 能力 | 状态 |
|---|---|---|
| **B 本地读取** | 解密导出聊天记录、增量监控、通讯录/会话/全文搜索/统计画像、语音转写、媒体导出 | 已可用 |
| **A 在线操作** | 通过 WecomTeam `wecom-cli` 操作文档、在线表格、智能表格、待办等在线 API | 分模块可用，受企业权限限制 |
| **实时互动** | WecomTeam Bot SDK WebSocket 收消息、回复、推送 | 后续接入 |

旧自建应用 HTTP API 不再是主线。历史聊天读取默认走本地解密；在线写操作默认复用 WecomTeam `wecom-cli`。

## 快速开始：本地读取

前提：企业微信已登录；首次抓 key 需要按 `docs/解密思路.md` 处理 macOS 签名限制。

```bash
PY=/opt/homebrew/bin/python3
$PY decrypt/macos/read_wecom.py
$PY decrypt/macos/wecom_local.py stats
$PY decrypt/macos/wecom_local.py contacts 张
$PY decrypt/macos/wecom_local.py search 报价
$PY decrypt/macos/wecom_local.py conversations --limit 100 --offset 0 --json
$PY decrypt/macos/wecom_local.py chat <会话ID> --days 7 --limit 50 --json
$PY decrypt/macos/wecom_local.py export <会话ID> --out decrypt/macos/export/chat.html --with-media
$PY decrypt/macos/wecom_local.py members <会话ID>
$PY decrypt/macos/monitor.py --poll 30
$PY decrypt/macos/voice_transcribe.py
```

查询保留完整正文和换行；MCP 会话与消息查询支持分页。会话名称重名时会列出候选 ID，不会合并多个群。导出支持 TXT、Markdown、HTML、JSON、CSV；`--with-media` 按消息资源标识定位本地图片、文件、语音和表情，生成逐消息清单及独立媒体目录。缺失、加密、同标识不同内容和未知格式均明确标注，详见 [本地读取与导出](docs/local-reading.md)。

macOS 的 `read_wecom.py` 现在默认只用已有密钥刷新聊天库和姓名库，缺钥时停止，不自动扫描或全量导出。首次取钥显式运行 `find_key_fast.py`；全量 JSON/CSV 导出用 `read_wecom.py --export <目录>`；任务结束用 `read_wecom.py --clean` 清理聊天快照及 SQLite sidecar，保留密钥、原始库和导出。需要本地待办／日程等其他库时显式运行 `decrypt_wxwork.py`。

多账号请明确设置 macOS `WECOM_PROFILE` 或 Windows `WECOM_DATA_DIR`；移动后的解密库与缓存可分别通过 `WECOM_DECRYPTED_DIR`、`WECOM_CACHE_DIR` 指定。

新安装的 macOS 运行数据默认位于 `~/.local/share/wecom-agent/<profile>/`；`WECOM_STATE_DIR` 可改父目录，`WECOM_KEYS_FILE` 可指定已有密钥文件。未指定新路径时仍复用已有源码目录内的密钥／快照，取钥命令不打印密钥值。

## 在线文档和表格

```bash
npm install -g @wecom/cli
wecom-cli auth init
wecom-cli auth show --status

$PY -m online.selfcheck
```

已实现封装：

- `online.docs`：创建/读取普通文档、Markdown 覆写正文、创建或导入智能主页；结构化旧版智能文档 payload 仅保留给 CLI `0.1.x`。
- `online.local_docs`：读取本地已缓存/已下载的文档，作为 `get_doc_content` 缺失时的 fallback。
- `online.sheets`：创建在线表格、读取表结构和单元格范围、新增/删除子表、追加行、更新区域。
- `online.smartsheets`：跨新旧 CLI 创建智能表格、管理子表/字段/记录，并在新版读取记录。

`wecom-cli 1.1+` 引入了破坏性的多级命令模型，并补齐在线文档、在线表格、智能主页和智能表格服务。封装会自动识别版本并转换新版 payload；无法无损映射的旧版结构化智能主页 `pages` 仍会安全拒绝，应改用 Markdown 导入。详见 [CLI 迁移说明](docs/wecom-cli-migration.md)。

## MCP

```bash
bash setup.sh
```

MCP 保留本地读取工具：`wecom_contacts/conversations/members/search/stats/todo/calendar/media/openfile`，新增 `wecom_read_chat`、`wecom_export_chat`，并提供 `wecom_local_doc_read_path`、`wecom_local_doc_search` 读取本地缓存/下载文档。

在线读取工具包括 `wecom_doc_read`、`wecom_sheet_get_range` 与 `wecom_smartsheet_records`；创建、导入、覆写、追加、更新等线上写操作仍必须传 `confirmed=True`。

`setup.sh` 会根据锁定的 [requirements.txt](requirements.txt) 创建隔离 `.venv`；本地文档解析的可选依赖见 [requirements-documents.txt](requirements-documents.txt)。

## 开发验证

```bash
python3 -m pip install -r requirements-dev.txt
python3 -m unittest discover -s tests -v
python3 -m compileall -q server.py online decrypt tests
ruff check online server.py tests
pip-audit -r requirements.txt
npm ci && npm run docs:build -- --output /tmp/wecom-agent-docs --quiet
```

## 结构

```text
decrypt/                          B 线本地解密读取核心
online/                           A 线 WecomTeam CLI 薄封装
server.py                         MCP 薄门面
legacy/self-built-app/            旧自建应用实验代码
docs/                             设计、状态和开发文档
tests/                            单元测试
```

## 隐私与安全

- 仅读本人设备本人账号。
- 解密产物、密钥、凭证和运行时数据均 `.gitignore`，不入库。
- 任何线上写操作必须先确认对象、内容和影响范围。
