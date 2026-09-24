#!/usr/bin/env bash
# Link skill/ into Claude Code's personal skills directory.
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
dest="${CLAUDE_SKILLS_DIR:-$HOME/.claude/skills}/reverse-engineering-video"
mkdir -p "$(dirname "$dest")"
ln -sfn "$here/skill" "$dest"
echo "skill linked → $dest"
command -v revideo >/dev/null || echo "note: run 'pip install -e \".[full]\"' so the skill can call revideo"
