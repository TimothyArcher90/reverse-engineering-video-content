"""Human-readable outputs: measured report (Markdown + HTML) and the dossier template the agent completes."""

from __future__ import annotations

import html
import os


def write_reports(r: dict, out_dir: str) -> None:
    from .pipeline import SCHEMA_VERSION

    if r.get("schema_version") != SCHEMA_VERSION:
        raise SystemExit(
            f"{out_dir}: analysis.json schema {r.get('schema_version')} ≠ {SCHEMA_VERSION}; re-run `revideo analyze`"
        )
    if r.get("kind", "video") != "video":
        from .media_report import write_media_reports

        write_media_reports(r, out_dir)
        return
    write_measured_report(r, os.path.join(out_dir, "report.md"))
    write_html_report(r, os.path.join(out_dir, "report.html"))


def _ref_label(m: dict | None) -> str:
    if not m:
        return "–"
    f = m.get("film") or {}
    name = f.get("title") or m.get("index", "reference")
    year = f" ({f['year']})" if f.get("year") else ""
    return f"[V] {name}{year} @ {m['film_timecode']} f{m['film_frame']}"


def _swatches(pal: list[dict], n: int = 6) -> str:
    return " ".join(f"`{c['hex']}` {c['share'] * 100:.0f}%" for c in pal[:n])


def write_measured_report(r: dict, path: str) -> None:
    fp, v = r["fingerprint"], r["source"]["video"]
    L = []
    L.append(f"# Measured report — {r['source']['platform'].get('title') or r['source']['input']}\n")
    L.append(
        "> Everything on this page is **MEASURED** (computed from pixels/samples). "
        "Labels in *italics* are heuristics derived from the numbers (**INFERRED**).\n"
    )
    L.append("## Source")
    L.append(f"- {v['width']}×{v['height']} @ {v['fps']} fps · {v['duration_sec']} s · delivery AR {fp['delivery_aspect_ratio']}")
    L.append(f"- Active picture AR {fp['active_picture_aspect_ratio']} → *{fp['active_picture_format_guess']}*")
    meta = r["source"]["platform"]
    for k in ("uploader", "upload_date", "view_count", "like_count", "comment_count", "track", "artist"):
        if meta.get(k) is not None:
            L.append(f"- {k}: {meta[k]}")
    L.append("\n## Edit rhythm")
    L.append(
        f"- Shots: **{fp['shot_count']}** · cuts/min **{fp['cuts_per_minute']}** · ASL **{fp['asl_sec']} s** · median {fp['median_shot_sec']} s"
    )
    L.append(f"- Hook: first shot {fp['hook']['first_shot_sec']} s · cuts in first 3 s: {fp['hook']['cuts_in_first_3s']}")
    L.append(f"- Pacing (cuts per {fp['pacing_window_sec']:g} s window): `{fp['pacing_curve']}`")
    L.append(f"- Transitions: {fp['transitions'] or 'hard cuts only'}")
    L.append(f"- Camera: {fp['camera_moves']}")
    if fp.get("tempo_bpm_estimate"):
        L.append(f"- Music ≈ {fp['tempo_bpm_estimate']} BPM · cuts on beat {fp.get('cuts_on_beat_ratio')}")
    g = fp.get("global_grade") or {}
    if g:
        L.append("\n## Color / grade")
        L.append(f"- Palette: {_swatches(fp['global_palette'], 8)}")
        L.append(
            f"- Luma mean {g['luma_mean']} · p5/p50/p95 {g['luma_p5_p50_p95']} · contrast σ {g['contrast_std']} · sat {g['saturation_mean']}"
        )
        L.append(
            f"- Black point L {g['black_point_L']} · WB (a,b) {g['white_balance_ab']} · shadows *{g['shadows_hue']}* / highlights *{g['highlights_hue']}*"
        )
        L.append(f"- Look: *{', '.join(g['look_labels'])}*")
    L.append("\n## Shot table\n")
    L.append("| # | In | Dur | Transition | Camera | Size (face) | Framing | Palette | Reference |")
    L.append("|---|---|---|---|---|---|---|---|---|")
    for s in r["shots"]:
        fr = s.get("framing") or {}
        size = (fr.get("faces") or {}).get("shot_size_estimate", "–")
        L.append(
            f"| {s['index']} | {s['start_tc']} | {s['duration_sec']}s | {s['transition_in']} | "
            f"{(s.get('camera') or {}).get('type', '–')} | {size} | {fr.get('framing_guess', '–')} | "
            f"{_swatches(s.get('palette', []), 3)} | {_ref_label(s.get('reference_match'))} |"
        )
    if r.get("transcript"):
        L.append("\n## Transcript\n")
        for t in r["transcript"]:
            L.append(f"- `{t['start']:.2f}` {t['text']}")
    from .media_report import forensics_md

    L += forensics_md(r.get("forensics"))
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(L) + "\n")


