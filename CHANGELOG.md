# Changelog

Format based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/); versions follow
[Semantic Versioning](https://semver.org/).

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
