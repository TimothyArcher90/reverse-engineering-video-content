"""Round-trip validation: score how closely a replica reproduces the original's measurable DNA."""

from __future__ import annotations

import json
import os

import numpy as np

from .color import palette_distance

WEIGHTS = {"rhythm": 0.30, "color": 0.30, "framing": 0.15, "camera": 0.15, "sound": 0.10}
IMAGE_WEIGHTS = {"color": 0.50, "framing": 0.25, "optics": 0.25}
AUDIO_WEIGHTS = {"tempo": 0.35, "key": 0.25, "spectrum": 0.25, "dynamics": 0.15}


def _load(p: str) -> dict:
    if os.path.isdir(p):
        p = os.path.join(p, "analysis.json")
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def _ratio_score(a, b) -> float | None:
    if a is None or b is None:
        return None
    if a == b:
        return 1.0
    return float(min(a, b) / max(a, b)) if max(a, b) > 0 else 0.0


def _mean(xs) -> float | None:
    xs = [x for x in xs if x is not None]
    return float(np.mean(xs)) if xs else None


def _resample(seq: list[float], n: int) -> np.ndarray:
    if not seq:
        return np.zeros(n)
    x = np.linspace(0, 1, len(seq))
    return np.interp(np.linspace(0, 1, n), x, seq)


def _color(pa: list, pb: list, ga: dict, gb: dict) -> dict:
    """Palette ΔE + grade stats → 0–1 score."""
    dE = palette_distance(pa, pb)
    col = []
    if dE is not None:
        col.append(max(0.0, 1 - dE / 30))  # ΔE 0 → 1.0, ΔE ≥30 → 0
    for k, span in (("luma_mean", 40), ("contrast_std", 20), ("saturation_mean", 0.4), ("black_point_L", 10)):
        if k in ga and k in gb:
            col.append(max(0.0, 1 - abs(ga[k] - gb[k]) / span))
    if ga.get("white_balance_ab") and gb.get("white_balance_ab"):
        col.append(max(0.0, 1 - float(np.linalg.norm(np.subtract(ga["white_balance_ab"], gb["white_balance_ab"]))) / 15))
    return {
        "score": _mean(col),
        "palette_delta_e": dE,
        "look_original": ga.get("look_labels"),
        "look_replica": gb.get("look_labels"),
    }


def _image_parts(A: dict, B: dict) -> dict:
    fa, fb, oa, ob = A["framing"], B["framing"], A["optics"], B["optics"]
    center = 1 - min(1.0, float(np.hypot(*np.subtract(fa["visual_center_norm"], fb["visual_center_norm"]))) / 0.5)
    framing = _mean(
        [
            _ratio_score(A["image"]["aspect_ratio"], B["image"]["aspect_ratio"]),
            center,
            float(fa["framing_guess"] == fb["framing_guess"]),
        ]
    )
    optics = _mean(
        [
            float(oa["depth_of_field_guess"] == ob["depth_of_field_guess"]),
            _ratio_score(oa["vignette_corner_to_center"], ob["vignette_corner_to_center"]),
            float(oa["grain_guess"] == ob["grain_guess"]),
        ]
    )
    return {
        "color": _color(A["palette"], B["palette"], A["grade"], B["grade"]),
        "framing": {"score": framing, "framing": [fa["framing_guess"], fb["framing_guess"]]},
        "optics": {"score": optics, "dof": [oa["depth_of_field_guess"], ob["depth_of_field_guess"]]},
    }


def _audio_parts(A: dict, B: dict) -> dict:
    a, b = A["audio"], B["audio"]
    ka, kb = a.get("key_estimate") or {}, b.get("key_estimate") or {}
    key = None
    if ka.get("key") and kb.get("key"):
        key = (
            1.0
            if ka["key"] == kb["key"]
            else 0.5
            if kb["key"] == ka.get("runner_up") or ka["key"] == kb.get("runner_up")
            else 0.0
        )
    sa, sb = (a.get("spectral") or {}).get("energy_share_pct") or {}, (b.get("spectral") or {}).get("energy_share_pct") or {}
    spectrum = 1 - sum(abs(sa[k] - sb.get(k, 0)) for k in sa) / 200 if sa and sb else None
    crest = _ratio_score((a.get("spectral") or {}).get("crest_factor_db"), (b.get("spectral") or {}).get("crest_factor_db"))
    return {
        "tempo": {
            "score": _ratio_score(a.get("tempo_bpm_estimate"), b.get("tempo_bpm_estimate")),
            "bpm": [a.get("tempo_bpm_estimate"), b.get("tempo_bpm_estimate")],
        },
        "key": {"score": key, "key": [ka.get("key"), kb.get("key")]},
        "spectrum": {"score": spectrum},
        "dynamics": {"score": crest},
    }


