---
name: reverse-engineering-video
description: Full reverse engineering of a video (reel, TikTok, Short, ad, music video, film clip). Measures cuts, rhythm, color grade, framing, camera movement and sound with the `revideo` CLI, then identifies cinematic references (film, director, DP, exact timecode/frame), infers the production stack and workflow, and writes an evidence-tagged dossier plus a replication plan and prompt pack, validated by a fidelity score. Use when the user shares a video/link and asks how it was made, what it references, which tools/workflow were used, or to copy/recreate/replicate it — in any language ("ingeniería inversa", "cómo se hizo", "de qué película es", "replícalo", "reverse-engineer this").
---

# Reverse engineering of video content

The goal is not to summarize a video. It is to recover **how it was made**, **what it borrows from**,
and **how to rebuild it** — with every claim traceable to evidence.

## Non-negotiable rules

1. **Measure before you interpret.** Run `revideo analyze` first. Never describe shots you have not
   looked at (keyframes / contact sheet). If you cannot see images, say so and stop at the measured report.
2. **Tag every claim**: **[M]** measured · **[O]** observed in a frame · **[I]** inferred ·
   **[V]** verified against an external source · **[?]** unknown. A film reference, a director, a
   timecode, a tool, a lens — all are **[I]** until verified.
3. **Never invent** a film, a timecode, a director, a DP, a song, a quote or a statistic. A reference
   is only **[V]** if (a) `revideo match-ref` found the frame, or (b) a citable source (credits
   database, ASC/BTS interview, the creator's own post) confirms it. Otherwise give candidates with
   confidence and the reason.
4. **Numbers come from `analysis.json`.** Quote them, don't eyeball them.
5. **Separate technique from assets.** Replicate the *technique* (rhythm, framing, grade, movement,
   structure). Tell the user when the source contains third-party film footage, music, faces or
   logos that they would need rights to reuse. One sentence, no lecture.

## Workflow

### Phase 0 — Scope
If > 3 min, ask whether to analyze everything or a segment (the first 3–5 s usually carry most of
the value for short-form). Default: whole video.

### Phase 1 — Measure (tool)
```bash
revideo analyze "<url-or-file>" -o runs/<name>          # add --whisper small if no subtitles
```
Produces `analysis.json` (schema: `docs/SCHEMA.md`), `report.html` + `report.md` (measured),
`dossier.md` (template), `contact_sheet.jpg`, `keyframes/shot_XXX_{in,mid,out}.jpg`, `audio.wav`.
Check `tool.detector` first: `flash_rejected_cuts` and `container_reported_frames` tell you when the
source was tricky. If cuts look wrong compared with the contact sheet, re-run with `--threshold 0.2`
(more cuts) or `0.45` (fewer), or try `--engine scenedetect` — and say which setting you used.
Dissolves and slow cross-fades can be missed: check with the contact sheet and note them as [O].

### Phase 2 — Observe (vision)
Open `contact_sheet.jpg` first (whole edit at a glance), then every `*_mid.jpg`, and `in/out` frames
for shots whose camera type is not static. For each shot fill `shots[i].interpretation` fields in
your head/dossier: shot size, angle, lens estimate, lighting, subject action, on-screen text,
function in the story. Use the vocabulary in `references/shot_glossary.md`.

### Phase 3 — Cinematic references
Follow `references/cinematic_reference_protocol.md`:
1. Propose candidates per shot/sequence (film, year, director, DP, scene) with the *visual reason*
   (composition, palette, blocking, aspect ratio, grain, production design). Tag **[I]** + confidence.
2. If the user has the candidate film file (or a trailer/clip), verify:
   ```bash
   revideo index-ref film.mkv -o refs/film.npz --title "…" --director "…" --year 1999
   revideo match-ref runs/<name> refs/film.npz
   ```
   A hit gives the exact **film frame and timecode**, *which* frame of the reel matched
   (`query_keyframe`, `query_timecode`), the estimated film timecode where the shot starts
   (`film_shot_start_estimate`, assumes 1× speed), the crop (`9:16@center`, `4:5@left`…) and whether
   it was mirrored → tag **[V]**. A shot with `match: false` has **no** timecode: do not invent one.
   Timecodes belong to the indexed file (edition, fps) — say which file.
3. Without the file, point to where the user can verify (reverse image search on the keyframe,
   still libraries, credits databases) and keep **[I]**.
4. Also identify *stylistic* references (director/DP signatures, movements: e.g. symmetrical
   one-point perspective, handheld verité, neon-noir) — these are always **[I]** unless the creator
   said so.

### Phase 4 — Grade, sound, graphics, stack
- Turn `global_grade` + palettes into a **grade recipe** (`references/color_grade_recipes.md`).
- Sound: BPM estimate **[M]**, `cuts_on_beat_ratio` **[M]**, genre/track identification **[I]**
  (verify with the platform's music tag in `source.platform.track/artist` if present **[V]**).
- Tools/workflow: use `references/tool_fingerprints.md`. Every tool claim needs a tell-tale sign.

### Phase 5 — Dossier
Complete every section of `dossier.md` (16 sections). Unknowns go in section 16, not hidden.

### Phase 6 — Replication plan + prompt pack
Use `references/replication_template.md`:
- **A. AI path**: per shot image prompt + motion prompt + negative prompt, matching measured aspect
  ratio, palette hexes, camera move and duration; model suggestions.
- **B. Live-action path**: gear, lens, lighting setup, blocking, shot order, crew.
- **C. Post**: edit list with exact durations (from `shots[*].duration_sec`), grade recipe, sound,
  captions, export specs for the target platform.

### Phase 7 — Round-trip validation
After the user (or you) produce a replica:
```bash
revideo analyze replica.mp4 -o runs/<name>-replica
revideo compare runs/<name> runs/<name>-replica
```
Report the fidelity score and the components that differ; iterate on the lowest component.

## Output to the user
1. 5–8 line summary (what it is, the core trick, top references with tags).
2. The dossier (link/path) and the prompt pack.
3. What could not be determined and how to resolve it.