DOSSIER_SECTIONS = [
    ("1. Identity", "What it is, platform, format, length, author. Objective of the piece (awareness, sale, follow)."),
    ("2. Hook anatomy (0–3 s)", "Frame-exact: what is seen, heard and read in the first 3 s, and why it stops the scroll."),
    ("3. Narrative structure", "Beat map with timecodes: hook → setup → escalation → payoff → CTA/loop. Retention devices."),
    (
        "4. Cinematic references",
        "Per shot or sequence: film, year, director, DP, exact timecode/frame if verified, what is borrowed (framing, palette, blocking, movement). Tag each VERIFIED / INFERRED.",
    ),
    (
        "5. Visual language",
        "Shot sizes, angles, lens (focal length estimate + why), depth of field, composition rules, blocking.",
    ),
    ("6. Lighting", "Key/fill/back, hard/soft, direction, practicals, color temperature, time of day. Diagram if useful."),
    (
        "7. Color grade recipe",
        "From measured numbers → reproducible recipe: WB, contrast curve, black point, split-tone, saturation, LUT family / film stock emulation.",
    ),
    (
        "8. Camera movement",
        "Per shot: move, speed, rig (tripod, gimbal, handheld, drone, slider, dolly) — INFERRED from measured flow.",
    ),
    ("9. Edit & rhythm", "ASL, cuts/min, pacing curve, cut-on-beat, J/L cuts, speed ramps, transitions, text-on-screen timing."),
    ("10. Sound design", "Music (genre, BPM, identifiable track?), SFX, VO, silence, mix levels, ducking."),
    ("11. Typography & graphics", "Caption style, fonts (closest match), position, animation, stickers, UI overlays."),
    (
        "12. Tools & production stack",
        "Likely camera/phone, editor (CapCut/Premiere/Resolve/After Effects), AI generators, templates — with the tell-tale sign that supports each inference.",
    ),
    (
        "13. Replication plan",
        "A) AI path (image → video prompts per shot, model choice) · B) Live-action path (gear, crew, locations, shot order) · C) Post (edit, grade, sound, export).",
    ),
    ("14. Prompt pack", "Per shot: image prompt + motion prompt + negative prompt, matching the measured palette/aspect/motion."),
    (
        "15. Fidelity check",
        "After rebuilding: run `revideo compare original/ replica/` and record the score + what still differs.",
    ),
    ("16. Open questions / unknowns", "Everything that could not be determined, and what would resolve it."),
]


def write_dossier_template(r: dict, path: str) -> None:
    fp = r["fingerprint"]
    L = [
        f"# Reverse-engineering dossier — {r['source']['platform'].get('title') or r['source']['input']}\n",
        "Evidence tags: **[M]** measured · **[O]** observed in frame · **[I]** inferred · **[V]** verified against an external source · **[?]** unknown.\n",
        "Numbers come from `analysis.json` / `report.md`. Do not restate a number without its tag.\n",
        f"_Key measurements: {fp['shot_count']} shots · ASL {fp['asl_sec']} s · {fp['cuts_per_minute']} cuts/min · "
        f"AR {fp['active_picture_aspect_ratio']} ({fp['active_picture_format_guess']}) · "
        f"look: {', '.join((fp.get('global_grade') or {}).get('look_labels', []))}_\n",
    ]
    for title, hint in DOSSIER_SECTIONS:
        L.append(f"## {title}\n\n<!-- {hint} -->\n\nTODO\n")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(L))


# ─────────────────────────────── HTML report ───────────────────────────────

