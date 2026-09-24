"""Frame access on top of OpenCV (no ffprobe required)."""

from __future__ import annotations

import os
import shutil
from dataclasses import dataclass

import cv2
import numpy as np


@dataclass
class VideoInfo:
    path: str
    fps: float
    frame_count: int
    width: int
    height: int

    @property
    def duration(self) -> float:
        return self.frame_count / self.fps if self.fps else 0.0

    def to_dict(self) -> dict:
        return {
            "path": self.path,
            "fps": round(self.fps, 3),
            "frame_count": self.frame_count,
            "width": self.width,
            "height": self.height,
            "duration_sec": round(self.duration, 3),
            "aspect_ratio": round(self.width / self.height, 4) if self.height else None,
        }


def probe(path: str) -> VideoInfo:
    cap = cv2.VideoCapture(path)
    if not cap.isOpened():
        raise FileNotFoundError(f"cannot open video: {path}")
    fps = cap.get(cv2.CAP_PROP_FPS) or 0.0
    count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    if count <= 0:  # some containers do not report a count; walk the stream
        count = 0
        while cap.grab():
            count += 1
    cap.release()
    return VideoInfo(path=path, fps=fps if fps > 0 else 25.0, frame_count=count, width=w, height=h)


def resize_max(frame: np.ndarray, max_side: int) -> np.ndarray:
    h, w = frame.shape[:2]
    scale = max_side / max(h, w)
    if scale >= 1:
        return frame
    return cv2.resize(frame, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_AREA)


def iter_frames(path: str, step: int = 1, max_side: int | None = None, start: int = 0, end: int | None = None):
    """Yield (frame_index, frame_bgr) for every `step`-th frame in [start, end)."""
    cap = cv2.VideoCapture(path)
    if start:
        cap.set(cv2.CAP_PROP_POS_FRAMES, start)
    idx = start
    while end is None or idx < end:
        ok = cap.grab()
        if not ok:
            break
        if (idx - start) % step == 0:
            ok, frame = cap.retrieve()
            if not ok:
                break
            yield idx, (resize_max(frame, max_side) if max_side else frame)
        idx += 1
    cap.release()


def read_frames(path: str, indices: list[int], max_side: int | None = None) -> dict[int, np.ndarray]:
    """Read specific frames. Sequential decoding is used for accuracy."""
    wanted = sorted(set(int(i) for i in indices))
    out: dict[int, np.ndarray] = {}
    if not wanted:
        return out
    for idx, frame in iter_frames(path, 1, max_side, start=0, end=wanted[-1] + 1):
        if idx in wanted:
            out[idx] = frame
    return out


def timecode(seconds: float, fps: float) -> str:
    """HH:MM:SS:FF (non-drop-frame)."""
    total_frames = int(round(seconds * fps))
    fps_i = max(1, int(round(fps)))
    ff = total_frames % fps_i
    s = total_frames // fps_i
    return f"{s // 3600:02d}:{(s % 3600) // 60:02d}:{s % 60:02d}:{ff:02d}"


def find_ffmpeg() -> str | None:
    exe = os.environ.get("REVIDEO_FFMPEG") or shutil.which("ffmpeg")
    if exe:
        return exe
    try:
        import imageio_ffmpeg

        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return None
