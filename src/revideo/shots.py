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


def _signature(frame: np.ndarray) -> tuple[np.ndarray, np.ndarray, float]:
    small = cv2.resize(frame, (96, 54), interpolation=cv2.INTER_AREA)
    hsv = cv2.cvtColor(small, cv2.COLOR_BGR2HSV)
    hist = cv2.calcHist([hsv], [0, 1, 2], None, [16, 4, 4], [0, 180, 0, 256, 0, 256]).flatten()
    hist /= hist.sum() + 1e-9
    gray = cv2.GaussianBlur(cv2.cvtColor(small, cv2.COLOR_BGR2GRAY), (5, 5), 0).astype(np.float32)
    return hist, gray, float(hsv[..., 2].mean())


def _signatures(path: str) -> list[tuple[np.ndarray, np.ndarray, float]]:
    return [_signature(f) for _, f in iter_frames(path, 1, max_side=160)]


def _dist(a, b) -> float:
    """max(color-histogram distance, structural distance) between two frame signatures.

    The histogram term catches cuts between differently colored shots; the structural term (mean
    absolute difference of blurred thumbnails) catches cuts between shots with similar colors.
    """
    return max(float(0.5 * np.abs(a[0] - b[0]).sum()), float(np.abs(a[1] - b[1]).mean() / 255.0) * 3.0)


def _persistent(sig, i: int, jump: float, span: int = 3, ratio: float = 0.5) -> bool:
    """A real cut changes the picture for good; a flash, explosion or strobe changes it and reverts.

    Compare the frames `span` before and after the candidate: if they are much closer to each other
    than the instantaneous jump, the change was transient.
    """
    lo, hi = max(0, i - span), min(len(sig) - 1, i + span)
    if hi <= i or lo >= i - 1:
        return True
    return _dist(sig[lo], sig[hi]) >= ratio * jump


def _detect_builtin(sig, threshold: float, min_len: int) -> list[int]:
    """Adaptive-threshold cut detector (no extra deps)."""
    d = np.array([0.0] + [_dist(sig[i - 1], sig[i]) for i in range(1, len(sig))])
    cuts, last = [], 0
    for i in range(1, len(d)):
        lo, hi = max(1, i - 15), min(len(d), i + 16)
        local = np.median(np.concatenate([d[lo:i], d[i + 1 : hi]])) if hi - lo > 1 else 0.0
        if d[i] > threshold and d[i] > 3 * local + 0.05 and i - last >= min_len and _persistent(sig, i, d[i]):
            cuts.append(i)
            last = i
    return cuts


def _detect_scenedetect(path: str, min_len: int) -> list[int] | None:
    try:
        from scenedetect import ContentDetector, detect
    except ImportError:
        return None
    scenes = detect(path, ContentDetector(threshold=27.0, min_scene_len=min_len))
    return [s[0].get_frames() for s in scenes[1:]]


def detect_shots(
    path: str, info: VideoInfo, threshold: float = 0.3, min_len_sec: float = 0.25, engine: str = "builtin"
) -> tuple[list[Shot], dict]:
    """Shot list + detector metadata. Flash-like (non-persistent) changes are rejected for both engines."""
    min_len = max(2, int(round(min_len_sec * info.fps)))
    sig = _signatures(path)
    total = len(sig) or info.frame_count  # decoded count is authoritative; containers can over-report
    cuts, used, rejected = None, "builtin", 0
    if engine == "scenedetect":
        cuts = _detect_scenedetect(path, min_len)
        if cuts is not None:
            used = "pyscenedetect.ContentDetector"
            kept = []
            for c in cuts:
                if not 0 < c < total:
                    continue
                # align to the local peak (engines can disagree by a frame or two), then test persistence
                i = max(range(max(1, c - 2), min(total, c + 3)), key=lambda k: _dist(sig[k - 1], sig[k]))
                if _persistent(sig, i, _dist(sig[i - 1], sig[i])):
                    kept.append(c)
            rejected, cuts = len(cuts) - len(kept), kept
    if cuts is None:
        cuts = _detect_builtin(sig, threshold, min_len)

    lumas = np.array([x[2] for x in sig])
    black = (lumas < 12) & (np.array([float(x[1].std()) for x in sig]) < 4)
    cuts = _merge_fades(sorted(c for c in cuts if 0 < c < total), lumas, black, info.fps)
    bounds = [0] + cuts + [total]
    shots = [Shot(i, bounds[i], bounds[i + 1], bounds[i] / info.fps, bounds[i + 1] / info.fps) for i in range(len(bounds) - 1)]
    _type_transitions(shots, lumas, black)
    meta = {
        "engine": used,
        "threshold": threshold,
        "min_shot_len_frames": min_len,
        "decoded_frames": total,
        "flash_rejected_cuts": rejected,
    }
    if info.frame_count and abs(info.frame_count - total) > 1:
        meta["container_reported_frames"] = info.frame_count
    return shots, meta


