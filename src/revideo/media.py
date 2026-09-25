"""Analysis for single photographs and audio-only files (videos go through pipeline.analyze)."""

from __future__ import annotations

import json
import os
import shutil
import time

import cv2

from . import __version__, audio, color, composition, forensics, ingest, optics


def _write(result: dict, out_dir: str) -> dict:
    with open(os.path.join(out_dir, "analysis.json"), "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    from .media_report import write_media_reports

    write_media_reports(result, out_dir)
    return result


def _lens_from_exif(ex: dict) -> dict:
    out = {
        k: ex[k]
        for k in ("Make", "Model", "LensModel", "FocalLength", "FocalLengthIn35mmFilm", "FNumber", "ShutterSpeed", "ISO")
        if ex.get(k)
    }
    f35 = ex.get("FocalLengthIn35mmFilm")
    if f35:
        out["field_of_view_class"] = (
            "ultra-wide"
            if f35 < 20
            else "wide"
            if f35 < 35
            else "normal"
            if f35 < 60
            else "short tele (portrait)"
            if f35 < 105
            else "telephoto"
        )
    return out


def analyze_image(source: str, out_dir: str, quiet: bool = False) -> dict:
    from .pipeline import SCHEMA_VERSION

    t0 = time.time()
    acq = ingest.acquire(source, out_dir)
    path = acq["video"]
    img = cv2.imread(path)
    if img is None:
        raise SystemExit(f"cannot decode image: {path} (convert HEIC/AVIF to JPG/PNG first)")
    h, w = img.shape[:2]
    active = composition.crop_active(img)
    meta = forensics.gather(path, acq["meta"])
    preview = os.path.join(out_dir, "preview.jpg")
    scale = 1280 / max(h, w)
    cv2.imwrite(preview, cv2.resize(img, (int(w * scale), int(h * scale))) if scale < 1 else img)
    result = {
        "schema_version": SCHEMA_VERSION,
        "kind": "image",
        "tool": {"name": "revideo", "version": __version__, "elapsed_sec": None},
        "source": {"input": source, "platform": acq["meta"], "file": os.path.relpath(path, out_dir).replace(os.sep, "/")},
        "image": {"width": w, "height": h, "aspect_ratio": round(w / h, 4), "format_guess": composition.nearest_ar_name(w / h)},
        "forensics": meta,
        "camera_and_lens": _lens_from_exif(meta.get("exif") or {}),
        "palette": color.palette([active], k=8),
        "grade": color.grade_stats([active]),
        "framing": composition.analyze_frame(img),
        "active_area": composition.active_area(img),
        "optics": optics.analyze(active),
        "artifacts": {"preview": "preview.jpg"},
    }
    result["tool"]["elapsed_sec"] = round(time.time() - t0, 2)
    if not quiet:
        print(f"▸ image analyzed in {result['tool']['elapsed_sec']}s → {out_dir}", flush=True)
    return _write(result, out_dir)


def analyze_audio(source: str, out_dir: str, whisper: str | None = None, quiet: bool = False) -> dict:
    from .pipeline import SCHEMA_VERSION

    t0 = time.time()
    acq = ingest.acquire(source, out_dir)
    path = acq["video"]
    wav = audio.extract_wav(path, os.path.join(out_dir, "audio.wav"))
    if not wav:
        if path.lower().endswith(".wav"):
            wav = shutil.copy(path, os.path.join(out_dir, "audio.wav"))
        else:
            raise SystemExit("audio decoding needs ffmpeg: install it or run `revideo.py setup`")
    rep = audio.analyze(wav, [])
    transcript = ingest.transcribe_whisper(wav, whisper) or [] if whisper else []
    result = {
        "schema_version": SCHEMA_VERSION,
        "kind": "audio",
        "tool": {"name": "revideo", "version": __version__, "elapsed_sec": None},
        "source": {"input": source, "platform": acq["meta"], "file": os.path.relpath(path, out_dir).replace(os.sep, "/")},
        "forensics": forensics.gather(path, acq["meta"]),
        "audio": rep,
        "transcript": transcript,
    }
    result["tool"]["elapsed_sec"] = round(time.time() - t0, 2)
    if not quiet:
        print(f"▸ audio analyzed in {result['tool']['elapsed_sec']}s → {out_dir}", flush=True)
    return _write(result, out_dir)
