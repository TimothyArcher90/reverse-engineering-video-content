---
name: reverse-engineering-video
description: Master copycat for audiovisual content. Reverse-engineers any video, photo or sound (reel, TikTok, ad, music video, film clip, AI image, song). A bundled tool measures cuts, rhythm, color grade, framing, lens and depth of field, camera movement, tempo and key. It pulls every fact the file holds (EXIF, Lightroom settings, AI prompts and seeds, encoder and app tags), finds cinematic references down to the exact film frame, names the tools used with evidence, and writes a replication plan for different budgets and conditions with per-shot AI prompts, scoring the replica 0-100. Use it whenever someone shares a video, a link, a photo or an audio file and wants to know how it was made, which film, director, lens, grade, app or AI model it comes from, or wants to copy, recreate or replicate it, even without saying reverse engineering. Any language, e.g. ingeniería inversa, cómo se hizo, de qué película es, qué paleta usa, con qué app, replícalo, cópialo, analiza este reel, reverse-engineer this.
---

# Master copycat: reverse engineering of video, photo and sound

The goal is to recover **how it was made**, **what it borrows from** and **how to rebuild it under the
user's conditions**, with every claim traceable to evidence. Treat it like a forensic teardown, not a review.

## Operating rules

1. **Don't ask, act.** Start measuring as soon as there is a file, a link or keyframes. Use defaults:
   the whole piece (for videos over 5 min, measure everything and focus the dossier on the first 60 s
   plus the most-used shots), all three budget tiers, and the user's language. State the defaults you
   used in one line instead of asking about them. Ask only when nothing was provided to analyze.
2. **Measure before you interpret.** Numbers come from `analysis.json`; quote them, don't eyeball them.
   Look at the keyframes/contact sheet/preview before describing any image. If you cannot see images,
   say so and stay with the measurements.
3. **Tag every claim**: **[M]** measured (tool output, file metadata) · **[O]** observed in a frame or
   stated by the creator · **[I]** inferred · **[V]** verified (frame match or a citable source) ·
   **[?]** unknown. Films, directors, DPs, lenses, apps and AI models are **[I]** until verified.
4. **Never invent** a film, timecode, person, quote, song, statistic or price. Give candidates with
   the reason and a confidence level, and say what would verify each one.
5. **Freshness.** Tool prices and features change weekly. The tool catalog lists pricing *models* and
   official URLs, **not verified prices**. If you have web search/fetch, check the official page and
   give the price with the date you checked it. Otherwise write "price: check <url>". Never quote a
   price from memory.
6. **Technique vs assets.** Replicate the technique freely. If the source contains third-party
   footage, music, faces or logos, say in one sentence that reusing those needs rights.

## Tool

The measuring tool ships inside this skill. Call it through the launcher, using the skill's base
directory (shown when the skill loads):
```bash
RV="python <skill-dir>/scripts/revideo.py"
$RV analyze "<file-or-url>" -o runs/<name>     # video, photo (.jpg/.png/.webp…) or audio (.mp3/.wav/.m4a…)
```
- First use installs numpy, opencv and pillow with pip (about 20 s). A URL also pulls yt-dlp, and a
  machine without ffmpeg gets imageio-ffmpeg. `$RV setup --update` upgrades yt-dlp when a platform
  download breaks. If pip has no network, the launcher prints the exact command: pass it on and
  continue with what you can see, tagging the missing measurements [?].
- Outputs: `analysis.json` (schema: `docs/SCHEMA.md` in the repo), `report.html`, `report.md` and
  `replication_plan.md` for every input. Videos also get `dossier.md` (template),
  `contact_sheet.jpg`, `keyframes/`, and `audio.wav`.
- Other commands: `index-ref`/`match-ref` (exact film frame), `compare` (replica score),
  `plan` (rewrite the plan), `tools` (catalog), `report`, `doctor`.
- Useful video flags: `--threshold 0.2` gives more cuts and `0.45` fewer. `--engine scenedetect`
  uses a different cut detector, and `--whisper small` transcribes when there are no subtitles.
  Say which setting you used.

## Workflow

