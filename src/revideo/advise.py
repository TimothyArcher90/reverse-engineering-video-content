"""Turn measurements into a replication plan for different conditions and budgets.

Everything specific in the plan (durations, hex colors, BPM, moves, lens class) comes from
analysis.json. Gear and tool choices per tier are recommendations [I]. Prices are never stated as
numbers: the catalog gives the pricing model and the official URL to check.
"""

from __future__ import annotations

import json
import os
from importlib import resources

TIERS = {
    "phone": "Phone only · $0 software",
    "creator": "Creator kit · mid budget",
    "pro": "Pro crew / studio",
}

RIG = {  # measured camera move → how to get it at each tier
    "static": ("phone on a mini tripod or leaned on something solid", "tripod", "tripod with fluid head / locked-off sticks"),
    "handheld": (
        "handheld phone, elbows tucked, no stabilization crop",
        "handheld with a light cage",
        "shoulder rig / handheld with a follow-focus",
    ),
    "pan": ("phone gimbal or slow body turn from the hips", "gimbal or tripod with fluid head", "fluid head or remote head"),
    "tilt": ("phone gimbal tilt mode", "gimbal or fluid head", "fluid head / crane"),
    "push": (
        "walk forward slowly with a gimbal, or digital punch-in in the edit",
        "gimbal walk-in or slider",
        "dolly / slider (zoom if no parallax is visible)",
    ),
    "pull": ("walk backward with a gimbal, or scale down in the edit", "gimbal walk-out or slider", "dolly / slider / zoom"),
    "roll": ("rotate in the edit (keyframed rotation)", "gimbal roll mode or rotate in post", "rolling head / rotate in post"),
}


def load_catalog() -> dict:
    with resources.files("revideo").joinpath("data/tools.json").open(encoding="utf-8") as f:
        return json.load(f)


def _move_key(cam_type: str) -> str:
    t = cam_type or ""
    for key, needle in (("push", "push_in"), ("pull", "pull_out"), ("pan", "pan_"), ("tilt", "tilt_"), ("roll", "roll")):
        if needle in t:
            return key
    return "handheld" if "handheld" in t else "static"


def _recipe_checks(crs: dict | None, o: dict | None) -> list[str]:
    """Where the embedded recipe and the pixels disagree, say so: the recipe may not match this export."""
    if not crs or not o:
        return []
    out = []
    try:
        grain = float(crs.get("GrainAmount", 0))
    except ValueError:
        grain = 0
    if grain > 0 and o.get("grain_guess") == "clean":
        out.append(
            f"Embedded GrainAmount {grain:g} but the pixels measure clean: downscaling may have removed it, or the settings do not match this export [I]."
        )
    return out


def _grade_steps(g: dict, crs: dict | None) -> list[str]:
    if crs:
        return ["**Exact settings found in the file's metadata (Lightroom/Camera Raw)** [M] — copy them 1:1:"] + [
            f"Lightroom `{k}` = {v}" for k, v in crs.items()
        ]
    if not g:
        return ["no grade measurements available"]
    a, b = g["white_balance_ab"]
    p5, p50, p95 = g["luma_p5_p50_p95"]
    steps = [
        f"White balance: {'warm' if b > 3 else 'cool' if b < -3 else 'neutral'} on the blue–yellow axis (b* {b}), "
        f"{'magenta' if a > 3 else 'green' if a < -3 else 'neutral'} on green–magenta (a* {a}).",
        f"Tone: target luma p5/p50/p95 ≈ {p5}/{p50}/{p95} (0–100 L*); contrast σ {g['contrast_std']} → "
        f"{'strong S-curve' if g['contrast_std'] > 28 else 'flat curve' if g['contrast_std'] < 14 else 'gentle S-curve'}.",
        f"Black point: L* {g['black_point_L']} → {'lift blacks (matte / film look)' if g['black_point_L'] > 6 else 'keep true black'}.",
        f"Split-tone: shadows toward {g['shadows_hue']} {g['shadows_tint_ab']}, highlights toward {g['highlights_hue']} {g['highlights_tint_ab']}.",
        f"Saturation: mean {g['saturation_mean']} (0–1) → {'pull saturation down' if g['saturation_mean'] < 0.18 else 'boost vibrance' if g['saturation_mean'] > 0.45 else 'leave near natural'}.",
        f"Look labels [I]: {', '.join(g['look_labels'])}.",
    ]
    return steps


