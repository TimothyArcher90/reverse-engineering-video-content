"""Lens and exposure signatures measured from pixels: depth of field, vignette, grain, clipping.

These are measurements; what they imply (fast lens, film grain added in post, ND filter...) is
inferred and belongs in the dossier with an [I] tag.
"""

from __future__ import annotations

import cv2
import numpy as np


def _gray(img: np.ndarray, side: int = 640) -> np.ndarray:
    g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if img.ndim == 3 else img
    h, w = g.shape
    s = side / max(h, w)
    return cv2.resize(g, (max(1, int(w * s)), max(1, int(h * s))), interpolation=cv2.INTER_AREA) if s < 1 else g


def sharpness_map(img: np.ndarray, grid: int = 8) -> np.ndarray:
    """Laplacian variance per cell, normalized to the sharpest cell (1.0)."""
    g = _gray(img).astype(np.float32)
    lap = cv2.Laplacian(g, cv2.CV_32F, ksize=3)
    h, w = g.shape
    cells = np.array(
        [
            [lap[i * h // grid : (i + 1) * h // grid, j * w // grid : (j + 1) * w // grid].var() for j in range(grid)]
            for i in range(grid)
        ]
    )
    return cells / (cells.max() + 1e-9)


def analyze(img: np.ndarray) -> dict:
    g = _gray(img).astype(np.float32)
    h, w = g.shape
    raw_detail = float(cv2.Laplacian(g, cv2.CV_32F, ksize=3).var())
    sm = sharpness_map(img)
    sharp_share = float((sm > 0.35).mean())
    ys, xs = np.nonzero(sm > 0.35)
    focus_center = (
        [round(float((xs.mean() + 0.5) / sm.shape[1]), 3), round(float((ys.mean() + 0.5) / sm.shape[0]), 3)] if len(xs) else None
    )

    # vignette: corner luminance vs center luminance
    c = g[h // 3 : 2 * h // 3, w // 3 : 2 * w // 3].mean()
    k = max(2, min(h, w) // 8)
    corners = np.mean([g[:k, :k].mean(), g[:k, -k:].mean(), g[-k:, :k].mean(), g[-k:, -k:].mean()])
    vignette = float(corners / (c + 1e-6))

    # grain/noise: residual std after a small blur, in the flattest 30 % of pixels
    resid = g - cv2.GaussianBlur(g, (0, 0), 1.2)
    grad = cv2.GaussianBlur(np.abs(cv2.Sobel(g, cv2.CV_32F, 1, 0)) + np.abs(cv2.Sobel(g, cv2.CV_32F, 0, 1)), (0, 0), 2)
    flat = grad <= np.percentile(grad, 30)
    noise = float(resid[flat].std()) if flat.any() else None

    hist = cv2.calcHist([g.astype(np.uint8)], [0], None, [256], [0, 256]).ravel() / g.size
    return {
        "sharp_area_share": round(sharp_share, 3),
        "focus_center_norm": focus_center,
        "depth_of_field_guess": "undetermined (too little texture)"
        if raw_detail < 4
        else "shallow (subject isolation)"
        if sharp_share < 0.3
        else "medium"
        if sharp_share < 0.6
        else "deep (everything in focus)",
        "vignette_corner_to_center": round(vignette, 3),
        "vignette_guess": "strong" if vignette < 0.6 else "visible" if vignette < 0.85 else "none/slight",
        "grain_noise_std": round(noise, 2) if noise is not None else None,
        "grain_guess": None if noise is None else "heavy grain/noise" if noise > 6 else "fine grain" if noise > 2.5 else "clean",
        "clipped_highlights_pct": round(float(hist[250:].sum() * 100), 2),
        "crushed_shadows_pct": round(float(hist[:6].sum() * 100), 2),
        "note": "guesses are heuristics (inferred); DOF also depends on distance and sensor size",
    }


def blur_amount(img: np.ndarray) -> float:
    """Global sharpness (Laplacian variance) — handy to compare an original with a replica."""
    return round(float(cv2.Laplacian(_gray(img), cv2.CV_64F).var()), 2)
