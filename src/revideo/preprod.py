"""Pre-production pack for a video analysis: shot list CSV, printable storyboard and call-sheet draft.

Timing, moves, palettes and keyframes are measured [M]. Setup grouping, rigs and shooting order are
recommendations [I]. Date, location, cast and crew are left as blanks for the user to fill.
"""

from __future__ import annotations

import csv
import json
import os

from .advise import RIG, TIERS, _move_key, _prompt
from .report import _CSS, _e

HANDLE_SEC = 1.0  # extra seconds to roll before and after each measured duration (editing margin) [I]
COLUMNS = [
    "shot",
    "setup",
    "in_tc",
    "out_tc",
    "duration_sec",
    "record_at_least_sec",
    "move",
    "shot_size",
    "depth_of_field",
    "palette",
    "look",
    "rig_phone",
    "rig_creator",
    "rig_pro",
    "keyframe",
    "ai_prompt",
    "notes",
]


def rows(r: dict) -> list[dict]:
    """One row per measured shot, with a setup id shared by shots that can be filmed together."""
    if r.get("kind", "video") != "video":
        raise SystemExit("preprod needs a video analysis (photos and audio have no shots)")
    ar = r["fingerprint"]["active_picture_format_guess"].split(" ")[0]
    setups: dict[tuple, str] = {}
    out = []
    for s in r["shots"]:
        cam = (s.get("camera") or {}).get("type", "static")
        key = _move_key(cam)
        look = (s.get("grade") or {}).get("look_labels", [])[:3]
        n = len(setups)
        setup = setups.setdefault((key, look[0] if look else ""), chr(ord("A") + n) if n < 26 else f"S{n + 1}")
        size = ((s.get("framing") or {}).get("faces") or {}).get("shot_size_estimate")
        dof = ((s.get("optics") or {}).get("depth_of_field_guess") or "").split(" ")[0]
        hexes = [c["hex"] for c in s.get("palette", [])]
        p = _prompt(
            {
                "shot_size": size,
                "move": cam.replace("_", " "),
                "dof": dof,
                "hexes": hexes,
                "look": look,
                "ar": ar,
                "duration": s["duration_sec"],
            }
        )
        rig = RIG[key]
        out.append(
            {
                "shot": s["index"],
                "setup": setup,
                "in_tc": s["start_tc"],
                "out_tc": s["end_tc"],
                "duration_sec": s["duration_sec"],
                "record_at_least_sec": round(s["duration_sec"] + 2 * HANDLE_SEC, 2),
                "move": cam,
                "shot_size": size or "",
                "depth_of_field": dof,
                "palette": " ".join(hexes[:5]),
                "look": ", ".join(look),
                "rig_phone": rig[0],
                "rig_creator": rig[1],
                "rig_pro": rig[2],
                "keyframe": (s.get("keyframes") or {}).get("mid", ""),
                "ai_prompt": p["prompt"],
                "notes": "",
            }
        )
    return out


def shooting_order(rs: list[dict]) -> list[tuple[str, list[dict]]]:
    """Group by setup (same rig and look), in order of first appearance; longest shot first inside a setup."""
    groups: dict[str, list[dict]] = {}
    for row in rs:
        groups.setdefault(row["setup"], []).append(row)
    return [(k, sorted(v, key=lambda x: -x["duration_sec"])) for k, v in groups.items()]


