import os

from revideo.pipeline import analyze
from revideo.references import best_per_shot, crop_window, index_reference, match


def _kf(r, root):
    return {s["index"]: {k: os.path.join(root, v) for k, v in s["keyframes"].items()} for s in r["shots"]}


def test_exact_frame_match_through_center_crop(film_and_reel, tmp_path):
    film, reel, target = film_and_reel
    idx = index_reference(film, str(tmp_path / "film"), sample_fps=2, title="Test Film", director="Nobody", year=2000)
    assert idx.endswith(".npz") and os.path.exists(str(tmp_path / "film.json"))
    r = analyze(reel, str(tmp_path / "reel"), engine="builtin", no_audio=True, no_motion=True, quiet=True)
    res = match(_kf(r, tmp_path / "reel"), idx)
    assert res[0]["match"], res
    assert res[0]["crop"] == "9:16@center"
    assert abs(res[0]["film_frame"] - target) <= 1, res
    assert res[0]["film"]["director"] == "Nobody"
    assert res[0]["evidence"] == "verified"


def test_offcenter_mirrored_regraded_crop(film_and_reel, hard_reel, tmp_path):
    film = film_and_reel[0]
    reel, target = hard_reel
    idx = index_reference(film, str(tmp_path / "film.npz"), sample_fps=2)
    r = analyze(reel, str(tmp_path / "hard"), engine="builtin", no_audio=True, no_motion=True, quiet=True)
    assert len(r["shots"]) == 2
    res = match(_kf(r, tmp_path / "hard"), idx)
    hit, miss = res[0], res[1]
    assert hit["match"] and hit["mirrored"] and hit["crop"].startswith("4:5"), hit
    assert abs(hit["film_frame"] - target) <= 1, hit
    assert not miss["match"] and "film_frame" not in miss  # no fake timecode for unmatched shots


def test_unrelated_does_not_match(film_and_reel, edit_video, tmp_path):
    idx = index_reference(film_and_reel[0], str(tmp_path / "film.npz"), sample_fps=2)
    r = analyze(edit_video, str(tmp_path / "e"), engine="builtin", no_audio=True, no_motion=True, quiet=True)
    assert not any(m["match"] for m in match(_kf(r, tmp_path / "e"), idx))


def test_best_per_shot_prefers_match():
    recs = [{"shot": 0, "match": False, "closest": {"correlation": 0.5}}, {"shot": 0, "match": True, "correlation": 0.9}]
    assert best_per_shot(recs)[0]["match"]


def test_crop_window_positions():
    import numpy as np

    img = np.zeros((100, 400, 3), np.uint8)
    assert crop_window(img, 1.0, 0.0).shape[:2] == (100, 100)
    img[:, 300:] = 255
    assert crop_window(img, 1.0, 1.0).mean() == 255
