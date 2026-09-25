"""Reports for photos and audio files, plus the forensics block shared with video reports."""

from __future__ import annotations

import json
import os

from .report import _CSS, _e, _swatches


def forensics_md(meta: dict | None) -> list[str]:
    if not meta:
        return []
    L = ["\n## Production fingerprints (metadata)"]
    for h in meta.get("tool_fingerprints", []):
        L.append(f"- **{h['tool']}** ({h['category']}) — {h['means']} · evidence: `{h['evidence'][:90]}`")
    for h in meta.get("tools_mentioned_in_post", []):
        L.append(f"- mentioned by the creator: **{h['tool']}** · `{h['evidence'][:90]}`")
    if not meta.get("tool_fingerprints"):
        L.append("- no tool strings in the file")
    if meta.get("metadata_stripped_likely"):
        L.append(
            "- *metadata looks stripped (typical after a social platform re-encode): tool evidence must come from the content itself*"
        )
    x = meta.get("xmp") or {}
    if x.get("camera_raw_settings"):
        L.append(f"- Lightroom/Camera Raw settings embedded (exact edit recipe): `{json.dumps(x['camera_raw_settings'])}`")
    if (meta.get("png_text") or {}).get("parameters"):
        L.append(f"- AI generation parameters embedded: `{str(meta['png_text']['parameters'])[:400]}`")
    if (meta.get("png_text") or {}).get("prompt"):
        L.append("- ComfyUI prompt graph embedded (see analysis.json → forensics.png_text.prompt)")
    if meta.get("c2pa_manifest_present"):
        L.append("- C2PA / Content Credentials signature bytes present (not validated)")
    for s in (meta.get("container") or {}).get("streams", []):
        L.append(f"- stream {s['type']}: `{s['desc'][:140]}`")
    return L


def forensics_html(meta: dict | None) -> str:
    if not meta:
        return ""
    items = [
        f"<li><b>{_e(h['tool'])}</b> <span class=muted>({_e(h['category'])})</span> — {_e(h['means'])}"
        f"<br><code>{_e(h['evidence'][:120])}</code></li>"
        for h in meta.get("tool_fingerprints", [])
    ] + [f"<li>creator mentions <b>{_e(h['tool'])}</b></li>" for h in meta.get("tools_mentioned_in_post", [])]
    if not items:
        items = ["<li class=muted>no tool strings in the file</li>"]
    note = (
        "<p class=legend>Metadata looks stripped (typical after a platform re-encode): tool evidence must come from the content itself.</p>"
        if meta.get("metadata_stripped_likely")
        else ""
    )
    crs = (meta.get("xmp") or {}).get("camera_raw_settings")
    crs_html = (
        "<h3>Embedded Lightroom / Camera Raw recipe</h3><dl class=kv>"
        + "".join(f"<dt>{_e(k)}</dt><dd>{_e(v)}</dd>" for k, v in crs.items())
        + "</dl>"
        if crs
        else ""
    )
    return f"<h2>Production fingerprints [M]</h2><ul>{''.join(items)}</ul>{note}{crs_html}"


def _dl(pairs) -> str:
    return (
        "<dl class=kv>" + "".join(f"<dt>{_e(k)}</dt><dd>{_e(v)}</dd>" for k, v in pairs if v not in (None, "", [], {})) + "</dl>"
    )


