"""Color forensics: palette, exposure/key, contrast, white balance and split-toning."""

from __future__ import annotations

import cv2
import numpy as np


def _lab(frame: np.ndarray) -> np.ndarray:
    """CIE L*a*b* with L in [0,100], a/b roughly [-128,127]."""
    lab = cv2.cvtColor(frame.astype(np.float32) / 255.0, cv2.COLOR_BGR2LAB)
    return lab


def lab_to_hex(lab: np.ndarray) -> str:
    px = np.array(lab, dtype=np.float32).reshape(1, 1, 3)
    bgr = np.clip(cv2.cvtColor(px, cv2.COLOR_LAB2BGR)[0, 0] * 255, 0, 255).astype(int)
    return f"#{bgr[2]:02X}{bgr[1]:02X}{bgr[0]:02X}"


def palette(frames: list[np.ndarray], k: int = 6) -> list[dict]:
    """Dominant colors by k-means in Lab space, sorted by share."""
    pts = []
    for f in frames:
        small = cv2.resize(f, (96, int(96 * f.shape[0] / f.shape[1]) or 1), interpolation=cv2.INTER_AREA)
        pts.append(_lab(small).reshape(-1, 3))
    data = np.concatenate(pts).astype(np.float32)
    k = min(k, len(np.unique(data.round(0), axis=0)))
    if k < 1:
        return []
    crit = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 30, 0.5)
    _, labels, centers = cv2.kmeans(data, k, None, crit, 3, cv2.KMEANS_PP_CENTERS)
    counts = np.bincount(labels.flatten(), minlength=k)
    order = np.argsort(-counts)
    return [
        {
            "hex": lab_to_hex(centers[i]),
            "share": round(float(counts[i] / counts.sum()), 4),
            "lab": [round(float(v), 2) for v in centers[i]],
        }
        for i in order
    ]


def _hue_name(a: float, b: float) -> str:
    if abs(a) < 2 and abs(b) < 2:
        return "neutral"
    ang = (np.degrees(np.arctan2(b, a)) + 360) % 360
    names = [
        (20, "magenta-red"),
        (70, "orange"),
        (105, "yellow"),
        (160, "yellow-green"),
        (200, "green"),
        (250, "teal-cyan"),
        (300, "blue"),
        (340, "violet"),
        (360, "magenta-red"),
    ]
    return next(n for lim, n in names if ang < lim)


def grade_stats(frames: list[np.ndarray]) -> dict:
    """Measured look descriptors. Labels at the end are heuristics (inferred)."""
    L, A, B, S = [], [], [], []
    for f in frames:
        small = cv2.resize(f, (192, int(192 * f.shape[0] / f.shape[1]) or 1), interpolation=cv2.INTER_AREA)
        lab = _lab(small)
        L.append(lab[..., 0].ravel())
        A.append(lab[..., 1].ravel())
        B.append(lab[..., 2].ravel())
        S.append(cv2.cvtColor(small, cv2.COLOR_BGR2HSV)[..., 1].ravel() / 255.0)
    L, A, B, S = (np.concatenate(x) for x in (L, A, B, S))

    p5, p50, p95 = np.percentile(L, [5, 50, 95])
    shadows = np.percentile(L, 20) >= L
    highs = np.percentile(L, 80) <= L
    sh_ab = (float(A[shadows].mean()), float(B[shadows].mean()))
    hi_ab = (float(A[highs].mean()), float(B[highs].mean()))
    stats = {
        "luma_mean": round(float(L.mean()), 2),
        "luma_p5_p50_p95": [round(float(p5), 2), round(float(p50), 2), round(float(p95), 2)],
        "contrast_std": round(float(L.std()), 2),
        "dynamic_range_p95_p5": round(float(p95 - p5), 2),
        "crushed_blacks_pct": round(float((L < 3).mean() * 100), 2),
        "clipped_whites_pct": round(float((L > 97).mean() * 100), 2),
        "black_point_L": round(float(np.percentile(L, 0.5)), 2),
        "saturation_mean": round(float(S.mean()), 3),
        "white_balance_ab": [round(float(A.mean()), 2), round(float(B.mean()), 2)],
        "shadows_tint_ab": [round(v, 2) for v in sh_ab],
        "highlights_tint_ab": [round(v, 2) for v in hi_ab],
        "shadows_hue": _hue_name(*sh_ab),
        "highlights_hue": _hue_name(*hi_ab),
    }
    stats["look_labels"] = _labels(stats)
    return stats


def _labels(s: dict) -> list[str]:
    out = []
    lm, con, sat = s["luma_mean"], s["contrast_std"], s["saturation_mean"]
    out.append("high-key" if lm > 65 else "low-key" if lm < 35 else "mid-key")
    out.append("high-contrast" if con > 28 else "low-contrast/flat" if con < 14 else "medium-contrast")
    out.append("desaturated" if sat < 0.18 else "saturated" if sat > 0.45 else "natural-saturation")
    wa, wb = s["white_balance_ab"]
    if wb > 6:
        out.append("warm")
    elif wb < -4:
        out.append("cool")
    if s["black_point_L"] > 6:
        out.append("lifted-blacks (matte/film-emulation)")
    if s["shadows_hue"] in ("teal-cyan", "blue", "green") and s["highlights_hue"] in ("orange", "yellow"):
        out.append("teal-and-orange split-tone")
    elif s["shadows_hue"] != s["highlights_hue"] and "neutral" not in (s["shadows_hue"], s["highlights_hue"]):
        out.append(f"split-tone: {s['shadows_hue']} shadows / {s['highlights_hue']} highlights")
    if s["crushed_blacks_pct"] > 8:
        out.append("crushed blacks")
    if s["clipped_whites_pct"] > 5:
        out.append("blown highlights")
    return out


def delta_e(lab1, lab2) -> float:
    return float(np.linalg.norm(np.array(lab1, dtype=float) - np.array(lab2, dtype=float)))


def palette_distance(p1: list[dict], p2: list[dict]) -> float | None:
    """Share-weighted average of each color's nearest-match ΔE76 (symmetric)."""
    if not p1 or not p2:
        return None

    def one_way(a, b):
        return sum(c["share"] * min(delta_e(c["lab"], d["lab"]) for d in b) for c in a) / (sum(c["share"] for c in a) or 1)

    return round((one_way(p1, p2) + one_way(p2, p1)) / 2, 2)
