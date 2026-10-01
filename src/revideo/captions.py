"""Word-by-word (kinetic) caption timing from the transcript, snapped to measured audio onsets.

Segment start/end times come from subtitles or Whisper [M]. Inside a segment each word gets a share
of the time proportional to its length, then its start snaps to the nearest audio onset within
SNAP_SEC when one exists. Both steps are approximations [I]: check the result against the audio.
"""

from __future__ import annotations

import json
import os

SNAP_SEC = 0.08
MIN_WORD_SEC = 0.12


def _srt_time(t: float) -> str:
    ms = int(round(max(0.0, t) * 1000))
    h, ms = divmod(ms, 3_600_000)
    m, ms = divmod(ms, 60_000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def words(transcript: list[dict], onsets: list[float] | None = None) -> list[dict]:
    onsets = sorted(onsets or [])
    out = []
    for seg in transcript:
        toks = str(seg.get("text", "")).split()
        a, b = float(seg["start"]), float(seg["end"])
        if not toks or b <= a:
            continue
        weights = [max(1, len(t.strip(".,!?;:\"'"))) for t in toks]
        total, t = sum(weights), a
        starts = []
        for w in weights:
            starts.append(t)
            t += (b - a) * w / total
        for i, s in enumerate(starts):
            near = [o for o in onsets if abs(o - s) <= SNAP_SEC and a - 1e-6 <= o < b]
            if near:
                starts[i] = min(near, key=lambda o: abs(o - s))
        for i in range(1, len(starts)):  # keep order and a minimum length per word
            starts[i] = max(starts[i], starts[i - 1] + MIN_WORD_SEC)
        for i, tok in enumerate(toks):
            end = starts[i + 1] if i + 1 < len(toks) else b
            if end > starts[i]:
                out.append({"word": tok, "start": round(starts[i], 3), "end": round(min(end, b), 3)})
    return out


def srt(ws: list[dict], per_cue: int = 1) -> str:
    cues = [ws[i : i + per_cue] for i in range(0, len(ws), per_cue)]
    return "\n".join(
        f"{n}\n{_srt_time(c[0]['start'])} --> {_srt_time(c[-1]['end'])}\n{' '.join(w['word'] for w in c)}\n"
        for n, c in enumerate(cues, start=1)
    )


def write_captions(analysis_dir: str) -> list[str]:
    with open(os.path.join(analysis_dir, "analysis.json"), encoding="utf-8") as f:
        r = json.load(f)
    ws = words(r.get("transcript") or [], (r.get("audio") or {}).get("onset_times"))
    if not ws:
        return []
    paths = []
    for name, n in (("captions_words.srt", 1), ("captions_3words.srt", 3)):
        p = os.path.join(analysis_dir, name)
        with open(p, "w", encoding="utf-8") as f:
            f.write(srt(ws, n))
        paths.append(p)
    return paths
