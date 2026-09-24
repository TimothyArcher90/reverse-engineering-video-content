# Contributing

## Setup
```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[full,dev]" ruff
revideo doctor
```

## Before opening a pull request
```bash
ruff check . && ruff format --check .
pytest -q
```
CI runs the same checks on Python 3.10 and 3.12.

## Rules of the project
1. **Measured vs inferred.** A new metric goes into `analysis.json` only if it is computed from the
   pixels/samples. Labels derived from it are heuristics and must be named as such.
2. **Every detector change needs a ground-truth test.** Build the case synthetically in
   `tests/` (see `conftest.py`) so the expected answer is known exactly. If the bug came from real
   footage, reproduce its *mechanism* synthetically (e.g. `test_flash_is_not_a_cut…`).
3. **Precision over recall for references.** A wrong film/timecode is worse than "no match".
4. **Schema changes** bump `SCHEMA_VERSION` (pipeline.py) and update `docs/SCHEMA.md` and `CHANGELOG.md`.
5. **No copyrighted media in the repository** — no films, frames, indexes or audio (see `docs/LEGAL.md`).

## Real-footage check
Openly licensed clips are available in OpenCV's test data:
```bash
git clone --depth 1 --filter=blob:none --sparse https://github.com/opencv/opencv_extra
cd opencv_extra && git sparse-checkout set testdata/highgui/video && cd ..
V=opencv_extra/testdata/highgui/video
revideo analyze $V/VID00003-20100701-2204.avi -o runs/fireworks   # expect 1 shot
revideo index-ref $V/big_buck_bunny.mp4 -o refs/bbb --title "Big Buck Bunny" --year 2008
# build a derived reel (crop + mirror + grade) with ffmpeg, analyze it, then:
revideo match-ref runs/<reel> refs/bbb.npz
```
Record results in `docs/VALIDATION.md`.