_CSS = """
:root{color-scheme:light;--bg:#fcfcfb;--panel:#f3f2ee;--line:#dedcd5;--ink:#0b0b0b;--ink2:#52514e;--ink3:#7a7974;
--accent:#2a78d6;--ok:#008300}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){color-scheme:dark;--bg:#1a1a19;--panel:#242422;
--line:#3a3a37;--ink:#ffffff;--ink2:#c3c2b7;--ink3:#8f8e86;--accent:#3987e5;--ok:#3fae3f}}
:root[data-theme="dark"]{color-scheme:dark;--bg:#1a1a19;--panel:#242422;--line:#3a3a37;--ink:#fff;--ink2:#c3c2b7;
--ink3:#8f8e86;--accent:#3987e5;--ok:#3fae3f}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.5 system-ui,-apple-system,
"Segoe UI",Roboto,sans-serif}main{max-width:1180px;margin:0 auto;padding:24px 16px 64px}
h1{font-size:24px;margin:0 0 4px;overflow-wrap:anywhere}h2{font-size:17px;margin:36px 0 12px}.sub{color:var(--ink2);margin:0 0 20px}
.tiles{display:grid;grid-template-columns:repeat(auto-fit,minmax(130px,1fr));gap:10px}
.legend,code{overflow-wrap:anywhere}
.tile{background:var(--panel);border-radius:10px;padding:12px 14px}.tile b{display:block;font-size:22px}
.tile span{color:var(--ink2);font-size:13px}.strip{display:flex;height:44px;border-radius:8px;overflow:hidden;gap:1px;
background:var(--bg)}.strip div{min-width:1px}.axis{display:flex;justify-content:space-between;color:var(--ink3);
font-size:12px;margin-top:4px}svg text{fill:var(--ink2);font-size:11px}.bar{fill:var(--accent)}
.bar:hover{opacity:.75}.grid{stroke:var(--line)}.sw{display:flex;flex-wrap:wrap;gap:8px}.sw div{display:flex;
align-items:center;gap:6px;font:12px ui-monospace,monospace;color:var(--ink2)}.sw i{width:22px;height:22px;
border-radius:5px;display:inline-block;border:1px solid var(--line)}.tags span{display:inline-block;
background:var(--panel);border-radius:99px;padding:2px 10px;margin:0 6px 6px 0;font-size:13px}
.scroll{overflow-x:auto}table{border-collapse:collapse;width:100%;font-size:13px}th,td{text-align:left;
padding:8px;border-bottom:1px solid var(--line);vertical-align:top}th{color:var(--ink2);font-weight:600}
td img{width:132px;border-radius:6px;display:block}.mini i{width:14px;height:14px;border-radius:3px;
display:inline-block;margin-right:2px}.v{color:var(--ok);font-weight:600}.muted{color:var(--ink3)}
.legend{font-size:13px;color:var(--ink2)}.kv{display:grid;grid-template-columns:auto 1fr;gap:4px 16px;font-size:14px}
.kv dt{color:var(--ink2)}.kv dd{margin:0}
"""


def _e(x) -> str:
    return html.escape(str(x))


