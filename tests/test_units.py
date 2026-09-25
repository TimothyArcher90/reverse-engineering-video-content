import os
import wave

import cv2
import numpy as np

from revideo import audio, color, composition, ingest
from revideo.cli import main
from revideo.video import timecode


def test_timecode():
    assert timecode(0, 24) == "00:00:00:00"
    assert timecode(61.5, 24) == "00:01:01:12"
    assert timecode(3600 + 1 / 25, 25) == "01:00:00:01"


def test_letterbox_detection():
    f = np.zeros((360, 640, 3), np.uint8)
    f[45:315] = 120
    a = composition.active_area(f)
    assert a["letterboxed"] and abs(a["aspect_ratio"] - 640 / 270) < 0.02
    assert composition.nearest_ar_name(a["aspect_ratio"]).startswith("2.39")


def test_palette_and_grade():
    f = np.zeros((100, 100, 3), np.uint8)
    f[:, :70] = (40, 120, 230)  # orange (BGR)
    f[:, 70:] = (200, 150, 40)  # blue-ish
    pal = color.palette([f], k=2)
    assert len(pal) == 2 and abs(pal[0]["share"] - 0.7) < 0.02
    g = color.grade_stats([f])
    assert g["saturation_mean"] > 0.5 and "saturated" in g["look_labels"]
    assert color.palette_distance(pal, pal) == 0


def test_subtitles_dedupe(tmp_path):
    vtt = tmp_path / "a.vtt"
    vtt.write_text(
        "WEBVTT\n\n00:00:00.000 --> 00:00:01.000\nhola\n\n00:00:01.000 --> 00:00:02.000\nhola mundo\n\n"
        "00:00:02.500 --> 00:00:03.000\n<c>otra</c> línea\n",
        encoding="utf-8",
    )
    subs = ingest.parse_subtitles(str(vtt))
    assert [s["text"] for s in subs] == ["hola mundo", "otra línea"]
    assert subs[0]["end"] == 2.0


def test_tempo_and_cut_sync(tmp_path):
    sr, bpm, dur = audio.SR, 120, 12
    x = np.zeros(sr * dur, np.float32)
    beat = 60 / bpm
    click = (np.sin(2 * np.pi * 1500 * np.arange(800) / sr) * np.hanning(800)).astype(np.float32)
    beats = np.arange(0.25, dur - 0.1, beat)
    for t in beats:
        i = int(t * sr)
        x[i : i + 800] += click
    p = tmp_path / "c.wav"
    with wave.open(str(p), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes((x * 30000).astype(np.int16).tobytes())
    rep = audio.analyze(str(p), cut_times=list(beats[2:10]))
    assert abs(rep["tempo_bpm_estimate"] - bpm) < 3 or abs(rep["tempo_bpm_estimate"] - bpm / 2) < 2
    assert rep["cuts_on_onset_ratio"] >= 0.9


def test_cli_end_to_end(edit_video, tmp_path, capsys):
    out = str(tmp_path / "cli")
    assert main(["analyze", edit_video, "-o", out, "--engine", "builtin", "--no-audio", "-q"]) == 0
    for f in ("analysis.json", "report.md", "report.html", "dossier.md", "contact_sheet.jpg"):
        assert os.path.exists(os.path.join(out, f)), f
    with open(os.path.join(out, "report.html"), encoding="utf-8") as f:
        html = f.read()
    assert "keyframes/shot_000_mid.jpg" in html and "<svg" in html
    assert main(["compare", out, out]) == 0
    assert "100.0" in capsys.readouterr().out
    assert main(["report", out]) == 0


def _write(path, frames, fps=24):
    h, w = frames[0].shape[:2]
    vw = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"mp4v"), fps, (w, h))
    for f in frames:
        vw.write(f)
    vw.release()
    return str(path)


def test_flash_is_not_a_cut_and_dark_scene_is_not_a_fade(tmp_path):
    """Fireworks-like bursts over a dark sky: one shot, no fades (regression from real footage)."""
    from revideo import shots
    from revideo.video import probe

    rng = np.random.default_rng(3)
    frames = []
    for i in range(96):
        f = np.full((180, 320, 3), 6, np.uint8)
        if i % 24 in (10, 11, 12):  # a burst: bright blob for 3 frames, then dark again
            c = (int(rng.integers(80, 240)), int(rng.integers(40, 140)))
            cv2.circle(f, c, 40 - 8 * (i % 24 - 10), (200, 220, 255), -1)
        frames.append(f)
    p = _write(tmp_path / "fw.mp4", frames)
    got, meta = shots.detect_shots(p, probe(p))
    assert len(got) == 1, meta
    assert all(s.transition_in == "hard_cut" for s in got)


def test_real_fade_through_black_is_labelled(tmp_path):
    from revideo import shots
    from revideo.video import probe

    a, b = np.full((180, 320, 3), 170, np.uint8), np.full((180, 320, 3), 90, np.uint8)
    cv2.rectangle(b, (50, 50), (150, 150), (20, 200, 20), -1)
    ramp = [np.clip(a * (1 - k / 8), 0, 255).astype(np.uint8) for k in range(1, 9)]
    frames = [a] * 40 + ramp + [b * 0] * 2 + [b] * 40
    p = _write(tmp_path / "fade.mp4", frames)
    got, _ = shots.detect_shots(p, probe(p))
    assert len(got) == 2 and got[1].transition_in == "fade_through_black"


def test_hard_cut_into_dark_shot_is_kept(tmp_path):
    """Regression from real footage: bright shot → dark shot with fully black moments → bright shot.
    Both cuts must survive (the dark shot is not a fade)."""
    from revideo import shots
    from revideo.video import probe

    rng = np.random.default_rng(5)
    bright = cv2.GaussianBlur(rng.integers(60, 200, (180, 320, 3), dtype=np.uint8), (0, 0), 3)
    dark = []
    for i in range(40):
        f = np.full((180, 320, 3), 8, np.uint8)
        if i % 10 < 4:  # sparks, then fully black sky
            cv2.circle(f, (100 + 3 * i, 80), 12, (60, 120, 200), -1)
        dark.append(f)
    other = cv2.GaussianBlur(rng.integers(40, 160, (180, 320, 3), dtype=np.uint8), (0, 0), 3)
    p = _write(tmp_path / "dark.mp4", [bright] * 30 + dark + [other] * 30)
    got, _ = shots.detect_shots(p, probe(p))
    assert [s.start_frame for s in got] == [0, 30, 70], got
