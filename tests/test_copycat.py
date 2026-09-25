"""Photo, audio, forensics and replication-plan paths, each checked against known ground truth."""

import json
import os
import wave

import cv2
import numpy as np
import pytest
from PIL import Image, PngImagePlugin

from revideo import advise, audio, cli, forensics, optics

XMP = (
    b'<x:xmpmeta xmlns:x="adobe:ns:meta/"><rdf:RDF><rdf:Description xmp:CreatorTool="Adobe Lightroom 7.0" '
    b'crs:Exposure2012="+0.35" crs:Contrast2012="+20" crs:Temperature="6100"/></rdf:RDF></x:xmpmeta>'
)


@pytest.fixture(scope="module")
def photo(tmp_path_factory):
    """Sharp center on a blurred field, darkened corners, with EXIF + Lightroom XMP."""
    d = tmp_path_factory.mktemp("photo")
    rng = np.random.default_rng(3)
    tex = (rng.random((400, 600, 3)) * 255).astype(np.uint8)
    img = cv2.GaussianBlur(tex, (0, 0), 8)
    img[130:270, 230:370] = tex[130:270, 230:370]
    yy, xx = np.mgrid[0:400, 0:600]
    img = (img * (1 - 0.5 * (((xx - 300) / 300) ** 2 + ((yy - 200) / 200) ** 2) / 2)[..., None]).astype(np.uint8)
    ex = Image.Exif()
    ex[271], ex[272] = "SONY", "ILCE-7M4"
    path = str(d / "photo.jpg")
    Image.fromarray(img[:, :, ::-1]).save(path, exif=ex, xmp=XMP, quality=92)
    return path


@pytest.fixture(scope="module")
def ai_png(tmp_path_factory):
    d = tmp_path_factory.mktemp("png")
    info = PngImagePlugin.PngInfo()
    info.add_text("parameters", "neon alley\nNegative prompt: blurry\nSteps: 30, Sampler: DPM++ 2M, CFG scale: 7, Seed: 42")
    path = str(d / "gen.png")
    Image.fromarray(np.full((64, 64, 3), 128, np.uint8)).save(path, pnginfo=info)
    return path


@pytest.fixture(scope="module")
def track(tmp_path_factory):
    """8 s of an A-minor triad pulsing at exactly 120 BPM."""
    d = tmp_path_factory.mktemp("audio")
    sr = audio.SR
    t = np.arange(sr * 8) / sr
    x = sum(np.sin(2 * np.pi * f * t) for f in (220.0, 261.63, 329.63)) * 0.25 * np.sin(np.pi * ((t * 2) % 1)) ** 8
    path = str(d / "track.wav")
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes((x * 32767).astype(np.int16).tobytes())
    return path


def test_media_kind_routing():
    assert forensics.media_kind("a/b/photo.JPG") == "image"
    assert forensics.media_kind("https://x.com/song.mp3?sig=1") == "audio"
    assert forensics.media_kind("https://www.instagram.com/reel/abc/") == "video"


def test_forensics_recovers_lightroom_recipe_and_camera(photo):
    meta = forensics.gather(photo)
    assert meta["exif"]["Model"] == "ILCE-7M4"
    crs = meta["xmp"]["camera_raw_settings"]
    assert crs["Exposure2012"] == "+0.35" and crs["Temperature"] == "6100"
    assert any(h["tool"] == "Adobe Lightroom" for h in meta["tool_fingerprints"])
    assert not meta["metadata_stripped_likely"]


def test_forensics_recovers_ai_generation_parameters(ai_png):
    meta = forensics.gather(ai_png)
    assert "Seed: 42" in meta["png_text"]["parameters"]
    assert any("Stable Diffusion" in h["tool"] for h in meta["tool_fingerprints"])


