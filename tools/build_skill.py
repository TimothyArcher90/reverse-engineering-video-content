"""Build a self-contained skill: dist/reverse-engineering-video/ and dist/reverse-engineering-video.skill.

The .skill file is a zip with the skill folder at its root. It bundles the revideo source under
scripts/lib/, so it runs without cloning this repo: upload it in claude.ai (Settings → Capabilities
→ Skills) or unzip it into ~/.claude/skills/ for Claude Code.

    python tools/build_skill.py            # → dist/
"""

from __future__ import annotations

import os
import shutil
import sys
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NAME = "reverse-engineering-video"
SKIP = shutil.ignore_patterns("__pycache__", "*.pyc", ".DS_Store")


def build(out_dir: str = os.path.join(ROOT, "dist")) -> str:
    stage = os.path.join(out_dir, NAME)
    shutil.rmtree(stage, ignore_errors=True)
    shutil.copytree(os.path.join(ROOT, "skill"), stage, ignore=SKIP)
    shutil.copytree(os.path.join(ROOT, "src", "revideo"), os.path.join(stage, "scripts", "lib", "revideo"), ignore=SKIP)
    shutil.copy(os.path.join(ROOT, "LICENSE"), os.path.join(stage, "LICENSE"))

    archive = os.path.join(out_dir, f"{NAME}.skill")
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as z:
        for folder, _, files in os.walk(stage):
            for f in sorted(files):
                path = os.path.join(folder, f)
                z.write(path, os.path.relpath(path, out_dir).replace(os.sep, "/"))
    return archive


if __name__ == "__main__":
    path = build(*sys.argv[1:2])
    print(f"built {path} ({os.path.getsize(path) // 1024} KB)")