def callsheet(r: dict, rs: list[dict]) -> str:
    fp, v = r["fingerprint"], r["source"]["video"]
    title = r["source"]["platform"].get("title") or os.path.basename(str(r["source"]["input"]))
    L = [
        f"# Call sheet (draft) — {title}\n",
        "> Shot timing, moves and palettes are **[M]** from analysis.json. Setups, rigs and order are "
        "recommendations **[I]**. Fill every `____` before sharing.\n",
        "| Field | Value |",
        "|---|---|",
        "| Production | ____ |",
        "| Shoot date / call time | ____ |",
        "| Location(s) | ____ |",
        "| Director / DP / sound | ____ |",
        "| Cast | ____ |",
        f"| Deliverable | {v['width']}×{v['height']} @ {v['fps']} fps · {fp['duration_sec']} s · "
        f"{fp['active_picture_format_guess']} [M] |",
        f"| Shots / setups | {len(rs)} shots · {len({x['setup'] for x in rs})} setups |",
        f"| Minimum screen time to record | {round(sum(x['record_at_least_sec'] for x in rs), 1)} s per take "
        f"(measured {fp['duration_sec']} s + {HANDLE_SEC:g} s handles each side) |",
    ]
    bpm = fp.get("tempo_bpm_estimate")
    if bpm:
        L.append(f"| Playback / music | ≈ {bpm} BPM, one beat every {60 / bpm:.3f} s [M]; play it on set for movement timing |")
    L += ["", "## Shooting order (grouped by setup, not by edit order)"]
    for setup, group in shooting_order(rs):
        first = min(group, key=lambda x: x["shot"])
        look = first["look"].split(",")[0] or "look n/a"
        L += [
            "",
            f"### Setup {setup} — {_move_key(first['move'])} rig · {look}",
            f"- Rig: phone *{first['rig_phone']}* · creator *{first['rig_creator']}* · pro *{first['rig_pro']}*",
            f"- Palette to dress and light for (shot {first['shot']}): {first['palette']}",
            "",
            "| Shot | Edit TC | Dur (s) | Roll ≥ (s) | Size | DOF | Takes | Circle |",
            "|---|---|---|---|---|---|---|---|",
            *[
                f"| {x['shot']} | {x['in_tc']} | {x['duration_sec']} | {x['record_at_least_sec']} | "
                f"{x['shot_size'] or '–'} | {x['depth_of_field'] or '–'} | ____ | ____ |"
                for x in group
            ],
        ]
    L += [
        "",
        "## Gear by tier [I]",
        *[f"- **{TIERS[t]}**: " + "; ".join(sorted({x[f"rig_{t}"] for x in rs})) for t in ("phone", "creator", "pro")],
        "",
        "## Checklist",
        "- Lock white balance and exposure per setup; match the palette above before rolling.",
        "- Slate or clap each take; log the circled take per shot here.",
        "- Rights: third-party music, footage, faces or logos from the original need permission.",
    ]
    return "\n".join(L) + "\n"


def storyboard_html(r: dict, rs: list[dict]) -> str:
    title = r["source"]["platform"].get("title") or os.path.basename(str(r["source"]["input"]))
    cards = []
    for x in rs:
        sw = "".join(f'<i style="background:{_e(h)}" title="{_e(h)}"></i>' for h in x["palette"].split())
        img = f'<img src="{_e(x["keyframe"])}" alt="shot {x["shot"]} keyframe">' if x["keyframe"] else "<div class=noimg></div>"
        cards.append(
            f"""<figure class=card>{img}<figcaption>
<b>#{x["shot"]}</b> · setup {_e(x["setup"])} · {_e(x["in_tc"])} · <b>{x["duration_sec"]} s</b>
<div class=meta>{_e(x["move"])} · {_e(x["shot_size"] or "size –")} · DOF {_e(x["depth_of_field"] or "–")}</div>
<div class=pal>{sw}</div><div class=prompt>{_e(x["ai_prompt"])}</div>
<div class=notes>Notes: ______________________</div></figcaption></figure>"""
        )
    css = """.board{display:grid;grid-template-columns:repeat(auto-fill,minmax(240px,1fr));gap:14px}
.card{margin:0;border:1px solid #8884;border-radius:10px;overflow:hidden;break-inside:avoid}
.card img,.noimg{width:100%;aspect-ratio:16/9;object-fit:contain;background:#111;display:block}
.card figcaption{padding:8px 10px;font-size:13px;line-height:1.4}
.meta,.notes{opacity:.75}.prompt{font-size:11px;opacity:.7;margin-top:4px}
.pal i{display:inline-block;width:18px;height:12px;margin-right:2px;border-radius:2px}
@media print{body{background:#fff;color:#000}.board{grid-template-columns:repeat(3,1fr)}}"""
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Storyboard</title>
<style>{_CSS}{css}</style></head><body><main>
<h1>Storyboard — {_e(title)}</h1>
<p class=legend>Frames, timing, moves and palettes are measured [M] from the original; setups and prompts are
recommendations [I]. Print it (3 per row) or share the page.</p>
<div class=board>{"".join(cards)}</div></main></body></html>"""


def write_preprod(analysis_dir: str) -> dict:
    with open(os.path.join(analysis_dir, "analysis.json"), encoding="utf-8") as f:
        r = json.load(f)
    rs = rows(r)
    paths = {
        k: os.path.join(analysis_dir, n)
        for k, n in (("csv", "shotlist.csv"), ("storyboard", "storyboard.html"), ("callsheet", "callsheet.md"))
    }
    with open(paths["csv"], "w", newline="", encoding="utf-8-sig") as f:  # BOM so Excel opens UTF-8 correctly
        w = csv.DictWriter(f, fieldnames=COLUMNS)
        w.writeheader()
        w.writerows(rs)
    with open(paths["storyboard"], "w", encoding="utf-8") as f:
        f.write(storyboard_html(r, rs))
    with open(paths["callsheet"], "w", encoding="utf-8") as f:
        f.write(callsheet(r, rs))
    return paths
