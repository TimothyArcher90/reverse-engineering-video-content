# Methodology — reverse-engineering standards applied to video

Software and hardware reverse engineering share a few principles that make results trustworthy.
This project applies them to audiovisual content.

| RE principle | What it means here | Where it lives |
|---|---|---|
| **Black-box analysis** — study the artifact, not the author's files | We only have the delivered video. Everything is recovered from pixels and samples. | `revideo analyze` |
| **Layered decomposition** | L0 source & platform metadata → L1 shot boundaries → L2 per-shot color/framing/motion → L3 sound → L4 global fingerprint → L5 interpretation (agent) | `pipeline.py`, `SKILL.md` |
| **Evidence chain** | Each claim is tagged measured / observed / inferred / verified / unknown. | `evidence.py`, dossier |
| **Hypothesis → test** | A film reference is a hypothesis until a frame match or a citable source confirms it. | `index-ref` + `match-ref` |
| **Specification before implementation (clean room)** | The dossier + prompt pack are a *spec*. The replica is built from the spec, not by re-uploading the original. | `replication_template.md` |
| **Round-trip validation** | Rebuild, re-measure, diff. The fidelity score tells you how close the rebuild is. | `revideo compare` |
| **Document unknowns** | What cannot be determined is written down with what would resolve it. | dossier §16 |

## What is measured (and how)

| Dimension | Metric | Method | Limits |
|---|---|---|---|
| Cuts | shot boundaries, ASL, cuts/min, pacing curve | Built-in: max(HSV-histogram distance, structural thumbnail distance) with an adaptive local threshold, then **flash rejection** (a change that reverts within ±3 frames is not a cut). Optional PySceneDetect, flash-filtered too | Slow dissolves can be missed; tune `--threshold` |
| Transitions | hard cut / fade through black / flash white | Fade = flat black frame + gradual ramp + dip relative to both neighbouring shots; the black stretch is folded into the transition | Dissolves and match cuts are labelled by the agent |
| Aspect | delivery AR, active picture AR (letterbox) | black-bar detection | Very dark scenes can fake bars |
| Color | palette (k-means in Lab), luma percentiles, contrast, black point, WB, shadow/highlight tint | OpenCV Lab | Look labels are heuristics |
| Framing | visual-weight centroid, thirds distance, symmetry, negative space, faces → shot size | Sobel energy, Haar cascade (OpenCV 4.x) | Face-based shot size only when a frontal face is visible |
| Camera | pan/tilt/zoom/roll per second, jitter (handheld), subject residual motion | LK optical flow + RANSAC similarity transform | Zoom vs dolly needs parallax analysis (agent) |
| Sound | loudness, silence, onsets, tempo, beat grid, cut-on-beat ratio | numpy STFT spectral flux + autocorrelation | Half/double-time BPM errors possible |
| Reference frames | exact film frame + timecode | pHash over crop windows (full; 9:16, 4:5, 1:1 at left/center/right) for in/mid/out keyframes, plain and mirrored → top-k candidates → frame-by-frame refinement; match only if pHash distance ≤ 12 **and** thumbnail correlation ≥ 0.8 | Requires the reference film on disk; arbitrary zoom/position crops and speed ramps reduce recall |

## Shot-length statistics background
Average shot length (ASL) as a style metric comes from film-statistics research (Barry Salt's work,
and the Cinemetrics project started by Yuri Tsivian). We use the same basic measures (ASL, median,
distribution) so numbers are comparable with that tradition. Verify specific published values in
those sources before quoting them.

## Validation
See [`VALIDATION.md`](VALIDATION.md) for what has been tested on synthetic and real footage, and what has not.

## Fidelity score
`compare` weights: rhythm 30 %, color 30 %, framing 15 %, camera 15 %, sound 10 %.
It measures **structural DNA**, not content identity: two videos with the same edit rhythm,
palette and movement score high even if the subjects differ. Weights are a starting point, not a
validated standard — adjust them for your use case.
