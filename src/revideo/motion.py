"""Camera-motion forensics from sparse optical flow + similarity-transform fitting."""

from __future__ import annotations

import cv2
import numpy as np

from .video import iter_frames


def _pair_transform(a: np.ndarray, b: np.ndarray):
    pts = cv2.goodFeaturesToTrack(a, maxCorners=300, qualityLevel=0.01, minDistance=8)
    if pts is None or len(pts) < 12:
        return None
    nxt, st, _ = cv2.calcOpticalFlowPyrLK(a, b, pts, None, winSize=(21, 21), maxLevel=3)
    good = st.ravel() == 1
    if good.sum() < 12:
        return None
    p0, p1 = pts[good], nxt[good]
    M, inl = cv2.estimateAffinePartial2D(p0, p1, method=cv2.RANSAC, ransacReprojThreshold=2.0)
    if M is None:
        return None
    scale = float(np.hypot(M[0, 0], M[1, 0]))
    rot = float(np.degrees(np.arctan2(M[1, 0], M[0, 0])))
    inlier_ratio = float(inl.mean()) if inl is not None else 0.0
    # residual = independent (subject) motion not explained by the camera model
    pred = (p0.reshape(-1, 2) @ M[:, :2].T) + M[:, 2]
    resid = float(np.median(np.linalg.norm(pred - p1.reshape(-1, 2), axis=1)))
    return float(M[0, 2]), float(M[1, 2]), scale, rot, inlier_ratio, resid


def analyze_shot(path: str, start: int, end: int, fps: float, samples: int = 10, width: int = 320) -> dict:
    """Classify camera movement within [start, end). Values are per-second, in % of frame width."""
    n = end - start
    if n < 3:
        return {"type": "static", "evidence_note": "shot too short to measure"}
    step = max(1, n // (samples + 1))
    grays = []
    for _, f in iter_frames(path, step, max_side=width, start=start, end=end):
        grays.append(cv2.cvtColor(f, cv2.COLOR_BGR2GRAY))
    if len(grays) < 2:
        return {"type": "static"}
    w = grays[0].shape[1]
    dt = step / fps
    rows = [r for r in (_pair_transform(grays[i], grays[i + 1]) for i in range(len(grays) - 1)) if r]
    if not rows:
        return {"type": "undetermined", "evidence_note": "not enough texture to track"}
    arr = np.array(rows)
    tx, ty = arr[:, 0] / w * 100 / dt, arr[:, 1] / w * 100 / dt  # % of width per second
    zoom = (arr[:, 2] - 1.0) * 100 / dt  # % scale change per second
    rot = arr[:, 3] / dt
    mtx, mty, mz, mr = (float(np.median(v)) for v in (tx, ty, zoom, rot))
    jitter = float(np.std(np.diff(tx)) + np.std(np.diff(ty))) if len(tx) > 2 else 0.0

    moves = []
    if abs(mtx) > 1.5:
        # scene content moving left means the camera pans right
        moves.append("pan_right" if mtx < 0 else "pan_left")
    if abs(mty) > 1.5:
        moves.append("tilt_down" if mty < 0 else "tilt_up")
    if abs(mz) > 1.0:
        moves.append("push_in/zoom_in" if mz > 0 else "pull_out/zoom_out")
    if abs(mr) > 1.0:
        moves.append("roll")
    handheld = jitter > 3.0
    if not moves:
        kind = "handheld_static" if handheld else "static/locked_off"
    else:
        kind = "+".join(moves) + (" (handheld)" if handheld else " (stabilized)")
    return {
        "type": kind,
        "pan_pct_w_per_s": round(mtx, 2),
        "tilt_pct_w_per_s": round(mty, 2),
        "zoom_pct_per_s": round(mz, 2),
        "roll_deg_per_s": round(mr, 2),
        "jitter": round(jitter, 2),
        "subject_motion_px": round(float(np.median(arr[:, 5])), 2),
        "track_inlier_ratio": round(float(np.median(arr[:, 4])), 2),
        "note": "zoom vs dolly cannot be separated from 2D flow alone (parallax check needed)",
    }
