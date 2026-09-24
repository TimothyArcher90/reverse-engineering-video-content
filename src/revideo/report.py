"""Human-readable outputs: the measured report and the dossier template the agent completes."""

from __future__ import annotations


def _swatches(pal: list[dict], n: int = 6) -> str:
    return " ".join(f"`{c['hex']}` {c['share'] * 100:.0f}%" for c in pal[:n])


def write_measured_report(r: dict, path: str) -> None:
    fp, v = r["fingerprint"], r["source"]["video"]
    L = []
    L.append(f"# Measured report — {r['source']['platform'].get('title') or r['source']['input']}\n")
    L.append("> Everything on this page is **MEASURED** (computed from pixels/samples). "
              "Labels in *italics* are heuristics derived from the numbers (**INFERRED**).\n")
    L.append("## Source")
    L.append(f"- {v['width']}×{v['height']} @ {v['fps']} fps · {v['duration_sec']} s · delivery AR {fp['delivery_aspect_ratio']}")
    L.append(f"- Active picture AR {fp['active_picture_aspect_ratio']} → *{fp['active_picture_format_guess']}*")
    meta = r["source"]["platform"]
    for k in ("uploader", "upload_date", "view_count", "like_count", "comment_count", "track", "artist"):
        if meta.get(k) is not None:
            L.append(f"- {k}: {meta[k]}")
    L.append("\n## Edit rhythm")
    L.append(f"- Shots: **{fp['shot_count']}** · cuts/min **{fp['cuts_per_minute']}** · ASL **{fp['asl_sec']} s** · median {fp['median_shot_sec']} s")
    L.append(f"- Hook: first shot {fp['hook']['first_shot_sec']} s · cuts in first 3 s: {fp['hook']['cuts_in_first_3s']}")
    L.append(f"- Pacing (cuts per 5 s): `{fp['pacing_curve_cuts_per_5s']}`")
    L.append(f"- Transitions: {fp['transitions'] or 'hard cuts only'}")
    L.append(f"- Camera: {fp['camera_moves']}")
    if fp.get("tempo_bpm_estimate"):
        L.append(f"- Music ≈ {fp['tempo_bpm_estimate']} BPM · cuts on beat {fp.get('cuts_on_beat_ratio')}")
    g = fp.get("global_grade") or {}
    if g:
        L.append("\n## Color / grade")
        L.append(f"- Palette: {_swatches(fp['global_palette'], 8)}")
        L.append(f"- Luma mean {g['luma_mean']} · p5/p50/p95 {g['luma_p5_p50_p95']} · contrast σ {g['contrast_std']} · sat {g['saturation_mean']}")
        L.append(f"- Black point L {g['black_point_L']} · WB (a,b) {g['white_balance_ab']} · shadows *{g['shadows_hue']}* / highlights *{g['highlights_hue']}*")
        L.append(f"- Look: *{', '.join(g['look_labels'])}*")
    L.append("\n## Shot table\n")
    L.append("| # | In | Dur | Transition | Camera | Size (face) | Framing | Palette |")
    L.append("|---|---|---|---|---|---|---|---|")
    for s in r["shots"]:
        fr = s.get("framing") or {}
        size = (fr.get("faces") or {}).get("shot_size_estimate", "–")
        L.append(f"| {s['index']} | {s['start_tc']} | {s['duration_sec']}s | {s['transition_in']} | "
                 f"{(s.get('camera') or {}).get('type', '–')} | {size} | {fr.get('framing_guess', '–')} | "
                 f"{_swatches(s.get('palette', []), 3)} |")
    if r.get("transcript"):
        L.append("\n## Transcript\n")
        for t in r["transcript"]:
            L.append(f"- `{t['start']:.2f}` {t['text']}")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(L) + "\n")


DOSSIER_SECTIONS = [
    ("1. Identity", "What it is, platform, format, length, author. Objective of the piece (awareness, sale, follow)."),
    ("2. Hook anatomy (0–3 s)", "Frame-exact: what is seen, heard and read in the first 3 s, and why it stops the scroll."),
    ("3. Narrative structure", "Beat map with timecodes: hook → setup → escalation → payoff → CTA/loop. Retention devices."),
    ("4. Cinematic references", "Per shot or sequence: film, year, director, DP, exact timecode/frame if verified, what is borrowed (framing, palette, blocking, movement). Tag each VERIFIED / INFERRED."),
    ("5. Visual language", "Shot sizes, angles, lens (focal length estimate + why), depth of field, composition rules, blocking."),
    ("6. Lighting", "Key/fill/back, hard/soft, direction, practicals, color temperature, time of day. Diagram if useful."),
    ("7. Color grade recipe", "From measured numbers → reproducible recipe: WB, contrast curve, black point, split-tone, saturation, LUT family / film stock emulation."),
    ("8. Camera movement", "Per shot: move, speed, rig (tripod, gimbal, handheld, drone, slider, dolly) — INFERRED from measured flow."),
    ("9. Edit & rhythm", "ASL, cuts/min, pacing curve, cut-on-beat, J/L cuts, speed ramps, transitions, text-on-screen timing."),
    ("10. Sound design", "Music (genre, BPM, identifiable track?), SFX, VO, silence, mix levels, ducking."),
    ("11. Typography & graphics", "Caption style, fonts (closest match), position, animation, stickers, UI overlays."),
    ("12. Tools & production stack", "Likely camera/phone, editor (CapCut/Premiere/Resolve/After Effects), AI generators, templates — with the tell-tale sign that supports each inference."),
    ("13. Replication plan", "A) AI path (image → video prompts per shot, model choice) · B) Live-action path (gear, crew, locations, shot order) · C) Post (edit, grade, sound, export)."),
    ("14. Prompt pack", "Per shot: image prompt + motion prompt + negative prompt, matching the measured palette/aspect/motion."),
    ("15. Fidelity check", "After rebuilding: run `revideo compare original/ replica/` and record the score + what still differs."),
    ("16. Open questions / unknowns", "Everything that could not be determined, and what would resolve it."),
]


def write_dossier_template(r: dict, path: str) -> None:
    fp = r["fingerprint"]
    L = [f"# Reverse-engineering dossier — {r['source']['platform'].get('title') or r['source']['input']}\n",
         "Evidence tags: **[M]** measured · **[O]** observed in frame · **[I]** inferred · **[V]** verified against an external source · **[?]** unknown.\n",
         "Numbers come from `analysis.json` / `report.md`. Do not restate a number without its tag.\n",
         f"_Key measurements: {fp['shot_count']} shots · ASL {fp['asl_sec']} s · {fp['cuts_per_minute']} cuts/min · "
         f"AR {fp['active_picture_aspect_ratio']} ({fp['active_picture_format_guess']}) · "
         f"look: {', '.join((fp.get('global_grade') or {}).get('look_labels', []))}_\n"]
    for title, hint in DOSSIER_SECTIONS:
        L.append(f"## {title}\n\n<!-- {hint} -->\n\nTODO\n")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(L))