def _optics_steps(o: dict | None, lens: dict | None) -> list[str]:
    out = []
    if lens:
        out.append(f"Camera/lens from EXIF [M]: {lens}")
    if o:
        dof = o["depth_of_field_guess"]
        if dof.startswith("undetermined"):
            return out
        if (o.get("focus_falloff_guess") or "").startswith("abrupt"):
            out.append(
                f"Focus falloff *abrupt* ({o['focus_falloff_width_pct']} % of the short side) → the sharp region was most likely "
                "cut out/composited over a blurred background: rebuild it in post (layer + blurred plate). No lens gives this edge."
            )
            return out
        out.append(
            f"Depth of field *{dof}* → "
            + (
                "open aperture (f/1.4–f/2.8 on full frame), longer lens, subject far from background; on phones use Portrait/Cinematic mode."
                if dof.startswith("shallow")
                else "stop down (f/5.6–f/11) or use a wide lens; phones do this by default."
                if dof.startswith("deep")
                else "moderate aperture (f/2.8–f/4)."
            )
        )
        if o["vignette_guess"] != "none/slight":
            out.append(
                f"Vignette {o['vignette_guess']} (corner/center {o['vignette_corner_to_center']}) → add a vignette in the grade."
            )
        if o["grain_guess"] and o["grain_guess"] != "clean":
            out.append(f"Texture: {o['grain_guess']} (σ {o['grain_noise_std']}) → add film grain in post, or shoot higher ISO.")
    return out


def _prompt(spec: dict) -> dict:
    parts = [spec.get("subject", "[subject/action — describe from the keyframe]")]
    if spec.get("shot_size"):
        parts.append(f"{spec['shot_size']} shot")
    if spec.get("move") and "undetermined" not in spec["move"]:
        parts.append(f"camera: {spec['move']}")
    if spec.get("dof") and spec["dof"] != "undetermined":
        parts.append(f"{spec['dof']} depth of field")
    parts.append(f"color palette {', '.join(spec.get('hexes', [])[:4])}")
    parts.append(", ".join(spec.get("look", [])))
    parts.append(f"aspect ratio {spec.get('ar', '9:16')}")
    if spec.get("duration"):
        parts.append(f"{spec['duration']} s")
    return {
        "prompt": ", ".join(p for p in parts if p),
        "negative": "text artifacts, watermark, extra fingers, warped faces"
        + ("" if spec.get("still") else ", flicker, color shift between frames"),
    }


def _tools_for(tier: str, cats: tuple[str, ...], catalog: dict) -> list[str]:
    return [
        f"[{t['name']}]({t['url']}) — {t['pricing_model']}"
        for t in catalog["tools"]
        if tier in t["tiers"] and any(c in t["category"] for c in cats)
    ]