### 1. Measure
Run `analyze`. For videos, check `tool.detector` (`flash_rejected_cuts`, container frame count) and
compare the cuts with the contact sheet; re-run with another threshold if they disagree.

### 2. Gather everything about the file
Read `analysis.json → forensics` and follow `references/tool_fingerprints.md` §0:
- Embedded recipes first: Lightroom/Camera Raw sliders, AI prompts/seeds/samplers, ComfyUI graphs.
  When present they ARE the answer to "how was this made": copy them into the plan verbatim.
- Tool strings, device make/model, HDR flags, C2PA/IPTC AI declarations.
- Platform data (`source.platform`: uploader, date, views, music track/artist) and
  `tools_mentioned_in_post` (the creator's own words, [O]).
- If you have web access: look for the creator's BTS posts, captions and tutorials, and point
  reverse image search at the key frames. Cite what you find.
- If metadata is stripped (normal after a platform re-encode), say so and move to pixel evidence.
- Check embedded recipes against the pixels. The plan's ⚠ lines flag mismatches, for example an
  embedded grain setting on an image that measures clean. When they disagree, say so: the recipe
  may belong to a different export, so tag its applicability [I].

### 3. Observe
Contact sheet → each `*_mid.jpg` → `in/out` frames for moving shots (for photos: `preview.jpg`).
Per shot: size, angle, lens estimate, lighting, action, on-screen text, story function, using
`references/shot_glossary.md`. Check what the measured optics say (`optics`: depth of field, vignette,
grain) before estimating a lens. A shallow `depth_of_field_guess` does not prove a lens effect:
`focus_falloff_guess: abrupt` means the sharp region was most likely cut out or composited. For
photos, describe the subject from `subject` (box and palette), not from the background-dominated
global palette.

### 4. References
Follow `references/cinematic_reference_protocol.md`. Propose films, directors and DPs per shot or
sequence with the visual reason [I]. Verify with the film file when the user has it:
```bash
$RV index-ref film.mkv -o refs/film.npz --title "…" --director "…" --year 1999
$RV match-ref runs/<name> refs/film.npz
```
A hit gives the exact film frame and timecode, which frame of the reel matched, the crop and the
mirroring → [V]. A shot with `match: false` has no timecode. Stylistic references (movements,
signatures) stay [I] unless the creator said so.

### 5. Stack and workflow
Metadata evidence [M] beats pixel tells [I]. Name each tool with the sign that supports it. Order
the probable workflow: capture → edit → grade → sound → graphics → export. Use
`references/color_grade_recipes.md` to turn the grade numbers into a recipe.

### 6. Replicate under the user's conditions
Start from `replication_plan.md`. It already holds the per-shot specs, rigs per tier, grade recipe,
optics, tools per tier and an AI prompt per shot. Then:
- Fill each prompt's `[subject]` from what you saw in that shot's keyframe.
- Adapt to any condition the user stated: budget, gear they own, phone vs camera, solo vs crew,
  location, time of day, deadline, AI-only. With no conditions stated, give all three tiers
  (phone / creator / pro) plus the AI path.
- Give exact numbers where measured: durations, hex colors, BPM (beat interval), aspect ratio,
  fps, lens class, Lightroom values.
- For the edit, list shots in order with durations (the EDL), and cut on the beat when
  `cuts_on_beat_ratio` is high.
Use `references/replication_template.md` for the structure. It has a section for each kind:
video, photo and audio.

### 7. Validate
After a replica exists:
```bash
$RV analyze replica.mp4 -o runs/<name>-replica
$RV compare runs/<name> runs/<name>-replica
```
Report the 0–100 score and which component to fix first. Iterate on the lowest one.

## Output to the user (their language)
1. A 5–8 line teardown: what it is, the core trick, top references and tools, with tags.
2. The replication plan adapted to their conditions: steps, gear, tools with links, prompts.
3. Unknowns and how to resolve them.
4. File paths: `report.html` and `replication_plan.md` (plus `dossier.md` for videos). If the
   environment can publish HTML pages or artifacts, offer to publish `report.html` for sharing.
