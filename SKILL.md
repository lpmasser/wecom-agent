---
name: wecom-agent
description: Use when 处理企业微信/企微/wecom 任务，包括本地聊天记录解密读取、离线搜索导出、媒体/文档定位，以及通过 WecomTeam 官方 CLI/Bot 能力发消息、查通讯录、读写文档、表格、日程、会议、待办。
allowed-tools: Bash
---

# wecom-agent

本 skill 的主线是 **本地解密读取 + WecomTeam 官方操作层**。

| 线 | 默认方案 | 能力边界 |
|---|---|---|
| **B 本地读取** | 本仓库 `decrypt/` | 历史聊天、离线全文搜索、会话/成员/统计、媒体导出、聊天文件定位。默认优先使用。 |
| **A 主动操作** | WecomTeam `wecom-cli 1.1+` + 本仓库 `online/` | 文档、在线表格、智能主页、智能表格已适配新版；消息、通讯录、日程、会议、待办仍按企业权限探测。 |
| **实时互动** | WecomTeam Bot SDK（后续接入） | WebSocket 收消息、流式回复、主动推送、文件下载解密。 |

旧的自建应用 HTTP API 方案不再是主线；不要为普通 A 线任务要求用户配置 CorpID/Secret/AgentId、可信域名或可信 IP。

## 决策规则

| 用户需求 | 默认调用 |
|---|---|
| 读/导出/搜索历史聊天、统计会话、找本地聊天文件 | B 本地读取 |
| 读任何聊天消息/历史/近期增量 | B 本地读取 |
| 用户明确要求官方在线接口且本地读取不可用 | 按当前 CLI 的 `message` 服务能力处理 |
| 发消息、通知某人/群 | `wecom-cli message ...`；若返回企业不支持授权机器人消息权限，说明该企业不可用 |
| 查人、找 userid | 优先 B 本地通讯录；A 线可用时用 `wecom-cli contact ...` |
| 读/建/改企业微信文档、表格、智能表格 | 优先用 `online/` 或新增 MCP 工具；写操作先确认 |
| 查/建/改/取消日程 | `wecom-cli calendar ...`；若企业不支持则说明权限边界 |
| 查/建/取消会议 | `wecom-cli meeting ...`；若企业不支持则说明权限边界 |
| 查/建/更新/删除待办 | `wecom-cli todo ...`；写操作先确认 |
| 自动回复/流式回复 | Bot SDK；未接入前说明暂未落地 |

**写操作执行前先向用户确认对象、内容和影响范围。**

## A 主动操作（WecomTeam CLI）

首次使用先检查并初始化：

```bash
wecom-cli --version || npm install -g @wecom/cli
wecom-cli auth show --status
wecom-cli auth init
```

通用格式：

```bash
wecom-cli <service> [resource...] <method> --json '<json参数>'
```

常用入口：

| category | 例子 |
|---|---|
| `doc` | `wecom-cli doc contents get --json '{"docid":"DOCID","content_type":"markdown"}'` |
| `sheet` | `wecom-cli sheet ranges get --json '{"docid":"DOCID","sheet_id":"SHEETID","mode":"default","range":"A1:D100"}'` |
| `smartsheet` | `wecom-cli smartsheet records list --json '{"docid":"DOCID","sheet_title":"子表名","limit":100}'` |
| `todo` | 先用 `wecom-cli todo --help` 核对当前命令和参数 |
| `contact` / `message` / `calendar` / `meeting` | 权限按企业环境实测；遇到明确权限错误时不要继续重试 |

遇到具体参数不确定时，优先查 `wecom-cli <category> --doc` 或 WecomTeam/wecom-cli 对应的 `skills/wecomcli-*/references`。

会议纪要和待办来自 `meeting get`；逐句原文来自 `meeting original get`，不能互相替代。直接复用官方 CLI 的 `--page-count N --output 文件` 自动分页与原始响应落盘（NDJSON，每行一页），检查末页 `has_more`；若仍为 true，沿 `next_cursor` 继续，不把页数上限当作完整结果。保留会议/子会议标识、原时间和发言人。多录音段的范围按当前 `--doc` 与实际响应确认，无法确认时明确说明，不猜测段数。

## A 在线文档/表格

本仓库 `online/` 是 `wecom-cli` 的薄封装。写操作全部需要 `confirmed=True`。

```bash
PY=${WECOM_PYTHON:-/opt/homebrew/bin/python3}
$PY -m online.selfcheck
```

