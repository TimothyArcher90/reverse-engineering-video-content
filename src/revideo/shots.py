"""Shot boundary detection, transition typing and keyframe export."""

from __future__ import annotations

import os
from dataclasses import asdict, dataclass

import cv2
import numpy as np

from .video import VideoInfo, iter_frames, read_frames, timecode


@dataclass
class Shot:
    index: int
    start_frame: int
    end_frame: int  # exclusive
    start_sec: float
    end_sec: float
    transition_in: str = "hard_cut"

    @property
    def duration(self) -> float:
        return self.end_sec - self.start_sec

    def to_dict(self, fps: float) -> dict:
        d = asdict(self)
        d["duration_sec"] = round(self.duration, 3)
        d["start_tc"] = timecode(self.start_sec, fps)
        d["end_tc"] = timecode(self.end_sec, fps)
        return d


def _signature(frame: np.ndarray) -> tuple[np.ndarray, float]:
    small = cv2.resize(frame, (96, 54), interpolation=cv2.INTER_AREA)
    hsv = cv2.cvtColor(small, cv2.COLOR_BGR2HSV)
    hist = cv2.calcHist([hsv], [0, 1, 2], None, [16, 4, 4], [0, 180, 0, 256, 0, 256]).flatten()
    hist /= hist.sum() + 1e-9
    return hist, float(hsv[..., 2].mean())


def _detect_builtin(path: str, info: VideoInfo, threshold: float, min_len: int) -> tuple[list[int], list[float]]:
    """Histogram-distance cut detector with an adaptive threshold (no extra deps)."""
    diffs, lumas = [], []
    prev = None
    for _, frame in iter_frames(path, 1, max_side=160):
        hist, luma = _signature(frame)
        lumas.append(luma)
        diffs.append(0.0 if prev is None else float(0.5 * np.abs(hist - prev).sum()))
        prev = hist
    d = np.array(diffs)
    cuts = []
    last = 0
    for i in range(1, len(d)):
        lo, hi = max(1, i - 15), min(len(d), i + 16)
        local = np.median(np.concatenate([d[lo:i], d[i + 1:hi]])) if hi - lo > 1 else 0.0
        if d[i] > threshold and d[i] > 3 * local + 0.05 and i - last >= min_len:
            cuts.append(i)
            last = i
    return cuts, lumas


def _detect_scenedetect(path: str, min_len: int) -> list[int] | None:
    try:
        from scenedetect import ContentDetector, detect
    except ImportError:
        return None
    scenes = detect(path, ContentDetector(threshold=27.0, min_scene_len=min_len))
    return [s[0].get_frames() for s in scenes[1:]]


def detect_shots(path: str, info: VideoInfo, threshold: float = 0.35, min_len_sec: float = 0.25,
                 engine: str = "auto") -> tuple[list[Shot], dict]:
    min_len = max(2, int(round(min_len_sec * info.fps)))
    cuts = None
    used = "builtin"
    if engine in ("auto", "scenedetect"):
        cuts = _detect_scenedetect(path, min_len)
        if cuts is not None:
            used = "pyscenedetect.ContentDetector"
    lumas = None
    if cuts is None:
        cuts, lumas = _detect_builtin(path, info, threshold, min_len)
    if lumas is None:
        lumas = [float(cv2.cvtColor(f, cv2.COLOR_BGR2HSV)[..., 2].mean()) for _, f in iter_frames(path, 1, max_side=96)]

    total = len(lumas) or info.frame_count
    bounds = [0] + [c for c in cuts if 0 < c < total] + [total]
    shots = []
    for i in range(len(bounds) - 1):
        a, b = bounds[i], bounds[i + 1]
        shots.append(Shot(i, a, b, a / info.fps, b / info.fps))
    _type_transitions(shots, np.array(lumas))
    return shots, {"engine": used, "threshold": threshold, "min_shot_len_frames": min_len}


def _type_transitions(shots: list[Shot], lumas: np.ndarray) -> None:
    """Label fades through black/white by the luminance trough/peak around the cut."""
    for s in shots[1:]:
        c = s.start_frame
        win = lumas[max(0, c - 6):min(len(lumas), c + 6)]
        if len(win) and win.min() < 12:
            s.transition_in = "fade_through_black"
        elif len(win) and win.max() > 245:
            s.transition_in = "flash_white"


def export_keyframes(path: str, info: VideoInfo, shots: list[Shot], out_dir: str,
                     positions=(0.1, 0.5, 0.9), max_side: int = 960) -> dict[int, dict[str, str]]:
    os.makedirs(out_dir, exist_ok=True)
    want: dict[int, tuple[int, str]] = {}
    for s in shots:
        span = max(1, s.end_frame - s.start_frame)
        for p in positions:
            idx = min(s.end_frame - 1, s.start_frame + int(span * p))
            label = {0.1: "in", 0.5: "mid", 0.9: "out"}.get(p, f"p{int(p * 100)}")
            want[idx] = (s.index, label)
    frames = read_frames(path, list(want), max_side=max_side)
    result: dict[int, dict[str, str]] = {s.index: {} for s in shots}
    for idx, frame in frames.items():
        shot_i, label = want[idx]
        fp = os.path.join(out_dir, f"shot_{shot_i:03d}_{label}.jpg")
        cv2.imwrite(fp, frame, [cv2.IMWRITE_JPEG_QUALITY, 90])
        result[shot_i][label] = fp
    return result


def contact_sheet(keyframes: dict[int, dict[str, str]], shots: list[Shot], fps: float, out_path: str,
                  cols: int = 6, cell_w: int = 320) -> str | None:
    """One image with every shot's mid frame + index + timecode — the fastest way for a vision model to see the whole edit."""
    tiles = []
    for s in shots:
        fp = keyframes.get(s.index, {}).get("mid")
        if not fp:
            continue
        img = cv2.imread(fp)
        h = int(img.shape[0] * cell_w / img.shape[1])
        img = cv2.resize(img, (cell_w, h))
        label = f"#{s.index} {timecode(s.start_sec, fps)} ({s.duration:.2f}s)"
        cv2.rectangle(img, (0, 0), (cell_w, 22), (0, 0, 0), -1)
        cv2.putText(img, label, (6, 16), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255, 255, 255), 1, cv2.LINE_AA)
        tiles.append(img)
    if not tiles:
        return None
    th = max(t.shape[0] for t in tiles)
    tiles = [cv2.copyMakeBorder(t, 0, th - t.shape[0], 0, 0, cv2.BORDER_CONSTANT) for t in tiles]
    while len(tiles) % cols:
        tiles.append(np.zeros_like(tiles[0]))
    rows = [np.hstack(tiles[i:i + cols]) for i in range(0, len(tiles), cols)]
    cv2.imwrite(out_path, np.vstack(rows), [cv2.IMWRITE_JPEG_QUALITY, 85])
    return out_path
