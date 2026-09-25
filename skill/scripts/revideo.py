#!/usr/bin/env python3
"""Run `revideo` from inside the skill, with no manual install.

Where the code comes from, in order:
  1. scripts/lib/revideo      – copy bundled into the packaged .skill (tools/build_skill.py)
  2. ../../src/revideo        – when the skill is used straight from a repo checkout
  3. an installed `revideo`   – `pip install revideo` / `pip install -e .`

Missing Python dependencies are installed with pip on first use:
  always      numpy, opencv-python (<5: 5.x dropped the Haar face detector)
  on demand   yt-dlp (URL input), imageio-ffmpeg (no ffmpeg on PATH → needed for audio)
Set REVIDEO_NO_INSTALL=1 to disable installs. `revideo.py setup` installs everything and runs doctor;
`revideo.py setup --update` also upgrades yt-dlp, whose site extractors change often.
"""

from __future__ import annotations

import importlib.util
import os
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SOURCES = [os.path.join(HERE, "lib"), os.path.normpath(os.path.join(HERE, "..", "..", "src"))]
CORE = {"numpy": "numpy>=1.24", "cv2": "opencv-python>=4.8,<5", "PIL": "pillow>=9"}
URL_DEP = {"yt_dlp": "yt-dlp>=2024.1"}
FFMPEG_DEP = {"imageio_ffmpeg": "imageio-ffmpeg>=0.4"}


def _say(msg: str) -> None:
    print(f"▸ {msg}", file=sys.stderr, flush=True)


def _missing(mods: dict[str, str]) -> list[str]:
    return [spec for mod, spec in mods.items() if importlib.util.find_spec(mod) is None]


def _pip(specs: list[str], upgrade: bool = False) -> bool:
    if not specs:
        return True
    if os.environ.get("REVIDEO_NO_INSTALL"):
        _say(f"missing {', '.join(specs)} (REVIDEO_NO_INSTALL is set, not installing)")
        return False
    _say(f"installing {', '.join(specs)} …")
    base = [
        sys.executable,
        "-m",
        "pip",
        "install",
        "--quiet",
        "--disable-pip-version-check",
        *(["-U"] if upgrade else []),
        *specs,
    ]
    for extra in ([], ["--user"]):  # --user covers read-only system site-packages
        if subprocess.run(base + extra).returncode == 0:
            importlib.invalidate_caches()
            return True
    _say(f"could not install automatically. Run: {sys.executable} -m pip install {' '.join(repr(s) for s in specs)}")
    return False


def _ensure(argv: list[str]) -> bool:
    if not _pip(_missing(CORE)):
        return False
    if argv[:2] == ["setup", "--update"] and not _pip(list(URL_DEP.values()), upgrade=True):
        return False
    wants_all = argv[:1] == ["setup"]
    cmd = argv[0] if argv else ""
    source = next((a for a in argv[1:] if not a.startswith("-")), "")
    needs_url = wants_all or (cmd == "analyze" and source.startswith(("http://", "https://")))
    needs_ffmpeg = wants_all or (cmd == "analyze" and "--no-audio" not in argv and not shutil.which("ffmpeg"))
    optional = (_missing(URL_DEP) if needs_url else []) + (_missing(FFMPEG_DEP) if needs_ffmpeg else [])
    # a URL cannot be fetched without yt-dlp; a missing ffmpeg only skips the audio layer
    return not (optional and not _pip(optional) and needs_url and not wants_all)


def _import_main():
    for src in SOURCES:
        if os.path.isfile(os.path.join(src, "revideo", "cli.py")):
            sys.path.insert(0, src)
            break
    from revideo.cli import main  # imported late: sys.path is set just above

    return main


def run(argv: list[str]) -> int:
    if not _ensure(argv):
        return 2
    main = _import_main()
    return main(["doctor"] if argv[:1] == ["setup"] else argv)


if __name__ == "__main__":
    sys.exit(run(sys.argv[1:]))
