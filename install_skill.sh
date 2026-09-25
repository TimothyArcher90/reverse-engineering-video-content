#!/usr/bin/env bash
# Link skill/ into Claude Code's personal skills directory.
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
dest="${CLAUDE_SKILLS_DIR:-$HOME/.claude/skills}/reverse-engineering-video"
mkdir -p "$(dirname "$dest")"
ln -sfn "$here/skill" "$dest"
echo "skill linked → $dest"
echo "dependencies install themselves on first use (or run: python skill/scripts/revideo.py setup)"
