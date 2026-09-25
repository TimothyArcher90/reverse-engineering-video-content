# Changelog

Format based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/); versions follow
[Semantic Versioning](https://semver.org/).

## Unreleased
### Added
- **Short-form layer** (`social.py`, `analysis.json → social`) for Reels/TikTok/Shorts:
  - on-screen text timing and placement (a classical stroke detector, no OCR dependency);
  - hook metrics for 0–3 s (cuts, motion energy against the rest, first text);
  - safe-zone checks against Meta and TikTok presets (`data/platforms.json`, third-party sources,
    marked unverified);
  - loop detection (first vs last frame);
  - 9:16 and 1080×1920 checks.
  These feed a "Reels / TikTok delivery" section in the plan and reports.

## [0.3.0] — 2026-09-25

The master-copycat release: photos and sound as well as video, everything the file says about how it
was made, and a replication plan per budget and condition.

### Added
- **Photos and audio**: `analyze` routes by extension (`--kind` to force). Photos get palette, grade,
  framing, optics and EXIF; audio gets tempo, key, spectral balance and dynamics.
- **Forensics** (`forensics.py`, every input): container/stream tags, EXIF, XMP with Lightroom/Camera Raw
  sliders, PNG generation parameters (Automatic1111, ComfyUI), IPTC AI declarations, C2PA signature, HDR
  flags, and tool fingerprints with the matched string as evidence. Tools named in the post text are
  kept separately as creator claims.
- **Optics**: depth of field, focus centre, vignette, grain and clipping, for photos and each video shot.
  `focus_falloff_guess` tells optical defocus (gradual) from a cut-out/composite (abrupt edge). Photos
  also get a `subject` block: the in-focus region's box and palette.
- Plans flag embedded recipes that disagree with the pixels (for example grain set but none measured).
- **Audio**: key estimate (Krumhansl–Kessler), energy per band, spectral centroid, crest factor; BPM
  now uses sub-frame peak interpolation (the 120 BPM test signal reads 120.0, it read 117.5).
- **`replication_plan.md`** for every run (`plan` command): target spec, EDL with rig per tier,
  grade recipe (exact Lightroom values when embedded), optics, paths by budget and condition, AI
  prompt per shot. Tool catalog `src/revideo/data/tools.json` (`tools` command) with pricing *models*
  and official links, marked unverified.
- **`compare`** scores photo and audio replicas too.
- **Daily workflow**: newest dependencies + tests, catalog link check, fresh `.skill` build.
- Direct links to photos/audio are downloaded without yt-dlp; yt-dlp failures suggest `setup --update`.
- Self-contained skill package: `tools/build_skill.py` → `dist/reverse-engineering-video.skill`, bundling the
  `revideo` source. The launcher `skill/scripts/revideo.py` installs numpy/opencv/pillow on first use (yt-dlp and
  imageio-ffmpeg only when needed); `REVIDEO_NO_INSTALL=1` turns that off.
- CI job that builds the `.skill` and uploads it as an artifact; test that the unpacked package runs on its own.

### Changed
- `analysis.json` schema 2: `kind`, `forensics`, `shots[].optics`, audio `key_estimate`/`spectral`.
  Re-run `analyze` for runs made with 0.2.
- SKILL.md: acts without asking, gathers file evidence first, adapts the plan to the user's conditions,
  never quotes prices from memory.
- New dependency: Pillow.
## [0.2.0] — 2026-09-24

Hardened against real footage. See [`docs/VALIDATION.md`](docs/VALIDATION.md).

### Added
- `report.html`: self-contained visual report (stat tiles, edit timeline, pacing chart, palette,
  grade, shot table with thumbnails, verified references), light/dark, mobile-friendly.
- `revideo report <dir>` to rebuild reports; `revideo --version`; `python -m revideo`.
- Film matching: crop windows at left/center/right for 9:16, 4:5 and 1:1; all keyframes (in/mid/out)
  plain and mirrored are tried; top-k candidates refined frame by frame.
- Match records now say **which frame of the analyzed video** matched (`query_keyframe`,
  `query_timecode`) and estimate where the shot starts in the film (`film_shot_start_estimate`).
- `match-ref` merges verified matches into `analysis.json` and the reports; best result per shot
  across several indexes; `--min-correlation`; `index-ref --dp`.
- `schema_version` in `analysis.json`; `docs/SCHEMA.md`, `docs/VALIDATION.md`.
- Lint (ruff) in CI; issue/PR templates; `CONTRIBUTING.md`.

### Changed
- Cut detector: structural term (catches cuts between similarly colored shots) + **flash rejection**
  (a change that reverts within a few frames is not a cut). Built-in detector is now the default;
  `--engine scenedetect` remains optional and is also flash-filtered.
- Fades: labelled only when there is a *flat* black frame, a gradual ramp and a dip relative to both
  neighbouring shots; the black stretch is folded into the transition instead of becoming a shot.
- Decoded frame count is authoritative (containers can over-report); reported when they differ.
- Pacing window adapts to length (1 s / 5 s / 10 s).
- Unmatched shots no longer carry a film frame/timecode.
- Keyframe extraction decodes only the frames it needs; audio analysis uses O(n) RMS, chunked STFT
  and FFT autocorrelation (bounded memory on long videos).
- `opencv-python<5` (OpenCV 5 dropped the Haar face detector); yt-dlp gets the ffmpeg location.
- `analysis.json` stores the video path relative to the run folder.

### Fixed
- A dark real-world clip (fireworks) produced 10 shots and 8 fake fades; now 1 shot.
- A hard cut into a dark shot was merged away as a "fade".
- `compare` no longer warns/crashes when a component has no data.

### Index format
- Reference indexes are version 2; indexes from 0.1.0 must be rebuilt with `revideo index-ref`.

## [0.1.0] — 2026-09-24
- First release: `analyze`, `index-ref`, `match-ref`, `compare`, `doctor`; Claude Code skill; docs.
