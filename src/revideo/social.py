"""Short-form (Reels / TikTok / Shorts) measurements: on-screen text, hook, safe zones, loop.

Text detection here is a classical heuristic (dense vertical strokes in a horizontal band),
chosen to avoid heavy OCR dependencies. It finds *where and when* text is, not what it says; the
agent reads the words from the keyframes. Safe-zone presets are unverified (see data/platforms.json).
"""

from __future__ import annotations

import json
from importlib import resources

import cv2
import numpy as np

from .video import iter_frames

VERTICAL_AR = 9 / 16


def load_presets() -> dict:
    with resources.files("revideo").joinpath("data/platforms.json").open(encoding="utf-8") as f:
        return json.load(f)


def text_regions(frame: np.ndarray, width: int = 480) -> list[list[float]]:
    """Boxes [x0, y0, x1, y1] (0–1) of likely overlay text: rows of dense, high-contrast vertical strokes."""
    h0, w0 = frame.shape[:2]
    s = width / w0
    g = cv2.cvtColor(cv2.resize(frame, (width, max(1, int(h0 * s))), interpolation=cv2.INTER_AREA), cv2.COLOR_BGR2GRAY)
    h, w = g.shape
    gx = np.abs(cv2.Sobel(g, cv2.CV_32F, 1, 0, ksize=3))
    edges = (gx > 120).astype(np.uint8)  # strong vertical edges: letter stems against contrasting fill/outline
    joined = cv2.morphologyEx(edges, cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_RECT, (max(3, w // 40), 3)))
    n, _, stats, _ = cv2.connectedComponentsWithStats(joined, connectivity=8)
    boxes = []
    for i in range(1, n):
        x, y, bw, bh, _ = stats[i]
        if not (0.015 * h <= bh <= 0.15 * h and bw >= 2.5 * bh and bw >= 0.08 * w):
            continue
        density = edges[y : y + bh, x : x + bw].mean()
        if 0.08 <= density <= 0.6:  # letters: many stems, but not a solid texture
            boxes.append([round(float(v), 3) for v in (x / w, y / h, (x + bw) / w, (y + bh) / h)])
    return boxes


def _violations(boxes: list[list[float]], m: dict) -> int:
    return sum(b[0] < m["left"] or b[2] > 1 - m["right"] or b[1] < m["top"] or b[3] > 1 - m["bottom"] for b in boxes)


def _tiny(frame: np.ndarray) -> np.ndarray:
    t = cv2.resize(cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY), (48, 48), interpolation=cv2.INTER_AREA).astype(np.float32)
    return (t - t.mean()) / (t.std() + 1e-6)


def analyze(path: str, info, shots: list, max_samples: int = 150) -> dict:
    """Sample 4 fps in the first 3 s (the hook) and ~1 fps after, capped at `max_samples` frames."""
    fps = info.fps or 25.0
    n = max(1, info.frame_count)
    hook_end = min(n, int(round(3 * fps)))
    idx = set(range(0, hook_end, max(1, int(round(fps / 4)))))
    idx |= set(range(hook_end, n, max(1, int(round(fps)))))
    idx.add(n - 1)
    idx = sorted(idx)
    if len(idx) > max_samples:
        idx = [idx[int(i)] for i in np.linspace(0, len(idx) - 1, max_samples)]
    want = set(idx)

    samples, prev, energy = [], None, []
    first = last = None
    for i, f in iter_frames(path, 1, max_side=640):
        if i not in want:
            continue
        g = cv2.cvtColor(cv2.resize(f, (160, int(160 * f.shape[0] / f.shape[1]) or 1)), cv2.COLOR_BGR2GRAY).astype(np.float32)
        energy.append((i / fps, float(np.abs(g - prev).mean()) if prev is not None and prev.shape == g.shape else 0.0))
        prev = g
        samples.append((i / fps, text_regions(f)))
        first = f if first is None else first
        last = f

    with_text = [(t, b) for t, b in samples if b]
    presets = load_presets()
    ar = info.width / max(1, info.height)
    vertical = abs(ar - VERTICAL_AR) / VERTICAL_AR < 0.03
    safe = {}
    all_boxes = [b for _, bs in with_text for b in bs]
    for key, p in presets["presets"].items():
        bad = _violations(all_boxes, p["margins"]) if all_boxes else 0
        safe[key] = {
            "label": p["label"],
            "text_boxes": len(all_boxes),
            "outside_safe_zone": bad,
            "applies": vertical,
            "first_violation_sec": next((round(t, 2) for t, bs in with_text if _violations(bs, p["margins"])), None),
        }

    bands = {"top": 0, "middle": 0, "bottom": 0}
    for b in all_boxes:
        cy = (b[1] + b[3]) / 2
        bands["top" if cy < 1 / 3 else "middle" if cy < 2 / 3 else "bottom"] += 1

    hook_e = [e for t, e in energy[1:] if t < 3]
    rest_e = [e for t, e in energy[1:] if t >= 3]
    cuts_hook = sum(1 for s in shots[1:] if s.start_sec < 3)
    loop = float((_tiny(first) * _tiny(last)).mean()) if first is not None and last is not None else None

    return {
        "format": {
            "aspect_ratio": round(ar, 4),
            "is_9_16": vertical,
            "resolution": [info.width, info.height],
            "full_hd_vertical": vertical and info.height >= 1920,
        },
        "on_screen_text": {
            "first_text_sec": round(with_text[0][0], 2) if with_text else None,
            "text_in_first_second": bool(with_text and with_text[0][0] < 1.0),
            "frames_with_text_share": round(len(with_text) / max(1, len(samples)), 3),
            "position_bands": bands,
            "timeline": [{"t": round(t, 2), "boxes": b} for t, b in with_text[:60]],
            "note": "heuristic stroke detector: finds where/when text is, not what it says",
        },
        "hook": {
            "cuts_in_first_3s": cuts_hook,
            "motion_energy_first_3s": round(float(np.mean(hook_e)), 2) if hook_e else None,
            "motion_energy_rest": round(float(np.mean(rest_e)), 2) if rest_e else None,
            "hook_vs_rest_energy": round(float(np.mean(hook_e) / (np.mean(rest_e) + 1e-6)), 2) if hook_e and rest_e else None,
        },
        "safe_zones": safe,
        "safe_zone_presets_verified": presets["verified"],
        "loop": {
            "first_last_similarity": round(loop, 3) if loop is not None else None,
            "loop_guess": None if loop is None else "seamless loop likely" if loop > 0.85 else "no loop",
        },
        "samples": len(samples),
    }


def advice(s: dict | None) -> list[str]:
    """Plan lines for short-form delivery, derived from the measurements above."""
    if not s:
        return []
    f, t, h, lp = s["format"], s["on_screen_text"], s["hook"], s["loop"]
    if f["is_9_16"]:
        fmt = "Format: 9:16 ✓" + (
            "" if f["full_hd_vertical"] else f" · source is {f['resolution'][0]}×{f['resolution'][1]}: deliver 1080×1920"
        )
    else:
        fmt = f"Format: AR {f['aspect_ratio']} → reframe to 9:16 (1080×1920) for Reels/TikTok"
    text_at = f"at {t['first_text_sec']} s" if t["first_text_sec"] is not None else "absent"
    energy = f", motion in the hook ×{h['hook_vs_rest_energy']} vs the rest" if h["hook_vs_rest_energy"] else ""
    out = [
        fmt,
        f"Hook (0–3 s): {h['cuts_in_first_3s']} cut(s), on-screen text {text_at}{energy} [M]. "
        "Replicate the same beat: first visual change and first words on screen at the same times.",
        f"Text on screen in {round(t['frames_with_text_share'] * 100)} % of sampled frames; placement {t['position_bands']} [M].",
    ]
    for p in s["safe_zones"].values():
        if p["applies"] and p["outside_safe_zone"]:
            out.append(
                f"⚠ {p['outside_safe_zone']}/{p['text_boxes']} text boxes fall outside the {p['label']} safe zone "
                f"(first at {p['first_violation_sec']} s): move them inward. "
                "Preset unverified: check the platform's current template."
            )
    out.append(
        f"Loop: first/last frame similarity {lp['first_last_similarity']} → {lp['loop_guess']} [M]"
        + (
            ". End on a frame that matches the opening to make it replay seamlessly."
            if lp["loop_guess"] == "seamless loop likely"
            else "."
        )
    )
    return out
