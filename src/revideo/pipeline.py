"""End-to-end measured analysis → analysis.json + keyframes + contact sheet + dossier template."""

from __future__ import annotations

import json
import os
import time
from collections import Counter

import cv2
import numpy as np

from . import __version__, audio, color, composition, evidence, forensics, ingest, motion, optics, social
from . import shots as shotmod
from .video import probe, timecode

SCHEMA_VERSION = 2  # bump when analysis.json changes shape (2: kind, forensics, optics, photo/audio inputs)


def _rel(path: str, start: str) -> str:
    """Relative path with forward slashes: portable in JSON and valid as an HTML src on every OS."""
    return os.path.relpath(path, start).replace(os.sep, "/")


def _log(msg: str, quiet: bool):
    if not quiet:
        print(f"▸ {msg}", flush=True)


def analyze(
    source: str,
    out_dir: str,
    *,
    threshold: float = 0.3,
    engine: str = "builtin",
    no_audio: bool = False,
    no_motion: bool = False,
    whisper: str | None = None,
    quiet: bool = False,
) -> dict:
    t0 = time.time()
    os.makedirs(out_dir, exist_ok=True)

    _log("L0 acquire source + platform metadata", quiet)
    acq = ingest.acquire(source, out_dir)
    video = acq["video"]
    info = probe(video)

    _log("L1 shot boundaries", quiet)
    shot_list, det = shotmod.detect_shots(video, info, threshold=threshold, engine=engine)
    info.frame_count = det["decoded_frames"]
    kf_dir = os.path.join(out_dir, "keyframes")
    keyframes = shotmod.export_keyframes(video, info, shot_list, kf_dir)
    sheet = shotmod.contact_sheet(keyframes, shot_list, info.fps, os.path.join(out_dir, "contact_sheet.jpg"))

    _log(f"L2 per-shot color / framing / motion ({len(shot_list)} shots)", quiet)
    per_shot, all_frames = [], []
    for s in shot_list:
        imgs = [cv2.imread(p) for p in keyframes[s.index].values()]
        imgs = [i for i in imgs if i is not None]
        all_frames.extend(imgs)
        mid = cv2.imread(keyframes[s.index].get("mid", "")) if keyframes[s.index].get("mid") else (imgs[0] if imgs else None)
        rec = s.to_dict(info.fps)
        rec["keyframes"] = {k: _rel(v, out_dir) for k, v in keyframes[s.index].items()}
        rec["keyframe_frames"] = shotmod.keyframe_frames(s)
        if imgs:
            active = [composition.crop_active(i) for i in imgs]
            rec["palette"] = color.palette(active, k=5)
            rec["grade"] = color.grade_stats(active)
            rec["framing"] = composition.analyze_frame(mid)
            rec["active_area"] = composition.active_area(mid)
            rec["optics"] = optics.analyze(composition.crop_active(mid))
        if not no_motion:
            rec["camera"] = motion.analyze_shot(video, s.start_frame, s.end_frame, info.fps)
        rec["interpretation"] = {
            k: None
            for k in (
                "shot_size",
                "angle",
                "lens_mm_estimate",
                "lighting",
                "subject_action",
                "on_screen_text",
                "function_in_story",
                "cinematic_reference",
                "prompt_image",
                "prompt_video",
            )
        }
        per_shot.append(rec)

    transcript, audio_rep = [], None
    for sub in acq.get("subtitles", []):
        transcript = ingest.parse_subtitles(sub)
        if transcript:
            break
    if not no_audio:
        _log("L3 sound (loudness, onsets, tempo, cut sync)", quiet)
        wav = audio.extract_wav(video, os.path.join(out_dir, "audio.wav"))
        if wav:
            audio_rep = audio.analyze(wav, [s.start_sec for s in shot_list[1:]])
            if not transcript and whisper:
                transcript = ingest.transcribe_whisper(wav, whisper) or []
        else:
            audio_rep = {"error": "no audio stream or ffmpeg unavailable"}

    _log("L4 forensics (container tags, XMP, tool fingerprints)", quiet)
    meta = forensics.gather(video, acq["meta"])

    _log("L5 short-form layer (on-screen text, hook, safe zones, loop)", quiet)
    social_rep = social.analyze(video, info, shot_list)

    _log("L6 global fingerprint", quiet)
    fp = fingerprint(info, shot_list, per_shot, all_frames, audio_rep)

    result = {
        "schema_version": SCHEMA_VERSION,
        "kind": "video",
        "tool": {"name": "revideo", "version": __version__, "detector": det, "elapsed_sec": None},
        "source": {
            "input": source,
            "platform": acq["meta"],
            "video": {**info.to_dict(), "path": _rel(video, out_dir)},
        },
        "fingerprint": fp,
        "forensics": meta,
        "social": social_rep,
        "shots": per_shot,
        "transcript": transcript,
        "audio": audio_rep,
        "artifacts": {"keyframes_dir": "keyframes", "contact_sheet": os.path.basename(sheet) if sheet else None},
        "evidence_legend": {
            evidence.MEASURED: "fingerprint, forensics, shots[*].palette/grade/framing/active_area/optics/camera, audio",
            evidence.VERIFIED: "shots[*].reference_match (from match-ref)",
            f"{evidence.OBSERVED}/{evidence.INFERRED}": "written by the agent in dossier.md and shots[*].interpretation",
        },
    }
    result["tool"]["elapsed_sec"] = round(time.time() - t0, 1)
    with open(os.path.join(out_dir, "analysis.json"), "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    from .report import write_dossier_template, write_reports

    write_reports(result, out_dir)
    write_dossier_template(result, os.path.join(out_dir, "dossier.md"))
    _log(f"done in {result['tool']['elapsed_sec']}s → {out_dir}", quiet)
    return result


def fingerprint(info, shot_list, per_shot, all_frames, audio_rep) -> dict:
    durs = np.array([s.duration for s in shot_list]) if shot_list else np.array([info.duration])
    dur = info.duration or float(durs.sum())
    cuts = max(0, len(shot_list) - 1)
    # cuts per window → pacing curve; window scales with length so short reels still get a curve
    win = 1.0 if dur <= 20 else 5.0 if dur <= 180 else 10.0
    bins = int(np.ceil(dur / win)) or 1
    curve = [0] * bins
    for s in shot_list[1:]:
        curve[min(bins - 1, int(s.start_sec // win))] += 1
    first3 = sum(1 for s in shot_list[1:] if s.start_sec < 3.0)

    cams = Counter((r.get("camera") or {}).get("type", "n/a").split(" (")[0] for r in per_shot)
    sizes = Counter(((r.get("framing") or {}).get("faces") or {}).get("shot_size_estimate", "no_face_detected") for r in per_shot)
    trans = Counter(s.transition_in for s in shot_list[1:])
    ar_vals = [r["active_area"]["aspect_ratio"] for r in per_shot if r.get("active_area")]
    active_ar = float(np.median(ar_vals)) if ar_vals else info.width / max(1, info.height)
    actives = [composition.crop_active(f) for f in all_frames] if all_frames else []

    return {
        "duration_sec": round(dur, 3),
        "shot_count": len(shot_list),
        "cuts_per_minute": round(cuts / dur * 60, 2) if dur else None,
        "asl_sec": round(float(durs.mean()), 3),
        "median_shot_sec": round(float(np.median(durs)), 3),
        "shot_len_std_sec": round(float(durs.std()), 3),
        "shortest_longest_sec": [round(float(durs.min()), 3), round(float(durs.max()), 3)],
        "pacing_window_sec": win,
        "pacing_curve": curve,
        "hook": {
            "first_shot_sec": round(float(durs[0]), 3),
            "cuts_in_first_3s": first3,
            "first_cut_tc": timecode(shot_list[1].start_sec, info.fps) if len(shot_list) > 1 else None,
        },
        "delivery_aspect_ratio": round(info.width / max(1, info.height), 4),
        "active_picture_aspect_ratio": round(active_ar, 3),
        "active_picture_format_guess": composition.nearest_ar_name(active_ar),
        "camera_moves": dict(cams),
        "shot_sizes_from_faces": dict(sizes),
        "transitions": dict(trans),
        "global_palette": color.palette(actives, k=8) if actives else [],
        "global_grade": color.grade_stats(actives) if actives else {},
        "tempo_bpm_estimate": (audio_rep or {}).get("tempo_bpm_estimate"),
        "cuts_on_beat_ratio": (audio_rep or {}).get("cuts_on_beat_ratio"),
    }
