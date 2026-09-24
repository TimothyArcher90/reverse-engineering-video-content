from revideo.pipeline import analyze
from revideo.references import index_reference, match
import os


def test_exact_frame_match_through_crop(film_and_reel, tmp_path):
    film, reel, target = film_and_reel
    idx = index_reference(film, str(tmp_path / "film.npz"), sample_fps=2, title="Test Film", director="Nobody", year=2000)
    r = analyze(reel, str(tmp_path / "reel"), engine="builtin", no_audio=True, no_motion=True, quiet=True)
    kf = {s["index"]: {k: os.path.join(tmp_path / "reel", v) for k, v in s["keyframes"].items()} for s in r["shots"]}
    res = match(kf, idx)
    assert res[0]["match"], res
    assert res[0]["crop"] == "9:16"
    assert abs(res[0]["film_frame"] - target) <= 1, res
    assert res[0]["film"]["director"] == "Nobody"
    assert res[0]["evidence"] == "verified"


def test_unrelated_does_not_match(film_and_reel, edit_video, tmp_path):
    film, _, _ = film_and_reel
    idx = index_reference(film, str(tmp_path / "film.npz"), sample_fps=2)
    r = analyze(edit_video, str(tmp_path / "e"), engine="builtin", no_audio=True, no_motion=True, quiet=True)
    kf = {s["index"]: {k: os.path.join(tmp_path / "e", v) for k, v in s["keyframes"].items()} for s in r["shots"]}
    assert not any(m["match"] for m in match(kf, idx, max_distance=8))
