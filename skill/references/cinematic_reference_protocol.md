# Cinematic reference protocol

Goal: for each shot or sequence, state **what film/work it quotes or imitates**, **who made it**
(director, DP), **where exactly** (timecode / frame), and **what is borrowed** — each item tagged.

## 1. Types of reference (be explicit about which one)

| Type | Meaning | Maximum evidence you can reach |
|---|---|---|
| **Direct footage** | The frames *are* from the film (edits, fan cuts, "cinematic" reels) | [V] via `match-ref` (exact frame) |
| **Recreation / homage** | New footage restaging a known shot | [V] only if the creator says so; otherwise [I] with side-by-side |
| **Stylistic lineage** | Borrows a director's/DP's signature (symmetry, color, movement) | [I] — style is never "verified" |
| **Genre convention** | Common grammar (e.g. dolly zoom, teal-orange blockbuster grade) | [I]; say it's a convention, not a quote |

## 2. Candidate generation (per shot)
Look at the keyframe and write down the *signals*:
- Aspect ratio [M] (2.39 scope, 1.85, 1.33 Academy…) and letterbox.
- Palette/grade [M] and texture (grain, halation, softness) [O].
- Composition signature [O]: one-point perspective, centered symmetry, deep staging, dutch angle.
- Production design, costume, era, locations, recognizable actors [O].
- Camera signature [M]/[O]: long steadicam, whip pans, snap zooms, locked-off wides.
Then propose up to 3 candidates: `Film (Year) — Director — DP — scene — confidence 0–1 — reason`.
Recognizing actors: name them only if they are publicly known performers in the candidate film; do
not identify private individuals.

## 3. Verification ladder (stop at the highest rung you can reach)
1. **Frame match** (`revideo index-ref` + `match-ref`) → exact frame + timecode + crop + mirrored → **[V]**.
2. **Creator statement** (caption, description, comments by the author, BTS post) → **[V]**, cite it.
3. **Credits database** for director/DP/year once the film is fixed (e.g. IMDb, TMDB) → **[V]** for credits.
4. **Still libraries / reverse image search** on the keyframe (e.g. Google Lens, TinEye, FILMGRAB,
   ShotDeck) → a matching still is strong evidence; still say where it was found.
5. Nothing reachable → keep **[I]** with the reasons. Never upgrade a guess by repeating it.

## 4. Record format (dossier §4)
```
Shot 07 · 00:00:12:04–00:00:13:10
- Reference: The Shining (1980) — Stanley Kubrick — DP John Alcott  [V: match-ref frame 88213, 01:01:14:13, crop 9:16]
- Type: direct footage, mirrored
- Borrowed: one-point perspective corridor, symmetrical blocking, steadicam push-in
- Palette overlap: ΔE 6.2 vs reference frame [M]
```
(The example is illustrative of the format only.)

## 5. Timecode conventions
- `HH:MM:SS:FF`, non-drop-frame, at the reference file's fps.
- Always state which file/edition the timecode refers to (theatrical vs extended, streaming version,
  Blu-ray) — timecodes differ between editions and PAL speed-up (25 fps) shifts them by ~4 %.