| 模块 | 能力 |
|---|---|
| `online.docs` | 新旧 CLI 普通文档创建/覆写；CLI `1.1+` 读取正文、创建/导入智能主页 |
| `online.local_docs` | 读取本地已缓存/已下载文档，作为线上读取接口缺失时的 fallback |
| `online.sheets` | 新旧 CLI 创建/读取/修改在线表格；CLI `1.1+` 读取单元格范围 |
| `online.smartsheets` | 新旧 CLI 创建和管理智能表格；CLI `1.1+` 读取记录 |

`wecom-cli 1.1+` 的命令和 payload 与 `0.1.x` 不兼容。运行 `python3 -m online.selfcheck` 后按 `generation` 路由。结构化旧版智能主页 `pages` 无法无损转换，新版应使用 Markdown 导入。本地缓存 fallback 仍可能落后于线上最新版。

## B 本地读取聊天记录

按系统分流：macOS → `decrypt/macos/`，Windows → `decrypt/windows/`。解密核心 `decrypt/wxwork_crypto.py` 与解析 `decrypt/export_wxwork.py` 两端共用。

### macOS

首次抓 key 需要企业微信运行并登录，签名条件见 `docs/解密思路.md`。已有有效密钥时直接离线刷新，不需要重签或扫描内存。

```bash
PY=${WECOM_PYTHON:-/opt/homebrew/bin/python3}
$PY decrypt/macos/read_wecom.py
# 缺钥时停止；需要首次取钥才单独运行（不自动重签或改系统设置）
$PY decrypt/macos/find_key_fast.py
# 可选：刷新聊天以外的全部本地数据库（例如本地 todo/calendar）
$PY decrypt/macos/decrypt_wxwork.py
```

`read_wecom.py` 默认只用已有密钥刷新 Info.db 和 Session.db，不再自动取钥或全量导出。全量 JSON/CSV 导出显式用 `read_wecom.py --export <目录>`，单个会话继续用下方 `export`。查询任务完成后用 `read_wecom.py --clean` 删除可重建的聊天快照和 SQLite sidecar；密钥、原始库、用户导出和其他文件保留。

新安装的 macOS 密钥和快照默认在 `~/.local/share/wecom-agent/<profile>/`，可用 `WECOM_STATE_DIR` 改父目录、`WECOM_KEYS_FILE` 指定已有密钥文件；显式配置不回退到其他路径。未指定新路径时仍复用原有源码目录内的密钥／快照。取钥只显示命中目标，不打印密钥；临时编译的扫描库自动清理。

本地查询：

```bash
$PY decrypt/macos/wecom_local.py <contacts|conversations|members|search|stats|todo|calendar|media|openfile>
```

| 子命令 | 作用 |
|---|---|
| `contacts [词]` | 本地通讯录搜索 |
| `conversations` | 会话列表 |
| `members <会话>` | 群成员与发言数 |
| `search <词> [--conversation <会话ID或唯一名称>]` | 全文搜索；已知会话时限定范围 |
| `chat <会话ID> [--days N] [--limit N] [--offset N]` | 按唯一会话读取消息，最新在前；常见凭据在返回前遮盖 |
| `export <会话ID> --out 文件 [--with-media]` | 导出 TXT/Markdown/HTML/JSON/CSV，附逐消息媒体清单 |
| `stats` | 发言/会话/类型/时间统计 |
| `todo` / `calendar` | 本地待办 / 日程 |
| `media [--out]` | 导出明文缓存图片和文件 |
| `openfile <名/词>` | 从聊天记录定位并解析本地文件 |

`conversations`、`search`、`chat` 支持 `--limit 1..2000 --offset N --json`；`search`、`chat`、`export` 的 `--days` 必须为正整数，不传则覆盖全部日期。CLI 的会话列表与搜索不传 limit 时保留全量行为，MCP 默认分别返回 100、50 条。消息正文不截断。名称重名时必须使用返回的会话 ID，不合并群成员。

定位联系人用 `contacts` / `conversations` 元数据，不用跨会话正文搜索找人。查指定会话内的需求或关键词时给 `search` 传 `--conversation`，MCP 对应参数为 `conversation`；仅在用户授权跨会话搜索时省略。不要先全量输出再用 `head` 代替范围控制或脱敏。

