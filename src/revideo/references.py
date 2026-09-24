"""Cinematic reference matching: find the exact film frame a shot was taken from or modeled on.

Workflow
--------
1. The agent proposes candidate films (INFERRED) from the keyframes.
2. `index_reference` fingerprints a film you legally have on disk (perceptual hashes of
   several crops per sampled frame — full, 9:16, 4:5, 1:1 — because reels crop films).
3. `match` compares each shot's keyframes to the index, then refines around the best hit
   frame-by-frame to return an exact frame number + timecode (MEASURED distance).
A match under the distance threshold upgrades the reference to VERIFIED.
"""

from __future__ import annotations

import json
import os

import cv2
import numpy as np

from .composition import crop_active
from .video import iter_frames, probe, timecode

CROPS = {"full": None, "9:16": 9 / 16, "4:5": 4 / 5, "1:1": 1.0}
_BITS = np.unpackbits(np.arange(256, dtype=np.uint8)[:, None], axis=1).sum(axis=1)


def center_crop(img: np.ndarray, ar: float | None) -> np.ndarray:
    if ar is None:
        return img
    h, w = img.shape[:2]
    if w / h > ar:
        nw = int(h * ar)
        x = (w - nw) // 2
        return img[:, x:x + nw]
    nh = int(w / ar)
    y = (h - nh) // 2
    return img[y:y + nh]


def phash(img: np.ndarray) -> np.ndarray:
    """64-bit DCT perceptual hash as 8 bytes."""
    g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if img.ndim == 3 else img
    g = cv2.resize(g, (32, 32), interpolation=cv2.INTER_AREA).astype(np.float32)
    d = cv2.dct(g)[:8, :8].flatten()
    bits = d[1:] > np.median(d[1:])
    bits = np.concatenate([[False], bits])
    return np.packbits(bits)


def hamming(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    """a: (8,), b: (N, 8) → (N,) distances."""
    return _BITS[np.bitwise_xor(b, a)].sum(axis=-1)


def _tiny(img: np.ndarray) -> np.ndarray:
    # zero-mean / unit-variance so a re-graded or re-exposed copy still matches
    t = cv2.resize(cv2.cvtColor(img, cv2.COLOR_BGR2GRAY), (48, 48), interpolation=cv2.INTER_AREA).astype(np.float32)
    return (t - t.mean()) / (t.std() + 1e-6)


def index_reference(film: str, out_path: str, sample_fps: float = 2.0, title: str | None = None,
                    director: str | None = None, year: int | None = None) -> str:
    info = probe(film)
    step = max(1, int(round(info.fps / sample_fps)))
    frames, hashes = [], {k: [] for k in CROPS}
    for idx, f in iter_frames(film, step, max_side=480):
        img = crop_active(f)
        frames.append(idx)
        for k, ar in CROPS.items():
            hashes[k].append(phash(center_crop(img, ar)))
    np.savez_compressed(out_path, frames=np.array(frames), **{f"h_{k.replace(':', 'x')}": np.array(v) for k, v in hashes.items()})
    meta = {"film_path": os.path.abspath(film), "fps": info.fps, "frame_count": info.frame_count,
            "sample_step": step, "title": title, "director": director, "year": year}
    with open(out_path + ".json", "w", encoding="utf-8") as fh:
        json.dump(meta, fh, ensure_ascii=False, indent=2)
    return out_path


def _load(index_path: str):
    npz = np.load(index_path if index_path.endswith(".npz") else index_path + ".npz")
    meta_path = index_path[:-4] + ".npz.json" if index_path.endswith(".npz") else index_path + ".npz.json"
    if not os.path.exists(meta_path):
        meta_path = index_path + ".json"
    with open(meta_path, encoding="utf-8") as fh:
        meta = json.load(fh)
    hashes = {k: npz[f"h_{k.replace(':', 'x')}"] for k in CROPS}
    return npz["frames"], hashes, meta


def match(keyframes: dict[int, dict[str, str]], index_path: str, max_distance: int = 12, refine: bool = True,
          coarse_slack: int = 10, min_correlation: float = 0.8) -> list[dict]:
    frames, hashes, meta = _load(index_path)
    film, fps = meta["film_path"], meta["fps"]
    results = []
    for shot_i, kf in sorted(keyframes.items()):
        fp = kf.get("mid") or next(iter(kf.values()), None)
        if not fp:
            continue
        q = crop_active(cv2.imread(fp))
        best = None
        for flipped in (False, True):
            qi = cv2.flip(q, 1) if flipped else q
            qh = phash(qi)
            for crop, H in hashes.items():
                d = hamming(qh, H)
                j = int(np.argmin(d))
                if best is None or d[j] < best[0]:
                    best = (int(d[j]), int(frames[j]), crop, flipped, qi)
        dist, fidx, crop, flipped, qi = best
        rec = {"shot": shot_i, "coarse_frame": fidx, "coarse_hash_distance": dist, "crop": crop, "mirrored": flipped}
        # The coarse index is sparse (e.g. 2 fps), so the gate is looser; the decision is made after
        # frame-accurate refinement on the actual nearest frame.
        if dist <= max_distance + coarse_slack and refine:
            fidx, corr, final = _refine(film, fidx, meta["sample_step"], qi, CROPS[crop])
            rec.update(hash_distance=final, correlation=round(corr, 4))
            rec["match"] = final <= max_distance and corr >= min_correlation
        else:
            rec.update(hash_distance=dist, correlation=None, match=False)
        rec["film_frame"] = fidx
        rec["film_seconds"] = round(fidx / fps, 3)
        rec["film_timecode"] = timecode(fidx / fps, fps)
        rec["film"] = {k: meta.get(k) for k in ("title", "director", "year")}
        rec["evidence"] = "verified" if rec["match"] else "unknown"
        results.append(rec)
    return results


def _refine(film: str, center: int, radius: int, query: np.ndarray, ar: float | None) -> tuple[int, float, int]:
    """Scan every frame within ±radius of the coarse hit. Returns (frame, correlation, pHash distance)."""
    lo = max(0, center - radius)
    qt, qh = _tiny(query), phash(query)
    best = (center, -1.0, 64)
    for idx, f in iter_frames(film, 1, max_side=480, start=lo, end=center + radius + 1):
        crop = center_crop(crop_active(f), ar)
        corr = float((_tiny(crop) * qt).mean())  # Pearson r on normalized thumbnails
        if corr > best[1]:
            best = (idx, corr, int(hamming(qh, phash(crop)[None])[0]))
    return best