def test_post_mentions_are_not_file_evidence():
    hits = forensics.fingerprints({"title": "made this with Kling and CapCut"}, "creator_mention")
    assert {h["tool"] for h in hits} >= {"Kling", "CapCut"}
    assert all(h["level"] == "creator_mention" for h in hits)


def test_optics_shallow_focus_and_vignette(photo):
    o = optics.analyze(cv2.imread(photo))
    assert o["depth_of_field_guess"].startswith("shallow")
    assert o["vignette_guess"] in ("strong", "visible")
    assert 0.4 < o["focus_center_norm"][0] < 0.6


def test_optics_flat_image_is_undetermined():
    o = optics.analyze(np.full((200, 300, 3), 90, np.uint8))
    assert o["depth_of_field_guess"].startswith("undetermined")


def test_audio_tempo_and_key(track):
    rep = audio.analyze(track, [])
    assert abs(rep["tempo_bpm_estimate"] - 120) <= 1.5
    assert rep["key_estimate"]["key"] in ("A minor", "C major")  # relative keys share the triad's notes
    assert rep["spectral"]["energy_share_pct"]["highs_>4kHz"] < 5


def test_photo_end_to_end_with_plan(photo, tmp_path):
    out = tmp_path / "p"
    assert cli.main(["analyze", photo, "-o", str(out), "--quiet"]) == 0
    r = json.loads((out / "analysis.json").read_text())
    assert r["kind"] == "image" and r["camera_and_lens"]["Model"] == "ILCE-7M4"
    plan = (out / "replication_plan.md").read_text()
    assert "Lightroom `Exposure2012` = +0.35" in plan  # exact recipe beats estimated grade
    assert (out / "report.html").read_text().count("Production fingerprints") == 1


def test_audio_end_to_end(track, tmp_path):
    out = tmp_path / "a"
    assert cli.main(["analyze", track, "-o", str(out), "--quiet"]) == 0
    r = json.loads((out / "analysis.json").read_text())
    assert r["kind"] == "audio" and r["audio"]["key_estimate"]
    assert "BPM" in (out / "replication_plan.md").read_text()


def test_video_plan_uses_measured_shots(edit_video, tmp_path):
    out = tmp_path / "v"
    assert cli.main(["analyze", edit_video, "-o", str(out), "--quiet", "--no-audio"]) == 0
    r = json.loads((out / "analysis.json").read_text())
    assert r["kind"] == "video" and "forensics" in r
    plan = advise.plan(r)
    for s in r["shots"]:
        assert f"**Shot {s['index']}** ({s['duration_sec']} s" in plan
    assert "Phone only" in plan and "Pro crew" in plan
    assert "pan_right" in plan  # the measured pan in shot 2 reaches the shot list


def test_catalog_is_well_formed():
    cat = advise.load_catalog()
    assert cat["prices_verified"] is False  # plans must never present catalog pricing as verified
    names = [t["name"] for t in cat["tools"]]
    assert len(names) == len(set(names))
    for t in cat["tools"]:
        assert t["url"].startswith("https://") and set(t["tiers"]) <= set(advise.TIERS)
        assert not any(ch.isdigit() for ch in t["pricing_model"]), t  # never a price figure


def test_skill_bundle_ships_catalog():
    root = os.path.join(os.path.dirname(__file__), "..", "src", "revideo", "data", "tools.json")
    assert os.path.isfile(root)


def test_compare_photo_and_audio_replicas(photo, track, tmp_path):
    from revideo.compare import compare

    for src, name in ((photo, "p"), (track, "a")):
        a, b = tmp_path / f"{name}1", tmp_path / f"{name}2"
        cli.main(["analyze", src, "-o", str(a), "--quiet"])
        cli.main(["analyze", src, "-o", str(b), "--quiet"])
        assert compare(str(a), str(b))["fidelity_score"] >= 99  # identical input → near-perfect score
    with pytest.raises(SystemExit):
        compare(str(tmp_path / "p1"), str(tmp_path / "a1"))
