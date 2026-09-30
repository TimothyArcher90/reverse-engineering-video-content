"""Vertical reframe plan: a 9:16 crop window per shot that follows the measured subject.

The anchor is the largest detected face when there is one, else the visual-weight center of the
frame [M]. Keeping that anchor inside the crop is a heuristic [I]: check the storyboard frames before
rendering, and hand-key any shot where the subject moves across the frame.
"""

from __future__ import annotations

import csv
import json
import os

TARGET = 9 / 16
COLUMNS = ["shot", "in_tc", "out_tc", "anchor", "subject_x_norm", "crop_x", "crop_y", "crop_w", "crop_h", "ffmpeg_filter"]


def _even(v: float) -> int:
    return max(2, int(round(v / 2)) * 2)


def plan(r: dict, out_w: int = 1080, out_h: int = 1920) -> dict:
    if r.get("kind", "video") != "video":
        raise SystemExit("reframe needs a video analysis")
    v = r["source"]["video"]
    rows = []
    for s in r["shots"]:
        x0, y0, x1, y1 = (s.get("active_area") or {}).get("box") or [0, 0, v["width"], v["height"]]
        aw, ah = x1 - x0, y1 - y0
        fr = s.get("framing") or {}
        face = (fr.get("faces") or {}).get("largest_center_norm")
        cx = (face or fr.get("visual_center_norm") or [0.5, 0.5])[0]
        anchor = "face" if face else "visual_weight" if fr.get("visual_center_norm") else "center"
        cw, ch = min(aw, _even(ah * TARGET)), _even(ah)
        x = int(round(min(max(x0 + cx * aw - cw / 2, x0), x1 - cw)))
        rows.append(
            {
                "shot": s["index"],
                "in_tc": s["start_tc"],
                "out_tc": s["end_tc"],
                "anchor": anchor,
                "subject_x_norm": round(cx, 3),
                "crop_x": x,
                "crop_y": y0,
                "crop_w": cw,
                "crop_h": ch,
                "ffmpeg_filter": f"crop={cw}:{ch}:{x}:{y0},scale={out_w}:{out_h}",
            }
        )
    source_ar = v["width"] / max(1, v["height"])
    return {
        "needed": source_ar > TARGET * 1.05,
        "source_aspect_ratio": round(source_ar, 3),
        "output": [out_w, out_h],
        "shots": rows,
    }


def plan_lines(rp: dict) -> list[str]:
    if not rp["needed"]:
        return [f"- Source is already vertical (AR {rp['source_aspect_ratio']}): no reframe needed."]
    L = [
        f"- Source AR {rp['source_aspect_ratio']} → 9:16 at {rp['output'][0]}×{rp['output'][1]}; "
        "one crop window per shot, full list in `reframe.csv` [I]",
        "",
        "| Shot | Anchor | Subject x | ffmpeg filter |",
        "|---|---|---|---|",
    ]
    L += [f"| {x['shot']} | {x['anchor']} | {x['subject_x_norm']} | `{x['ffmpeg_filter']}` |" for x in rp["shots"]]
    L.append('- Apply per shot: `ffmpeg -ss <in> -to <out> -i source.mp4 -vf "<filter>" shot_NN.mp4`')
    return L


def write_reframe(analysis_dir: str) -> str | None:
    with open(os.path.join(analysis_dir, "analysis.json"), encoding="utf-8") as f:
        rp = plan(json.load(f))
    if not rp["needed"]:
        return None
    path = os.path.join(analysis_dir, "reframe.csv")
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNS)
        w.writeheader()
        w.writerows(rp["shots"])
    return path
