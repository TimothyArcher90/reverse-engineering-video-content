"""Cinematic reference matching: find the exact film frame a shot was taken from.

Workflow
--------
1. The agent proposes candidate films (INFERRED) from the keyframes.
2. `index_reference` fingerprints a film you legally have on disk: a perceptual hash for
   several crops of every sampled frame (full frame, and 9:16 / 4:5 / 1:1 windows at the
   left, center and right), because reels crop and reposition widescreen films.
3. `match` compares each shot's keyframes (in/mid/out, plain and mirrored) with the index,
   takes the best few coarse candidates, and scans every frame around each one to return the
   exact frame number + timecode. A match that passes both the hash-distance and the
   correlation thresholds is tagged VERIFIED; anything else is reported as no match.

Limits: crops at arbitrary positions/zoom levels outside the windows above, heavy overlays,
or speed changes reduce recall. Precision stays high because of the two-threshold decision.
"""

from __future__ import annotations

import json
import os

import cv2
import numpy as np

from .composition import crop_active
from .video import iter_frames, probe, timecode

ASPECTS = {"9:16": 9 / 16, "4:5": 4 / 5, "1:1": 1.0}
POSITIONS = {"left": 0.0, "center": 0.5, "right": 1.0}
CROPS: dict[str, tuple[float | None, float]] = {"full": (None, 0.5)}
CROPS.update({f"{a}@{p}": (ar, pos) for a, ar in ASPECTS.items() for p, pos in POSITIONS.items()})

_BITS = np.unpackbits(np.arange(256, dtype=np.uint8)[:, None], axis=1).sum(axis=1)
INDEX_VERSION = 2


def crop_window(img: np.ndarray, ar: float | None, pos: float = 0.5) -> np.ndarray:
    """Largest window of aspect `ar` inside `img`, placed at `pos` (0 = left/top, 1 = right/bottom)."""
    if ar is None:
        return img
    h, w = img.shape[:2]
    if w / h > ar:
        nw = max(1, int(h * ar))
        x = int((w - nw) * pos)
        return img[:, x : x + nw]
    nh = max(1, int(w / ar))
    y = int((h - nh) * pos)
    return img[y : y + nh]


def phash(img: np.ndarray) -> np.ndarray:
    """64-bit DCT perceptual hash, packed into 8 bytes."""
    g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if img.ndim == 3 else img
    g = cv2.resize(g, (32, 32), interpolation=cv2.INTER_AREA).astype(np.float32)
    d = cv2.dct(g)[:8, :8].flatten()
    bits = np.concatenate([[False], d[1:] > np.median(d[1:])])
    return np.packbits(bits)


