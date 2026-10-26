#!/bin/bash
# WeCom Agent macOS installer. MCP installation/registration is explicit.
# Usage: bash setup.sh [--mcp]
set -e

WITH_MCP=0
for argument in "$@"; do
    case "$argument" in
        --mcp) WITH_MCP=1 ;;
        -h|--help)
            echo "Usage: bash setup.sh [--mcp]"
            echo "Default: local CLI dependencies only. --mcp also installs and registers MCP."
            exit 0 ;;
        *) echo "Unknown argument: $argument" >&2; exit 2 ;;
    esac
done

SKILL_DIR="$(cd "$(dirname "$0")" && pwd)"

if [[ "$(uname)" != "Darwin" ]]; then
    echo "此脚本仅适用于 macOS。"
    exit 1
fi

echo "=== WeCom Agent 安装 (macOS) ==="
echo "目录: $SKILL_DIR"
echo ""

PYTHON="${WECOM_PYTHON:-/opt/homebrew/bin/python3}"
[ -x "$PYTHON" ] || PYTHON="$(command -v python3)"
echo "[1/4] 使用 Python: $PYTHON ($("$PYTHON" --version))"

VENV_DIR="${WECOM_VENV_DIR:-$SKILL_DIR/.venv}"
echo "[2/4] 创建隔离环境: $VENV_DIR"
"$PYTHON" -m venv "$VENV_DIR"
VENV_PYTHON="$VENV_DIR/bin/python"

echo "[3/4] 安装锁定依赖..."
REQUIREMENTS="$SKILL_DIR/requirements-core.txt"
if [[ "$WITH_MCP" == 1 ]]; then
    REQUIREMENTS="$SKILL_DIR/requirements.txt"
fi
"$VENV_PYTHON" -m pip install --quiet -r "$REQUIREMENTS"
"$VENV_PYTHON" -c "import cryptography; print('  local crypto OK')"

if [[ "$WITH_MCP" == 1 ]]; then
    "$VENV_PYTHON" -c "import mcp; print('  mcp OK')"
    echo "[4/4] 注册 MCP Server (wecom)..."
    if command -v claude &>/dev/null; then
        claude mcp remove wecom -s user 2>/dev/null || true
        claude mcp add -s user wecom \
            "$VENV_PYTHON" \
            "$SKILL_DIR/server.py" 2>&1
        echo "  MCP 已注册"
    else
        echo "  Claude Code 未安装,跳过注册；可直接运行 server.py"
    fi
else
    echo "[4/4] 本地 CLI 就绪；未安装或修改 MCP 注册"
fi

echo ""
echo "=== 安装完成 ==="
echo ""
echo "后续步骤:"
echo "  1. 用已有 key 刷新聊天快照: $VENV_PYTHON decrypt/macos/read_wecom.py"
echo "     首次取钥单独执行 find_key_fast.py；脚本不重签客户端或修改系统设置"
echo "  2. 查询: $VENV_PYTHON decrypt/macos/wecom_local.py <子命令> [--json]"
echo "  3. 完成后清理聊天快照: $VENV_PYTHON decrypt/macos/read_wecom.py --clean"
echo "  4. 文档解析可选依赖: $VENV_PYTHON -m pip install -r requirements-documents.txt"
if [[ "$WITH_MCP" == 1 ]]; then
    echo "  MCP 注册完成后，重启对应客户端以加载工具"
fi