def _page(title: str, sub: str, body: str, version: str) -> str:
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Media Teardown</title><style>{_CSS}
.hero{{max-width:100%;border-radius:10px;margin:8px 0 16px}}</style></head><body><main>
<h1>{_e(title)}</h1><p class="sub">{_e(sub)}</p>
<p class="legend">Everything here is <b>measured</b> [M]; italic labels are heuristics [I]. Interpretation lives in the dossier.</p>
{body}<p class="legend" style="margin-top:32px">revideo {_e(version)}</p></main></body></html>"""


def write_media_reports(r: dict, out_dir: str) -> None:
    title = r["source"]["platform"].get("title") or os.path.basename(str(r["source"]["input"]))
    if r["kind"] == "image":
        im, g, o, fr, cam = r["image"], r["grade"], r["optics"], r["framing"], r["camera_and_lens"]
        L = [
            f"# Measured report (photo) — {title}\n",
            "## Image",
            f"- {im['width']}×{im['height']} · AR {im['aspect_ratio']} → *{im['format_guess']}*",
        ]
        if cam:
            L.append(f"- Camera/lens (EXIF): {cam}")
        L += [
            "\n## Color / grade",
            f"- Palette: {_swatches(r['palette'], 8)}",
            f"- Luma mean {g['luma_mean']} · p5/p50/p95 {g['luma_p5_p50_p95']} · contrast σ {g['contrast_std']} · sat {g['saturation_mean']}",
            f"- Black point L {g['black_point_L']} · WB (a,b) {g['white_balance_ab']} · shadows *{g['shadows_hue']}* / highlights *{g['highlights_hue']}*",
            f"- Look: *{', '.join(g['look_labels'])}*",
            "\n## Optics & composition",
            f"- Depth of field: *{o['depth_of_field_guess']}* (sharp area {o['sharp_area_share']}) · focus at {o['focus_center_norm']}",
            f"- Vignette *{o['vignette_guess']}* ({o['vignette_corner_to_center']}) · grain *{o['grain_guess']}* (σ {o['grain_noise_std']})",
            f"- Clipped highlights {o['clipped_highlights_pct']} % · crushed shadows {o['crushed_shadows_pct']} %",
            f"- Framing *{fr['framing_guess']}* · visual center {fr['visual_center_norm']} · symmetry {fr['symmetry']} · negative space {fr['negative_space']}",
        ]
        if fr.get("faces"):
            L.append(f"- Faces: {fr['faces']['count']} · shot size *{fr['faces']['shot_size_estimate']}*")
        L += forensics_md(r.get("forensics"))
        sw = "".join(
            f'<div><i style="background:{c["hex"]}"></i>{c["hex"]} · {c["share"] * 100:.0f}%</div>' for c in r["palette"]
        )
        body = (
            f'<img class="hero" src="{_e(r["artifacts"]["preview"])}" alt="analyzed photo">'
            f'<h2>Color &amp; grade</h2><div class="sw">{sw}</div>'
            f'<p class="tags">{"".join(f"<span><i>{_e(t)}</i></span>" for t in g["look_labels"])}</p>'
            + _dl(
                [
                    ("Luma mean / p5·p50·p95", f"{g['luma_mean']} / {g['luma_p5_p50_p95']}"),
                    ("Contrast σ", g["contrast_std"]),
                    ("Black point L*", g["black_point_L"]),
                    ("White balance a*, b*", g["white_balance_ab"]),
                    ("Shadows / highlights", f"{g['shadows_hue']} / {g['highlights_hue']}"),
                ]
            )
            + "<h2>Optics &amp; composition</h2>"
            + _dl(
                [
                    ("Depth of field", f"{o['depth_of_field_guess']} (sharp {o['sharp_area_share']})"),
                    ("Vignette", f"{o['vignette_guess']} ({o['vignette_corner_to_center']})"),
                    ("Grain", f"{o['grain_guess']} (σ {o['grain_noise_std']})"),
                    ("Framing", f"{fr['framing_guess']} · center {fr['visual_center_norm']}"),
                    ("Faces / shot size", (fr.get("faces") or {}).get("shot_size_estimate")),
                    *[(k, v) for k, v in cam.items()],
                ]
            )
            + forensics_html(r.get("forensics"))
        )
        sub = f"{im['width']}×{im['height']} · {im['format_guess']}"
    else:
        a = r["audio"]
        k, sp = a.get("key_estimate") or {}, a.get("spectral") or {}
        L = [
            f"# Measured report (audio) — {title}\n",
            "## Sound",
            f"- Duration {a['duration_sec']} s · tempo ≈ **{a['tempo_bpm_estimate']} BPM** · key ≈ **{k.get('key', '–')}** (r {k.get('confidence_r')}, runner-up {k.get('runner_up')})",
            f"- Level mean {a['loudness_mean_dbfs']} dBFS · peak {a['loudness_peak_dbfs']} dBFS · crest {sp.get('crest_factor_db')} dB · silence {a['silence_pct']} %",
            f"- Spectrum: {sp.get('energy_share_pct')} · centroid {sp.get('spectral_centroid_hz')} Hz → *{sp.get('brightness_guess')}*",
            f"- {a['note']}",
        ]
        if r.get("transcript"):
            L.append("\n## Transcript")
            L += [f"- `{t['start']:.2f}` {t['text']}" for t in r["transcript"]]
        L += forensics_md(r.get("forensics"))
        body = (
            "<h2>Sound</h2>"
            + _dl(
                [
                    ("Tempo (est.)", f"{a['tempo_bpm_estimate']} BPM"),
                    ("Key (est.)", f"{k.get('key')} · r {k.get('confidence_r')} · runner-up {k.get('runner_up')}"),
                    ("Level mean / peak", f"{a['loudness_mean_dbfs']} / {a['loudness_peak_dbfs']} dBFS"),
                    ("Crest factor", f"{sp.get('crest_factor_db')} dB"),
                    ("Energy by band", sp.get("energy_share_pct")),
                    ("Brightness", f"{sp.get('brightness_guess')} ({sp.get('spectral_centroid_hz')} Hz)"),
                    ("Silence", f"{a['silence_pct']} %"),
                ]
            )
            + forensics_html(r.get("forensics"))
        )
        sub = f"{a['duration_sec']} s audio"
    with open(os.path.join(out_dir, "report.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(L) + "\n")
    with open(os.path.join(out_dir, "report.html"), "w", encoding="utf-8") as f:
        f.write(_page(title, sub, body, r["tool"]["version"]))
