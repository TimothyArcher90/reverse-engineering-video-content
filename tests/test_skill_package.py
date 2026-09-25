"""The packaged .skill must run on its own: bundled source, launcher, one SKILL.md."""

import os
import subprocess
import sys
import zipfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))
import build_skill  # noqa: E402


def test_skill_package_is_self_contained(tmp_path, edit_video):
    archive = build_skill.build(str(tmp_path / "dist"))
    names = zipfile.ZipFile(archive).namelist()
    root = build_skill.NAME
    assert f"{root}/SKILL.md" in names
    assert f"{root}/scripts/revideo.py" in names
    assert f"{root}/scripts/lib/revideo/cli.py" in names
    assert sum(n.endswith("SKILL.md") for n in names) == 1
    assert not any("__pycache__" in n for n in names)

    unpacked = tmp_path / "installed"
    zipfile.ZipFile(archive).extractall(unpacked)
    launcher = unpacked / root / "scripts" / "revideo.py"
    env = {**os.environ, "REVIDEO_NO_INSTALL": "1", "PYTHONPATH": ""}  # prove it uses the bundled copy
    out = tmp_path / "run"
    r = subprocess.run(
        [sys.executable, str(launcher), "analyze", edit_video, "-o", str(out), "--no-audio", "--no-motion", "--quiet"],
        env=env,
        cwd=tmp_path,
        capture_output=True,
        text=True,
    )
    assert r.returncode == 0, r.stderr
    assert (out / "analysis.json").exists() and (out / "report.html").exists()