def _pacing_svg(curve: list[int], window: float = 5) -> str:
    if not curve:
        return ""
    w, h, pl, pb, pt = 760, 170, 30, 22, 10
    n, top = len(curve), max(max(curve), 1)
    bw = (w - pl) / n
    bar_w = min(bw - 2, 48)
    ticks = sorted({0, top // 2, top})
    out = [f'<svg viewBox="0 0 {w} {h}" width="100%" role="img" aria-label="Cuts per {window}-second window">']
    for t in ticks:
        y = pt + (h - pb - pt) * (1 - t / top)
        out.append(
            f'<line class="grid" x1="{pl}" x2="{w}" y1="{y:.1f}" y2="{y:.1f}"/>'
            f'<text x="{pl - 6}" y="{y + 4:.1f}" text-anchor="end">{t}</text>'
        )
    for i, c in enumerate(curve):
        bh = (h - pb - pt) * c / top
        x = pl + i * bw + (bw - bar_w) / 2
        # hit target spans the whole slot so thin or zero-height bars still show their tooltip
        out.append(
            f"<g><title>{i * window:g}–{(i + 1) * window:g} s: {c} cut{'s' if c != 1 else ''}</title>"
            f'<rect x="{pl + i * bw:.1f}" y="{pt}" width="{bw:.1f}" height="{h - pb - pt}" fill="transparent"/>'
            f'<rect class="bar" x="{x:.1f}" y="{h - pb - bh:.1f}" width="{max(1, bar_w):.1f}" '
            f'height="{bh:.1f}" rx="3"/></g>'
        )
        if n <= 24 or i % max(1, n // 12) == 0:
            out.append(f'<text x="{pl + i * bw + bw / 2:.1f}" y="{h - 6}" text-anchor="middle">{i * window:g}s</text>')
    out.append("</svg>")
    return "".join(out)


def write_html_report(r: dict, path: str) -> None:
    from .media_report import forensics_html

    fp, v, meta = r["fingerprint"], r["source"]["video"], r["source"]["platform"]
    title = meta.get("title") or os.path.basename(str(r["source"]["input"]))
    g = fp.get("global_grade") or {}
    dur = fp["duration_sec"] or 1
    tiles = [
        (fp["shot_count"], "shots"),
        (f"{fp['asl_sec']} s", "average shot length"),
        (fp["cuts_per_minute"], "cuts / minute"),
        (f"{fp['hook']['first_shot_sec']} s", "first shot (hook)"),
        (f"{fp['active_picture_aspect_ratio']}", f"active AR · {fp['active_picture_format_guess']}"),
        (fp.get("tempo_bpm_estimate") or "–", "tempo BPM (est.)"),
        (
            f"{round((fp.get('cuts_on_beat_ratio') or 0) * 100)} %" if fp.get("cuts_on_beat_ratio") is not None else "–",
            "cuts on beat",
        ),
    ]
    strip = "".join(
        f'<div style="flex:{max(s["duration_sec"], 0.001) / dur:.5f};background:{(s.get("palette") or [{"hex": "#888"}])[0]["hex"]}"'
        f' title="#{s["index"]} · {s["start_tc"]} · {s["duration_sec"]}s"></div>'
        for s in r["shots"]
    )
    rows = []
    for s in r["shots"]:
        fr = s.get("framing") or {}
        thumb = s.get("keyframes", {}).get("mid")
        img = f'<img loading="lazy" src="{_e(thumb)}" alt="shot {s["index"]}">' if thumb else ""
        chips = "".join(f'<i title="{c["hex"]}" style="background:{c["hex"]}"></i>' for c in s.get("palette", [])[:5])
        ref = s.get("reference_match")
        ref_html = f'<span class="v">{_e(_ref_label(ref))}</span>' if ref else '<span class="muted">–</span>'
        size = (fr.get("faces") or {}).get("shot_size_estimate") or "–"
        cells = [
            str(s["index"]),
            img,
            f'{s["start_tc"]}<br><span class="muted">{s["duration_sec"]} s</span>',
            _e(s["transition_in"]),
            _e((s.get("camera") or {}).get("type", "–")),
            _e(size),
            _e(fr.get("framing_guess", "–")),
            f'<span class="mini">{chips}</span>',
            ref_html,
        ]
        rows.append("<tr>" + "".join(f"<td>{c}</td>" for c in cells) + "</tr>")
    sw = "".join(
        f'<div><i style="background:{c["hex"]}"></i>{c["hex"]} · {c["share"] * 100:.0f}%</div>'
        for c in fp.get("global_palette", [])
    )
    kv = ""
    if g:
        kv = "".join(
            f"<dt>{_e(k)}</dt><dd>{_e(val)}</dd>"
            for k, val in (
                ("Luma mean / p5·p50·p95", f"{g['luma_mean']} / {g['luma_p5_p50_p95']}"),
                ("Contrast σ", g["contrast_std"]),
                ("Black point L*", g["black_point_L"]),
                ("Saturation", g["saturation_mean"]),
                ("White balance a*, b*", g["white_balance_ab"]),
                ("Shadows / highlights", f"{g['shadows_hue']} / {g['highlights_hue']}"),
            )
        )
    tx = "".join(f"<tr><td class=muted>{t['start']:.2f}</td><td>{_e(t['text'])}</td></tr>" for t in r.get("transcript") or [])
    meta_bits = " · ".join(
        _e(f"{k}: {meta[k]}") for k in ("uploader", "upload_date", "view_count", "track", "artist") if meta.get(k)
    )
    doc = f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Video Teardown</title><style>{_CSS}</style></head>
<body><main>
<h1>{_e(title)}</h1>
<p class="sub">{v["width"]}×{v["height"]} · {v["fps"]} fps · {v["duration_sec"]} s{(" · " + meta_bits) if meta_bits else ""}</p>
<p class="legend">Everything on this page is <b>measured</b> [M]. Italic labels are heuristics [I].
Verified film references [V] come from <code>revideo match-ref</code>. Interpretation lives in <code>dossier.md</code>.</p>
<div class="tiles">{"".join(f'<div class="tile"><b>{_e(a)}</b><span>{_e(b)}</span></div>' for a, b in tiles)}</div>
<h2>Edit timeline — one block per shot, width = duration, color = dominant color</h2>
<div class="strip">{strip}</div><div class="axis"><span>0 s</span><span>{dur:.1f} s</span></div>
<h2>Pacing — cuts per {fp["pacing_window_sec"]:g}-second window</h2>{_pacing_svg(fp.get("pacing_curve", []), fp["pacing_window_sec"])}
<h2>Color &amp; grade</h2><div class="sw">{sw}</div>
<p class="tags">{"".join(f"<span><i>{_e(t)}</i></span>" for t in g.get("look_labels", []))}</p>
<dl class="kv">{kv}</dl>
<h2>Shots</h2><div class="scroll"><table><thead><tr><th>#</th><th>Frame</th><th>In</th><th>Transition</th>
<th>Camera</th><th>Size</th><th>Framing</th><th>Palette</th><th>Reference</th></tr></thead><tbody>{"".join(rows)}</tbody></table></div>
{f'<h2>Transcript</h2><div class="scroll"><table>{tx}</table></div>' if tx else ""}
{forensics_html(r.get("forensics"))}
<p class="legend" style="margin-top:32px">revideo {r["tool"]["version"]} · detector {r["tool"]["detector"]["engine"]}</p>
</main></body></html>"""
    with open(path, "w", encoding="utf-8") as f:
        f.write(doc)
