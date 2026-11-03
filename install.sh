#!/usr/bin/env bash
# 把 skills/x-voice-zh 复制到你的 AI 编程助手的 skills 目录。
# 用法:
#   ./install.sh claude           # 装到 ~/.claude/skills/x-voice-zh（Claude Code，全局）
#   ./install.sh claude-project   # 装到当前目录的 .claude/skills/x-voice-zh
#   ./install.sh codex            # 装到 ~/.codex/skills/x-voice-zh（Codex，路径请按你的版本核对）
#   ./install.sh /自定义/目录      # 装到 /自定义/目录/x-voice-zh
set -euo pipefail
SRC="$(cd "$(dirname "$0")" && pwd)/skills/x-voice-zh"
case "${1:-}" in
  claude) DEST_DIR="$HOME/.claude/skills" ;;
  claude-project) DEST_DIR="$PWD/.claude/skills" ;;
  codex) DEST_DIR="${CODEX_HOME:-$HOME/.codex}/skills" ;;
  ""|-h|--help) sed -n '2,8p' "$0"; exit 0 ;;
  *) DEST_DIR="$1" ;;
esac
mkdir -p "$DEST_DIR"
rm -rf "$DEST_DIR/x-voice-zh"
cp -R "$SRC" "$DEST_DIR/x-voice-zh"
find "$DEST_DIR/x-voice-zh" -name __pycache__ -type d -prune -exec rm -rf {} +
echo "已安装到 $DEST_DIR/x-voice-zh"
echo "重启或新开一个会话，然后说：「用 x-voice-zh 学我的语气」"