def _merge_fades(cuts: list[int], lumas: np.ndarray, black: np.ndarray, fps: float, max_gap_sec: float = 1.5) -> list[int]:
    """A fade-out → black → fade-in yields two nearby cuts around a black trough. Keep only the second,
    so the black stretch belongs to the transition instead of becoming a fake shot.

    Guards against dark scenes: the trough must contain a flat black frame (dark *and* no detail), and
    the first cut must sit on a gradual ramp — a hard cut into a dark shot drops at once (e.g. 88 → 16).
    """
    out: list[int] = []
    for c in cuts:
        if out and c - out[-1] <= max_gap_sec * fps:
            p = out[-1]
            before, after = lumas[max(0, p - 24) : p], lumas[c : c + 24]
            has_black = bool(black[p : c + 6].any())  # the trough can extend a few frames past the 2nd cut
            ramp = p > 0 and lumas[p] >= 0.5 * lumas[p - 1]
            deep = len(before) and len(after) and lumas[p : c + 6].min() < 0.4 * min(np.median(before), np.median(after))
            if has_black and ramp and deep:
                out[-1] = c
                continue
        out.append(c)
    return out


def _type_transitions(shots: list[Shot], lumas: np.ndarray, black: np.ndarray) -> None:
    """Fade through black/white = a luminance trough/peak that stands out from BOTH neighbouring shots
    (relative test, so a dark scene is not mistaken for a fade)."""
    for s in shots[1:]:
        c = s.start_frame
        win = lumas[max(0, c - 6) : min(len(lumas), c + 6)]
        before = lumas[max(0, c - 30) : max(0, c - 6)]
        after = lumas[min(len(lumas), c + 6) : min(len(lumas), c + 30)]
        if not len(win) or not len(before) or not len(after):
            continue
        ref_lo = min(np.median(before), np.median(after))
        ref_hi = max(np.median(before), np.median(after))
        if black[max(0, c - 6) : c + 6].any() and win.min() < 0.4 * ref_lo:
            s.transition_in = "fade_through_black"
        elif win.max() > 240 and win.max() > ref_hi + 60:
            s.transition_in = "flash_white"


KEYFRAME_POSITIONS = {"in": 0.1, "mid": 0.5, "out": 0.9}


def keyframe_frames(shot: Shot) -> dict[str, int]:
    """Frame index of each keyframe label inside a shot."""
    span = max(1, shot.end_frame - shot.start_frame)
    return {lab: min(shot.end_frame - 1, shot.start_frame + int(span * p)) for lab, p in KEYFRAME_POSITIONS.items()}


def export_keyframes(
    path: str, info: VideoInfo, shots: list[Shot], out_dir: str, max_side: int = 960
) -> dict[int, dict[str, str]]:
    os.makedirs(out_dir, exist_ok=True)
    want: dict[int, list[tuple[int, str]]] = {}
    for s in shots:
        for label, idx in keyframe_frames(s).items():
            want.setdefault(idx, []).append((s.index, label))
    frames = read_frames(path, list(want), max_side=max_side)
    result: dict[int, dict[str, str]] = {s.index: {} for s in shots}
    for idx, frame in frames.items():
        for shot_i, label in want[idx]:
            fp = os.path.join(out_dir, f"shot_{shot_i:03d}_{label}.jpg")
            cv2.imwrite(fp, frame, [cv2.IMWRITE_JPEG_QUALITY, 90])
            result[shot_i][label] = fp
    return result


def contact_sheet(
    keyframes: dict[int, dict[str, str]], shots: list[Shot], fps: float, out_path: str, cols: int = 6, cell_w: int = 320
) -> str | None:
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
    cols = min(cols, len(tiles))
    while len(tiles) % cols:
        tiles.append(np.zeros_like(tiles[0]))
    rows = [np.hstack(tiles[i : i + cols]) for i in range(0, len(tiles), cols)]
    cv2.imwrite(out_path, np.vstack(rows), [cv2.IMWRITE_JPEG_QUALITY, 85])
    return out_path