def _finish(parts: dict, weights: dict, note: str) -> dict:
    got = {k: v["score"] for k, v in parts.items() if v["score"] is not None}
    wsum = sum(weights[k] for k in got) or 1
    total = sum(weights[k] * v for k, v in got.items()) / wsum
    for v in parts.values():
        if v["score"] is not None:
            v["score"] = round(v["score"] * 100, 1)
    return {"fidelity_score": round(total * 100, 1), "weights": weights, "components": parts, "note": note}


def compare(original: str, replica: str) -> dict:
    A, B = _load(original), _load(replica)
    kind_a, kind_b = A.get("kind", "video"), B.get("kind", "video")
    if kind_a != kind_b:
        raise SystemExit(f"cannot compare a {kind_a} with a {kind_b}")
    if kind_a == "image":
        return _finish(_image_parts(A, B), IMAGE_WEIGHTS, "Measures look (color, framing, optics), not content identity.")
    if kind_a == "audio":
        return _finish(_audio_parts(A, B), AUDIO_WEIGHTS, "Measures tempo, key, spectrum and dynamics, not the melody itself.")
    fa, fb = A["fingerprint"], B["fingerprint"]
    parts: dict[str, dict] = {}

    # rhythm: shot count, ASL, and shape of the normalized shot-length sequence
    da = [s["duration_sec"] / fa["duration_sec"] for s in A["shots"]]
    db = [s["duration_sec"] / fb["duration_sec"] for s in B["shots"]]
    n = max(len(da), len(db), 2)
    ra, rb = np.cumsum(_resample(da, n)), np.cumsum(_resample(db, n))
    shape = 1.0 - float(np.mean(np.abs(ra / ra[-1] - rb / rb[-1]))) if ra[-1] and rb[-1] else 0.0
    rhythm = _mean([_ratio_score(fa["shot_count"], fb["shot_count"]), _ratio_score(fa["asl_sec"], fb["asl_sec"]), shape])
    parts["rhythm"] = {
        "score": rhythm,
        "shots": [fa["shot_count"], fb["shot_count"]],
        "asl": [fa["asl_sec"], fb["asl_sec"]],
        "cut_timing_shape": round(shape, 3),
    }

    parts["color"] = _color(
        fa.get("global_palette", []), fb.get("global_palette", []), fa.get("global_grade") or {}, fb.get("global_grade") or {}
    )

    # framing: aspect ratio + shot-size distribution overlap
    ar = _ratio_score(fa["active_picture_aspect_ratio"], fb["active_picture_aspect_ratio"])
    sa, sb = fa.get("shot_sizes_from_faces", {}), fb.get("shot_sizes_from_faces", {})
    keys = set(sa) | set(sb)
    ta, tb = sum(sa.values()) or 1, sum(sb.values()) or 1
    overlap = sum(min(sa.get(k, 0) / ta, sb.get(k, 0) / tb) for k in keys) if keys else None
    parts["framing"] = {
        "score": _mean([ar, overlap]),
        "aspect": [fa["active_picture_aspect_ratio"], fb["active_picture_aspect_ratio"]],
        "shot_size_overlap": overlap,
    }

    # camera: distribution overlap of movement types
    ca, cb = fa.get("camera_moves", {}), fb.get("camera_moves", {})
    keys = set(ca) | set(cb)
    ta, tb = sum(ca.values()) or 1, sum(cb.values()) or 1
    parts["camera"] = {
        "score": sum(min(ca.get(k, 0) / ta, cb.get(k, 0) / tb) for k in keys) if keys else None,
        "original": ca,
        "replica": cb,
    }

    # sound: tempo + cut sync
    sync = (
        None
        if fa.get("cuts_on_beat_ratio") is None or fb.get("cuts_on_beat_ratio") is None
        else 1 - abs(fa["cuts_on_beat_ratio"] - fb["cuts_on_beat_ratio"])
    )
    parts["sound"] = {
        "score": _mean([_ratio_score(fa.get("tempo_bpm_estimate"), fb.get("tempo_bpm_estimate")), sync]),
        "bpm": [fa.get("tempo_bpm_estimate"), fb.get("tempo_bpm_estimate")],
    }

    return _finish(parts, WEIGHTS, "Measures structural DNA (rhythm, color, framing, camera, sound), not content identity.")


def to_markdown(res: dict) -> str:
    L = [f"# Fidelity: **{res['fidelity_score']} / 100**\n", "| Component | Score | Detail |", "|---|---|---|"]
    for k, v in res["components"].items():
        detail = ", ".join(f"{a}={b}" for a, b in v.items() if a != "score")
        L.append(f"| {k} | {v['score'] if v['score'] is not None else 'n/a'} | {detail} |")
    L.append(f"\n_{res['note']}_")
    return "\n".join(L) + "\n"