def hamming(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    """a: (8,), b: (N, 8) → (N,) bit distances."""
    return _BITS[np.bitwise_xor(b, a)].sum(axis=-1)


def _tiny(img: np.ndarray) -> np.ndarray:
    # zero-mean / unit-variance so a re-graded or re-exposed copy still correlates
    t = cv2.resize(cv2.cvtColor(img, cv2.COLOR_BGR2GRAY), (48, 48), interpolation=cv2.INTER_AREA).astype(np.float32)
    return (t - t.mean()) / (t.std() + 1e-6)


def _paths(index_path: str) -> tuple[str, str]:
    base = index_path[:-4] if index_path.endswith(".npz") else index_path
    return base + ".npz", base + ".json"


def index_reference(
    film: str,
    out_path: str,
    sample_fps: float = 2.0,
    title: str | None = None,
    director: str | None = None,
    year: int | None = None,
    dp: str | None = None,
) -> str:
    """Write `<out>.npz` (hashes) + `<out>.json` (film metadata). Returns the .npz path."""
    info = probe(film)
    step = max(1, int(round(info.fps / sample_fps)))
    frames, hashes = [], {k: [] for k in CROPS}
    for idx, f in iter_frames(film, step, max_side=480):
        img = crop_active(f)
        frames.append(idx)
        for k, (ar, pos) in CROPS.items():
            hashes[k].append(phash(crop_window(img, ar, pos)))
    npz_path, meta_path = _paths(out_path)
    os.makedirs(os.path.dirname(os.path.abspath(npz_path)), exist_ok=True)
    np.savez_compressed(npz_path, frames=np.array(frames), **{f"h{i}": np.array(hashes[k]) for i, k in enumerate(CROPS)})
    meta = {
        "index_version": INDEX_VERSION,
        "film_path": os.path.abspath(film),
        "fps": info.fps,
        "frame_count": info.frame_count,
        "sample_step": step,
        "crops": list(CROPS),
        "title": title,
        "director": director,
        "director_of_photography": dp,
        "year": year,
    }
    with open(meta_path, "w", encoding="utf-8") as fh:
        json.dump(meta, fh, ensure_ascii=False, indent=2)
    return npz_path


def load_index(index_path: str):
    npz_path, meta_path = _paths(index_path)
    with open(meta_path, encoding="utf-8") as fh:
        meta = json.load(fh)
    if meta.get("index_version") != INDEX_VERSION:
        raise ValueError(f"{index_path}: index format {meta.get('index_version')} ≠ {INDEX_VERSION}; re-run index-ref")
    npz = np.load(npz_path)
    hashes = {k: npz[f"h{i}"] for i, k in enumerate(meta["crops"])}
    return npz["frames"], hashes, meta


def _coarse_candidates(queries, frames, hashes, step: int, top_k: int):
    """Best (distance, frame, crop, query_img) per distinct film region across all query variants."""
    cands = []
    for qi in queries:
        qh = phash(qi)
        for crop, H in hashes.items():
            d = hamming(qh, H)
            k = min(top_k, len(d))
            for j in np.argpartition(d, k - 1)[:k]:  # O(n) partial sort; matters for feature-length indexes
                cands.append((int(d[j]), int(frames[j]), crop, qi))
    cands.sort(key=lambda c: c[0])
    picked = []
    for c in cands:
        if all(abs(c[1] - p[1]) > step or c[2] != p[2] for p in picked):
            picked.append(c)
        if len(picked) == top_k:
            break
    return picked


def _refine(film: str, center: int, radius: int, query: np.ndarray, crop: tuple[float | None, float]):
    """Scan every frame within ±radius of a coarse hit → (frame, correlation, pHash distance)."""
    ar, pos = crop
    qt, qh = _tiny(query), phash(query)
    best = (center, -1.0, 64)
    for idx, f in iter_frames(film, 1, max_side=480, start=max(0, center - radius), end=center + radius + 1):
        win = crop_window(crop_active(f), ar, pos)
        corr = float((_tiny(win) * qt).mean())  # Pearson r of normalized thumbnails
        if corr > best[1]:
            best = (idx, corr, int(hamming(qh, phash(win)[None])[0]))
    return best


def match(
    keyframes: dict[int, dict[str, str]],
    index_path: str,
    max_distance: int = 12,
    min_correlation: float = 0.8,
    coarse_slack: int = 10,
    top_k: int = 3,
    query_frames: dict[int, dict[str, int]] | None = None,
    query_fps: float | None = None,
) -> list[dict]:
    """One record per shot. `match` is True only when both thresholds pass.

    `query_frames`/`query_fps` (from analysis.json) let the record state which frame of the analyzed
    video maps to which film frame, and estimate where the shot starts in the film (assuming 1× speed).
    """
    frames, hashes, meta = load_index(index_path)
    film, fps, step = meta["film_path"], meta["fps"], meta["sample_step"]
    film_info = {k: meta.get(k) for k in ("title", "year", "director", "director_of_photography")}
    results = []
    for shot_i, kf in sorted(keyframes.items()):
        loaded = [(lab, cv2.imread(p)) for lab, p in kf.items()]
        loaded = [(lab, crop_active(im)) for lab, im in loaded if im is not None]
        if not loaded:
            continue
        variants = [(im, False, lab) for lab, im in loaded] + [(cv2.flip(im, 1), True, lab) for lab, im in loaded]
        mirrored_of = {id(v[0]): v[1] for v in variants}
        label_of = {id(v[0]): v[2] for v in variants}
        cands = _coarse_candidates([v[0] for v in variants], frames, hashes, step, top_k)
        best = None
        for dist, fidx, crop, qi in cands:
            if dist > max_distance + coarse_slack:
                continue
            ridx, corr, final = _refine(film, fidx, step, qi, CROPS[crop])
            if best is None or corr > best["correlation"]:
                best = {
                    "film_frame": ridx,
                    "correlation": round(corr, 4),
                    "hash_distance": final,
                    "coarse_hash_distance": dist,
                    "crop": crop,
                    "mirrored": mirrored_of[id(qi)],
                    "query_keyframe": label_of[id(qi)],
                }
        rec = {"shot": shot_i, "film": film_info, "index": os.path.basename(index_path)}
        if best and best["hash_distance"] <= max_distance and best["correlation"] >= min_correlation:
            rec.update(
                best,
                match=True,
                evidence="verified",
                film_seconds=round(best["film_frame"] / fps, 3),
                film_timecode=timecode(best["film_frame"] / fps, fps),
            )
            qf = (query_frames or {}).get(shot_i, {}).get(best["query_keyframe"])
            if qf is not None and query_fps:
                rec["query_frame"] = qf
                rec["query_timecode"] = timecode(qf / query_fps, query_fps)
                shot_start = query_frames[shot_i].get("start", min(query_frames[shot_i].values()))
                offset = (qf - shot_start) / query_fps  # seconds from the shot's first frame
                start = max(0.0, best["film_frame"] / fps - offset)
                rec["film_shot_start_estimate"] = {
                    "seconds": round(start, 3),
                    "timecode": timecode(start, fps),
                    "assumes": "1x playback speed",
                }
        else:
            rec.update(
                match=False, evidence="unknown", closest={k: best[k] for k in ("hash_distance", "correlation")} if best else None
            )
        results.append(rec)
    return results


def best_per_shot(records: list[dict]) -> list[dict]:
    """Merge results from several indexes: keep the strongest record per shot."""
    out: dict[int, dict] = {}
    for r in records:
        cur = out.get(r["shot"])
        score = (r["match"], r.get("correlation") or (r.get("closest") or {}).get("correlation") or -1)
        if cur is None or score > (cur["match"], cur.get("correlation") or (cur.get("closest") or {}).get("correlation") or -1):
            out[r["shot"]] = r
    return [out[k] for k in sorted(out)]
