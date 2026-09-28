"""CMX 3600 edit decision list of the measured cuts, importable into DaVinci Resolve and Premiere Pro.

Each measured shot becomes one event on track V. The source is a placeholder reel per shot
(SHOT001, SHOT002…) so the editor can relink each event to the matching new take; the record side
reproduces the original timing frame-accurately. Beat positions go in as comment lines.
"""

from __future__ import annotations

import json
import os
import re


def _tc(frame: int, fps_i: int) -> str:
    s, ff = divmod(frame, fps_i)
    return f"{s // 3600:02d}:{(s % 3600) // 60:02d}:{s % 60:02d}:{ff:02d}"


def build(r: dict, title: str | None = None) -> str:
    if r.get("kind", "video") != "video":
        raise SystemExit("an EDL needs a video analysis (photos and audio have no cuts)")
    fps = float(r["source"]["video"]["fps"])
    fps_i = max(1, round(fps))
    name = title or r["source"]["platform"].get("title") or os.path.basename(str(r["source"]["input"]))
    safe = re.sub(r"[^A-Za-z0-9 _.-]", "_", name)[:60] or "REVIDEO"
    L = [f"TITLE: {safe}", "FCM: NON-DROP FRAME", ""]
    if abs(fps - fps_i) > 0.01:
        L.append(f"* NOTE: source is {fps} fps; timecode counts {fps_i} frames per second (non-drop)")
    for n, s in enumerate(r["shots"], start=1):
        a, b = int(s["start_frame"]), int(s["end_frame"])
        reel = f"SHOT{n:03d}"
        L.append(f"{n:03d}  {reel:<8} V     C        {_tc(0, fps_i)} {_tc(b - a, fps_i)} {_tc(a, fps_i)} {_tc(b, fps_i)}")
        cam = (s.get("camera") or {}).get("type", "")
        L.append(f"* FROM CLIP NAME: shot_{s['index']:03d} {cam}".rstrip())
        if s.get("transition_in") and s["transition_in"] != "hard_cut":
            L.append(f"* ORIGINAL TRANSITION IN: {s['transition_in']}")
        L.append("")
    beats = (r.get("audio") or {}).get("beat_times") or []
    for t in beats:
        L.append(f"* BEAT {_tc(int(round(float(t) * fps)), fps_i)}")
    return "\n".join(L).rstrip() + "\n"


def parse_events(text: str) -> list[tuple[str, str, str, str]]:
    """(src_in, src_out, rec_in, rec_out) for each event line; used by tests and to sanity-check imports."""
    pat = re.compile(r"^\d{3}\s+\S+\s+V\s+C\s+(\S+) (\S+) (\S+) (\S+)$")
    return [m.groups() for line in text.splitlines() if (m := pat.match(line))]


def write_edl(analysis_dir: str) -> str:
    with open(os.path.join(analysis_dir, "analysis.json"), encoding="utf-8") as f:
        r = json.load(f)
    path = os.path.join(analysis_dir, "edit.edl")
    with open(path, "w", encoding="ascii", errors="replace", newline="\r\n") as f:
        f.write(build(r))
    return path
