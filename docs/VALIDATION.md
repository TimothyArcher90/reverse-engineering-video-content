# Validation

What has been tested, how, and what the numbers were. Anything not listed here is **not validated**.

## 1. Automated tests (CI, every push)

31 tests on synthetic videos, photos and audio with known ground truth (`tests/`):

| Area | What is asserted |
|---|---|
| Cut detection | Exact cut frames on a 4-shot edit; cut between two shots with *similar colors* but different content |
| Flash rejection | Light bursts over a dark sky → 1 shot, 0 cuts |
| Dark shots | Hard cut into a dark shot that has fully black moments → both cuts kept, no fake fade |
| Fades | Fade-out → black → cut → labelled `fade_through_black`, black stretch not counted as a shot |
| Color | Warm vs cool white balance, low-key label, palette shares, ΔE = 0 on identity |
| Camera | Pan direction (content moving left → `pan_right`), static shot |
| Framing | Letterbox detection → 2.37:1 active area named "2.39 anamorphic/scope" |
| Sound | 120 BPM click track → tempo within ±3 BPM (or half-time), cuts on onsets ≥ 90 % |
| Subtitles | VTT parsing, tag stripping, rolling auto-caption de-duplication |
| Film-frame match | Center 9:16 crop → exact frame ±1; **left-aligned 4:5 crop + mirrored + re-graded** → exact frame ±1; unrelated shot → no match and **no timecode emitted** |
| Fidelity | Identity = 100; different videos < 80 |
| CLI | `analyze`, `compare`, `report` end to end; HTML report references keyframes and contains the chart |
| Photo forensics | JPEG with EXIF + Lightroom XMP → camera model and every Camera Raw slider recovered 1:1; plan copies them verbatim |
| AI forensics | PNG with Automatic1111 parameters → prompt, seed and sampler recovered; tool = Stable Diffusion |
| Creator claims | Tools named in the post text are reported as `creator_mention`, never as file evidence |
| Optics | Sharp centre on a blurred field → shallow DOF, focus at centre, vignette detected; flat image → `undetermined` |
| Key / tempo | A-minor triad at 120 BPM → A minor (or relative C major), 120 ± 1.5 BPM (reads 120.0) |
| Plans | Every measured shot appears with its duration; measured pan reaches the shot list; all tiers present |
| Catalog | No price figures, HTTPS links, unique names, `prices_verified: false` |
| Photo/audio compare | Identical input ≥ 99; photo vs audio refused |
| Skill package | Built `.skill` unzipped and run with installs disabled → analysis from the bundled source |

CI runs lint (ruff) and the test suite on Linux (3.10, 3.12), macOS and Windows. A daily run repeats the suite on the newest dependencies and checks every catalog link.

## 2. Real footage (manual, v0.2.0)

Clips from the OpenCV test-data repository (`opencv/opencv_extra`, `testdata/highgui/video`):
a 5.2 s excerpt of *Big Buck Bunny* (© Blender Foundation, CC BY 3.0) and a 39 s handheld phone
recording of fireworks.

| Test | Ground truth | Result |
|---|---|---|
| *Big Buck Bunny* excerpt | 1 shot | 1 shot ✅ |
| Fireworks phone clip (dark, many light bursts) | 1 continuous handheld shot | 1 shot, `handheld_static` ✅ — v0.1 reported 10 shots and 8 fake fades ❌ (fixed) |
| Montage of 5 real segments (BBB / fireworks / BBB / fireworks / BBB), H.264 | cuts at 1.2, 2.7, 3.7, 5.7 s | 1.2, 2.7, 3.7, 5.733 s — **4/4 cuts, max error 1 frame, 0 false positives** ✅ |
| Derived "reel": BBB 2.5–4.0 s → 9:16 crop, **mirrored**, contrast/saturation/gamma/color-balance change, 720×1280, 30 fps, H.264 CRF 26, + one unrelated shot | reel frame 40 = BBB 3.833 s = frame 92 @ 24 fps; shot starts at 2.5 s | **frame 92, 00:00:03:20**, r = 0.981, pHash distance 2, crop `9:16@center`, mirrored = true; shot-start estimate **2.500 s** ✅ · unrelated shot: no match ✅ |
| Timings (4-core container) | — | index 5 s film 0.3 s · analyze 3 s reel 1.4 s · match 0.5 s · analyze 39 s clip 2.4 s |

## 3. Not yet validated

- Feature-length reference films (indexing time and precision with thousands of similar frames).
- Crops at arbitrary positions/zoom outside the left/center/right windows, speed ramps, heavy text overlays.
- Face-based shot size on real faces (Haar cascade; OpenCV 4.x only).
- Tempo and key on real music (only synthetic signals are tested); half/double-time and relative-key errors are possible.
- Photos straight from real phones/cameras (EXIF layouts vary by maker; HEIC is not decoded — convert to JPG).
- Tool fingerprints on real exports from each editor: the rules match documented strings, but each app's
  export metadata has not been sampled here.
- Catalog links: this environment's network policy blocked them; the daily workflow checks them on GitHub.
- URL download through `yt-dlp` (network was not available in the validation environment).
- The fidelity-score weights: they are a reasoned starting point, not calibrated against human judgement.
- `--engine scenedetect`: on the fireworks clip it still reports 7 shots after flash filtering (built-in: 1).

To reproduce section 2, see the commands in [`CONTRIBUTING.md`](../CONTRIBUTING.md#real-footage-check).