`chat` / `search` 的共同查询出口默认用 `[REDACTED]` 遮盖常见凭据（具名 API key、密码/口令、连接串口令、常见 token 和私钥块），文本、JSON 和 MCP 同样生效；被改动的消息带 `content_redacted=true`，来源 ID、人物和时间保留。规则不能保证识别所有无标签、混淆或未知格式的秘密。原始库及显式本地导出不改写，不能把未脱敏导出直接交给模型或打印。需要未知格式原文时先在本机检查和遮盖，再提供必要片段。

`export --with-media` 用企微消息资源标识关联缓存，生成 `<stem>.media.json` 与 `<stem>.assets-<export-id>/`。只导出所选会话/日期范围的媒体；同名文件按资源 ID 区分；缺失、加密或歧义明确标注。具体 schema 和边界见 [本地读取与导出](docs/local-reading.md)。

多账号必须指定 `WECOM_PROFILE`（macOS profile 目录）或 `WECOM_DATA_DIR`（Windows Data 目录）。迁移解密库可用 `WECOM_DECRYPTED_DIR`，独立缓存可用 `WECOM_CACHE_DIR`；无有效配置时不自动切换到其他账号。消息库只读打开，解密使用已提交主库/WAL 快照，并在校验通过后原子替换旧输出。

可选语音转写：

```bash
$PY decrypt/macos/voice_transcribe.py
```

### Windows

前提：企业微信运行并登录，安装 Python 与 `pycryptodome`。

```powershell
powershell -ExecutionPolicy Bypass -File decrypt/windows/run.ps1 <子命令>
powershell -ExecutionPolicy Bypass -File decrypt/windows/run_test.ps1
powershell -ExecutionPolicy Bypass -File decrypt/windows/find_key.ps1
python decrypt/windows/wecom_win.py <key> <子命令>
```

## MCP（可选）

本地读取 MCP 只是 `wecom_local.py --json` 的薄门面。不要为了本地查询强制走 MCP；直接跑 CLI 更透明。

```bash
bash setup.sh --mcp
```

`bash setup.sh` 默认只安装本地 CLI 依赖，不修改 MCP 注册；确实需要 MCP 才传 `--mcp`。已有安装不会因省略该选项而被卸载。

本地读取工具：`wecom_contacts/conversations/members/search/stats/todo/calendar/media/openfile`，以及 `wecom_read_chat`、`wecom_export_chat`。

本地文档 fallback：

| 工具 | 作用 |
|---|---|
| `wecom_local_doc_read_path` | 按本地路径解析文件，支持 txt/csv/md/json/xlsx/xls/docx/pdf，图片型内容返回 visual 标记 |
| `wecom_local_doc_search` | 按文件名关键词在 WeCom 文件缓存、Downloads、Documents、Desktop 中查找并解析 |

在线工具：

| 工具 | 作用 |
|---|---|
| `wecom_doc_create` / `wecom_doc_write_markdown` | 创建普通文档、覆写 Markdown 正文 |
| `wecom_doc_read` | CLI `1.1+` 读取线上普通文档最新版正文 |
| `wecom_smartpage_create` / `wecom_smartpage_import` | 创建空智能主页 / 导入 Markdown 智能主页 |
| `wecom_sheet_create` / `wecom_sheet_info` | 创建在线表格、读取表结构 |
| `wecom_sheet_get_range` | CLI `1.1+` 读取在线表格单元格范围 |
| `wecom_sheet_add_sub` / `wecom_sheet_delete_sub` | 新增/删除在线表格子表 |
| `wecom_sheet_append_row` / `wecom_sheet_update_range` | 追加行、更新区域 |
| `wecom_smartsheet_create` / `wecom_smartsheet_sheets` / `wecom_smartsheet_fields` | 创建智能表格、读取子表/字段 |
| `wecom_smartsheet_records` | CLI `1.1+` 读取智能表格记录 |
| `wecom_smartsheet_add_*` / `update_*` / `delete_*` | 管理智能表格子表、字段、记录 |

## 状态

- **B 本地读取**：已实跑验证，覆盖本地历史聊天、会话、发送者、文本/图片/语音/文件/文档/卡片等解析。
- **A 主动操作**：普通文档、在线表格和智能表格已适配 CLI `0.1.x` 与 `1.1+`；新版支持智能主页创建/Markdown 导入。2026-09-01 本机已升级到 `1.2.0` 且授权仍有效；尚未执行真实线上写入验收。
- **实时互动**：后续接 WecomTeam Bot SDK；旧回调实验代码在 `legacy/self-built-app/`。
