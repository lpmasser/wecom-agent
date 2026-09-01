#!/bin/bash
# WeCom Agent Skill + MCP Server — macOS installer
# Usage: bash setup.sh
set -e

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
"$VENV_PYTHON" -m pip install --quiet -r "$SKILL_DIR/requirements.txt"
"$VENV_PYTHON" -c "import mcp; print('  mcp OK')" 2>/dev/null || {
    echo "  [!] 安装失败: $VENV_PYTHON -m pip install -r $SKILL_DIR/requirements.txt"
    exit 1
}

echo "[4/4] 注册 MCP Server (wecom)..."
if command -v claude &>/dev/null; then
    claude mcp remove wecom -s user 2>/dev/null || true
    claude mcp add -s user wecom \
        "$VENV_PYTHON" \
        "$SKILL_DIR/server.py" 2>&1
    echo "  MCP 已注册"
else
    echo "  Claude Code 未安装,跳过"
fi

echo ""
echo "=== 安装完成 ==="
echo ""
echo "后续步骤:"
echo "  1. 提 key + 解密: $VENV_PYTHON decrypt/macos/read_wecom.py (扫 key→解密→导出)"
echo "  2. 重启 Claude Code → MCP 工具 wecom_* 可用"
echo "  3. 不用 MCP 也行: $VENV_PYTHON decrypt/macos/wecom_local.py <子命令> [--json]"
echo "  4. 文档解析可选依赖: $VENV_PYTHON -m pip install -r requirements-documents.txt"
