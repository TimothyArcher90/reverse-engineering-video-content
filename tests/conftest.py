"""Synthetic fixtures: videos with known cuts, colors, motion and a known film-frame origin."""

import cv2
import numpy as np
import pytest

FPS = 24


def _texture(h, w, seed):
    rng = np.random.default_rng(seed)
    base = rng.integers(0, 255, (h // 8 + 1, w // 8 + 1, 3), dtype=np.uint8)
    img = cv2.resize(base, (w, h), interpolation=cv2.INTER_CUBIC)
    return cv2.GaussianBlur(img, (0, 0), 1.5)


def write(path, frames):
    h, w = frames[0].shape[:2]
    vw = cv2.VideoWriter(path, cv2.VideoWriter_fourcc(*"mp4v"), FPS, (w, h))
    for f in frames:
        vw.write(f)
    vw.release()
    return path


@pytest.fixture(scope="session")
def edit_video(tmp_path_factory):
    """4 shots: warm static (1.0s), cool static (1.5s), pan across texture (2.0s), dark static (1.0s)."""
    d = tmp_path_factory.mktemp("edit")
    h, w = 180, 320
    frames = []
    warm = np.full((h, w, 3), (40, 120, 230), np.uint8)  # BGR orange
    cool = np.full((h, w, 3), (200, 150, 40), np.uint8)  # BGR teal/blue
    for _ in range(24):
        f = warm.copy()
        cv2.circle(f, (160, 90), 30, (255, 255, 255), -1)
        frames.append(f)
    for _ in range(36):
        f = cool.copy()
        cv2.rectangle(f, (40, 40), (120, 140), (20, 20, 20), -1)
        frames.append(f)
    big = _texture(h, w * 3, 7)
    for i in range(48):
        x = int(i * 8)  # content moves left → camera pans right
        frames.append(big[:, x : x + w].copy())
    dark = np.full((h, w, 3), (25, 25, 30), np.uint8)
    for _ in range(24):
        f = dark.copy()
        cv2.line(f, (0, 0), (320, 180), (90, 90, 90), 3)
        frames.append(f)
    return write(str(d / "edit.mp4"), frames)


@pytest.fixture(scope="session")
def film_and_reel(tmp_path_factory):
    """A letterboxed 'film' of 6 distinct scenes, and a 9:16 'reel' made from center crops of scene 4."""
    d = tmp_path_factory.mktemp("film")
    fh, fw = 270, 640  # 2.37:1 picture inside 16:9 canvas
    canvas_h = 360
    film = []
    for s in range(6):
        tex = _texture(fh, fw * 2, 100 + s)
        for i in range(48):
            img = np.zeros((canvas_h, fw, 3), np.uint8)
            img[45 : 45 + fh] = tex[:, i * 2 : i * 2 + fw]
            film.append(img)
    film_path = write(str(d / "film.mp4"), film)
    target = 4 * 48 + 20  # the exact frame the reel quotes
    reel = []
    for _ in range(12):
        src = film[target][45 : 45 + fh]
        cw = int(fh * 9 / 16)
        x = (fw - cw) // 2
        crop = src[:, x : x + cw]
        reel.append(cv2.resize(crop, (180, 320)))
    reel_path = write(str(d / "reel.mp4"), reel)
    return film_path, reel_path, target


@pytest.fixture(scope="session")
def hard_reel(film_and_reel, tmp_path_factory):
    """Harder derivative of the film: left-aligned 4:5 crop, mirrored, warm grade + contrast change,
    downscaled, then a second unrelated shot appended."""
    film_path, _, _ = film_and_reel
    d = tmp_path_factory.mktemp("hard")
    cap = cv2.VideoCapture(film_path)
    frames = []
    while True:
        ok, f = cap.read()
        if not ok:
            break
        frames.append(f)
    target = 2 * 48 + 30
    src = frames[target][45 : 45 + 270]
    cw = int(270 * 4 / 5)
    crop = cv2.flip(src[:, :cw], 1).astype(np.float32)
    crop = np.clip((crop - 128) * 1.25 + 128 + np.array([-12, 4, 22]), 0, 255).astype(np.uint8)
    shot1 = [cv2.resize(crop, (216, 270))] * 18
    other = _texture(270, 216, 999)
    shot2 = [other] * 18
    return write(str(d / "hard.mp4"), shot1 + shot2), target
