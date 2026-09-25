import json
import os

from revideo import compare as cmp
from revideo.pipeline import analyze


def test_shots_color_motion(edit_video, tmp_path):
    r = analyze(edit_video, str(tmp_path / "run"), engine="builtin", no_audio=True, quiet=True)
    fp = r["fingerprint"]
    assert fp["shot_count"] == 4
    starts = [s["start_frame"] for s in r["shots"]]
    assert starts == [0, 24, 60, 108]
    # shot 0 warm/orange, shot 1 cool
    assert r["shots"][0]["grade"]["white_balance_ab"][1] > 20
    assert r["shots"][1]["grade"]["white_balance_ab"][1] < -10
    assert "pan_right" in r["shots"][2]["camera"]["type"]
    assert r["shots"][0]["camera"]["type"].startswith("static")
    assert "low-key" in r["shots"][3]["grade"]["look_labels"]
    for f in ("analysis.json", "report.md", "dossier.md", "contact_sheet.jpg"):
        assert os.path.exists(tmp_path / "run" / f)
    with open(tmp_path / "run" / "analysis.json") as f:
        json.load(f)


def test_compare_identity_is_100(edit_video, tmp_path):
    analyze(edit_video, str(tmp_path / "a"), engine="builtin", no_audio=True, quiet=True)
    res = cmp.compare(str(tmp_path / "a"), str(tmp_path / "a"))
    assert res["fidelity_score"] == 100.0


def test_compare_detects_difference(edit_video, film_and_reel, tmp_path):
    analyze(edit_video, str(tmp_path / "a"), engine="builtin", no_audio=True, quiet=True)
    analyze(film_and_reel[0], str(tmp_path / "b"), engine="builtin", no_audio=True, quiet=True)
    assert cmp.compare(str(tmp_path / "a"), str(tmp_path / "b"))["fidelity_score"] < 80
