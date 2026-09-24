"""Framing forensics: active image area (letterbox), faces, shot size, visual weight, symmetry."""

from __future__ import annotations

import cv2
import numpy as np

_FACE = None

# Common delivery / camera aspect ratios, used to name the measured active area.
KNOWN_AR = [
    (1.0, "1:1"), (0.8, "4:5"), (0.5625, "9:16"), (1.333, "4:3 (Academy-ish)"), (1.375, "1.375 Academy"),
    (1.5, "3:2"), (1.66, "1.66 European widescreen"), (1.778, "16:9"), (1.85, "1.85 flat"),
    (2.0, "2.00 Univisium"), (2.2, "2.20 70mm"), (2.39, "2.39 anamorphic/scope"), (2.76, "2.76 Ultra Panavision"),
]


def _face_detector():
    """Haar cascade (OpenCV 4.x). OpenCV 5 dropped it from the main package → returns False."""
    global _FACE
    if _FACE is None:
        try:
            _FACE = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
        except AttributeError:
            _FACE = False
    return _FACE


def active_area(frame: np.ndarray, thresh: int = 18) -> dict:
    """Detect black bars (letterbox/pillarbox) and report the active picture aspect ratio."""
    g = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    rows = np.where(g.max(axis=1) > thresh)[0]
    cols = np.where(g.max(axis=0) > thresh)[0]
    h, w = g.shape
    if len(rows) == 0 or len(cols) == 0:
        return {"box": [0, 0, w, h], "aspect_ratio": round(w / h, 3), "letterboxed": False}
    y0, y1, x0, x1 = int(rows[0]), int(rows[-1]) + 1, int(cols[0]), int(cols[-1]) + 1
    ar = (x1 - x0) / max(1, (y1 - y0))
    return {"box": [x0, y0, x1, y1], "aspect_ratio": round(ar, 3),
            "letterboxed": (y0 > h * 0.03 or (h - y1) > h * 0.03 or x0 > w * 0.03 or (w - x1) > w * 0.03)}


def nearest_ar_name(ar: float) -> str:
    return min(KNOWN_AR, key=lambda t: abs(t[0] - ar))[1]


def crop_active(frame: np.ndarray) -> np.ndarray:
    x0, y0, x1, y1 = active_area(frame)["box"]
    return frame[y0:y1, x0:x1] if (x1 - x0) > 16 and (y1 - y0) > 16 else frame


def shot_size_from_face(face_h_ratio: float) -> str:
    """Heuristic: fraction of frame height occupied by the largest face."""
    r = face_h_ratio
    if r >= 0.45:
        return "extreme_close_up"
    if r >= 0.28:
        return "close_up"
    if r >= 0.16:
        return "medium_close_up"
    if r >= 0.09:
        return "medium_shot"
    if r >= 0.05:
        return "medium_wide"
    return "wide"


def analyze_frame(frame: np.ndarray) -> dict:
    img = crop_active(frame)
    h, w = img.shape[:2]
    g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    # visual weight: gradient energy + brightness
    gx = cv2.Sobel(g, cv2.CV_32F, 1, 0, ksize=3)
    gy = cv2.Sobel(g, cv2.CV_32F, 0, 1, ksize=3)
    mag = cv2.GaussianBlur(np.sqrt(gx * gx + gy * gy), (0, 0), 3)
    weight = mag / (mag.sum() + 1e-9)
    ys, xs = np.mgrid[0:h, 0:w]
    cx, cy = float((weight * xs).sum() / w), float((weight * ys).sum() / h)
    thirds = [(a, b) for a in (1 / 3, 2 / 3) for b in (1 / 3, 2 / 3)]
    d_thirds = min(np.hypot(cx - a, cy - b) for a, b in thirds)
    d_center = float(np.hypot(cx - 0.5, cy - 0.5))

    flipped = cv2.flip(g, 1)
    symmetry = 1.0 - float(np.abs(g.astype(np.float32) - flipped).mean() / 255.0)
    edge_density = float((mag > 20).mean())
    negative_space = float((mag < 8).mean())

    det = _face_detector()
    faces = det.detectMultiScale(g, scaleFactor=1.1, minNeighbors=5, minSize=(max(20, h // 30),) * 2) if det else []
    faces = sorted([[int(v) for v in f] for f in faces], key=lambda f: -f[3])
    face_info = None
    if faces:
        x, y, fw, fh = faces[0]
        ratio = fh / h
        face_info = {
            "count": len(faces),
            "largest_box_norm": [round(x / w, 3), round(y / h, 3), round(fw / w, 3), round(fh / h, 3)],
            "largest_center_norm": [round((x + fw / 2) / w, 3), round((y + fh / 2) / h, 3)],
            "headroom_norm": round(y / h, 3),
            "shot_size_estimate": shot_size_from_face(ratio),
        }
    return {
        "visual_center_norm": [round(cx, 3), round(cy, 3)],
        "dist_to_thirds_point": round(float(d_thirds), 3),
        "dist_to_center": round(d_center, 3),
        "framing_guess": ("no_structure" if mag.mean() < 1.0 else "centered" if d_center < 0.06
                          else "rule_of_thirds" if d_thirds < 0.08 else "off-center"),
        "symmetry": round(symmetry, 3),
        "edge_density": round(edge_density, 3),
        "negative_space": round(negative_space, 3),
        "faces": face_info,
    }