def plan(r: dict) -> str:
    catalog = load_catalog()
    kind = r.get("kind", "video")
    meta = r.get("forensics") or {}
    crs = (meta.get("xmp") or {}).get("camera_raw_settings")
    L = [f"# Replication plan — {r['source']['platform'].get('title') or os.path.basename(str(r['source']['input']))}\n"]
    L.append(
        "> Specs are **[M]** from analysis.json. Gear, tools and methods are recommendations **[I]**. "
        f"Tool pricing models are from a catalog dated {catalog['catalog_date']} and **not verified**: "
        "check the linked page before quoting a price.\n"
    )

    fingerprints = meta.get("tool_fingerprints") or []
    if fingerprints:
        L.append("## What the original was made with (metadata)")
        L += [f"- {h['tool']} — {h['means']} [M]" for h in fingerprints]
        L.append("")

    if kind == "video":
        fp, v = r["fingerprint"], r["source"]["video"]
        g = fp.get("global_grade") or {}
        L += [
            "## 1. Target spec [M]",
            f"- Deliver {v['width']}×{v['height']} @ {v['fps']} fps, {fp['duration_sec']} s, active picture {fp['active_picture_format_guess']}",
            f"- {fp['shot_count']} shots · ASL {fp['asl_sec']} s · {fp['cuts_per_minute']} cuts/min · hook: first cut at {fp['hook']['first_cut_tc'] or 'none'}",
            f"- Palette: {', '.join(c['hex'] for c in fp.get('global_palette', [])[:6])}",
        ]
        if fp.get("tempo_bpm_estimate"):
            bpm = fp["tempo_bpm_estimate"]
            L.append(f"- Music ≈ {bpm} BPM (one beat every {60 / bpm:.3f} s) · cuts on beat {fp.get('cuts_on_beat_ratio')}")
        a = r.get("audio") or {}
        if (a.get("key_estimate") or {}).get("key"):
            L.append(f"- Music key ≈ {a['key_estimate']['key']} · {((a.get('spectral') or {}).get('brightness_guess')) or ''}")
        L += [
            "",
            "## 2. Shot list (edit decision list) [M]",
            "",
            "| # | In | Dur (s) | Move | Rig — phone / creator / pro | Size | AI prompt |",
            "|---|---|---|---|---|---|---|",
        ]
        prompts = []
        for s in r["shots"]:
            cam = (s.get("camera") or {}).get("type", "static")
            rig = RIG[_move_key(cam)]
            size = ((s.get("framing") or {}).get("faces") or {}).get("shot_size_estimate")
            p = _prompt(
                {
                    "shot_size": size,
                    "move": cam.replace("_", " "),
                    "dof": ((s.get("optics") or {}).get("depth_of_field_guess") or "").split(" ")[0],
                    "hexes": [c["hex"] for c in s.get("palette", [])],
                    "look": (s.get("grade") or {}).get("look_labels", [])[:3],
                    "ar": fp["active_picture_format_guess"].split(" ")[0],
                    "duration": s["duration_sec"],
                }
            )
            prompts.append((s, p))
            L.append(
                f"| {s['index']} | {s['start_tc']} | {s['duration_sec']} | {cam} | {rig[0]} / {rig[1]} / {rig[2]} | {size or '–'} | see §6 #{s['index']} |"
            )
        L += ["", "## 3. Grade recipe", *[f"- {x}" for x in _grade_steps(g, crs)]]
        mids = [s.get("optics") for s in r["shots"] if s.get("optics")]
        if mids:
            L += ["", "## 4. Optics", *[f"- {x}" for x in _optics_steps(mids[len(mids) // 2], None)]]
        L += ["", "## 5. Paths by condition"]
        L += _paths(catalog, ai=True, shoot=True)
        L += ["", "## 6. AI prompt pack (fill the [subject] from each keyframe)"]
        for s, p in prompts:
            L.append(f"\n**Shot {s['index']}** ({s['duration_sec']} s, keyframe `{s.get('keyframes', {}).get('mid', '')}`)")
            L.append(f"- prompt: `{p['prompt']}`")
            L.append(f"- negative: `{p['negative']}`")
    elif kind == "image":
        im, g, o = r["image"], r["grade"], r["optics"]
        L += [
            "## 1. Target spec [M]",
            f"- {im['width']}×{im['height']} ({im['format_guess']}) · palette {', '.join(c['hex'] for c in r['palette'][:6])}",
            f"- Framing {r['framing']['framing_guess']} · visual center {r['framing']['visual_center_norm']}",
            *(
                [
                    f"- Subject (in-focus region) at {r['subject']['box_px']} px · palette {', '.join(c['hex'] for c in r['subject']['palette'])}"
                ]
                if r.get("subject")
                else []
            ),
            "",
            "## 2. Grade recipe",
            *[f"- {x}" for x in _grade_steps(g, crs)],
            *[f"- ⚠ {x}" for x in _recipe_checks(crs, o)],
            "",
            "## 3. Optics & capture",
            *[f"- {x}" for x in _optics_steps(o, r.get("camera_and_lens"))],
            "",
            "## 4. Paths by condition",
            *_paths(catalog, ai=True, shoot=True, photo=True),
            "",
            "## 5. AI prompt",
        ]
        p = _prompt(
            {
                "shot_size": (r["framing"].get("faces") or {}).get("shot_size_estimate"),
                "dof": o["depth_of_field_guess"].split(" ")[0],
                "hexes": [c["hex"] for c in (r.get("subject") or {}).get("palette", [])[:2]] + [c["hex"] for c in r["palette"]],
                "look": g["look_labels"][:3],
                "ar": im["format_guess"].split(" ")[0],
                "still": True,
            }
        )
        gen = (meta.get("png_text") or {}).get("parameters")
        if gen:
            L.append(f"- Original generation parameters were embedded [M]: `{str(gen)[:600]}`")
        L += [f"- prompt: `{p['prompt']}`", f"- negative: `{p['negative']}`"]
    else:
        a = r["audio"]
        k, sp = a.get("key_estimate") or {}, a.get("spectral") or {}
        L += [
            "## 1. Target spec [M]",
            f"- {a['duration_sec']} s · ≈ {a['tempo_bpm_estimate']} BPM · key ≈ {k.get('key')} · {sp.get('brightness_guess')}",
            f"- Energy by band: {sp.get('energy_share_pct')} · crest {sp.get('crest_factor_db')} dB (lower = more compressed/louder master)",
            "",
            "## 2. How to get a similar sound",
            f"- Search music libraries / generators with: `{a['tempo_bpm_estimate']} BPM, {k.get('key')}, {sp.get('brightness_guess')}`",
            "- Match the level: compare crest factor and mean level against your mix; loudness targets differ per platform (check current platform specs).",
            "",
            "## 3. Paths by condition",
            *_paths(catalog, ai=True, shoot=False, audio=True),
        ]
    L += [
        "",
        "## Validate the replica",
        "Analyze your version and score it against the original: `analyze replica -o runs/x-replica` then `compare runs/x runs/x-replica`. "
        "Fix the lowest-scoring component first.",
    ]
    return "\n".join(L) + "\n"


def _paths(catalog: dict, ai: bool, shoot: bool, photo: bool = False, audio: bool = False) -> list[str]:
    cats_edit = ("photo", "color") if photo else ("audio",) if audio else ("edit", "color", "motion")
    cats_ai = ("ai-image",) if photo else ("ai-audio",) if audio else ("ai-video", "ai-avatar", "ai-audio")
    out = ["", "| Condition | Capture | Software |", "|---|---|---|"]
    for tier, label in TIERS.items():
        capture = {
            "phone": "phone main camera, daylight or a window as key light, reflector = white card",
            "creator": "mirrorless or recent phone + fast prime, 1–2 LED panels with softbox, lav/shotgun mic",
            "pro": "cinema camera + matched primes, full lighting package, sound recordist",
        }[tier]
        if audio:
            capture = {
                "phone": "phone voice memo in a quiet, soft room",
                "creator": "USB/XLR mic + interface",
                "pro": "studio + engineer",
            }[tier]
        elif photo:
            capture = {
                "phone": "phone main camera (Portrait mode for shallow focus), window light, white card as reflector",
                "creator": "mirrorless + fast prime, one strobe or LED with softbox, reflector",
                "pro": "full-frame/medium-format body, matched lenses, lighting crew, digital tech",
            }[tier]
        out.append(f"| {label} | {capture} | {'; '.join(_tools_for(tier, cats_edit, catalog)) or '–'} |")
    if ai:
        tools = sorted({t for tier in TIERS for t in _tools_for(tier, cats_ai, catalog)})
        out += ["", f"- **No location / no talent / no gear → AI path**: {'; '.join(tools)}"]
    if shoot and not audio:
        out += [
            "- **Night or low light**: widest aperture, raise ISO and add grain to match, use practical lights in frame.",
            "- **Outdoors, harsh sun**: shoot in shade or golden hour, or diffuse with a scrim; ND filter to keep the aperture open.",
            "- **Alone, no crew**: tripod + remote/timer, lock exposure and focus, record several takes per shot.",
        ]
    return out


def write_plan(analysis_dir: str) -> str:
    with open(os.path.join(analysis_dir, "analysis.json"), encoding="utf-8") as f:
        r = json.load(f)
    path = os.path.join(analysis_dir, "replication_plan.md")
    with open(path, "w", encoding="utf-8") as f:
        f.write(plan(r))
    return path
