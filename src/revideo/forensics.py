"""Gather every recoverable fact about how a file was made: container tags, EXIF, XMP, AI-generation records.

All of it is read from the file itself, so it is MEASURED metadata. It is not proof of the tool used,
because metadata can be stripped (most social platforms re-encode and drop it) or rewritten. Each
tool fingerprint therefore carries the matched string as evidence.
"""

from __future__ import annotations

import contextlib
import json
import os
import re
import subprocess

from .video import find_ffmpeg

IMAGE_EXT = {".jpg", ".jpeg", ".png", ".webp", ".tif", ".tiff", ".bmp"}
AUDIO_EXT = {".mp3", ".wav", ".m4a", ".aac", ".flac", ".ogg", ".opus", ".aif", ".aiff"}


def media_kind(path: str) -> str:
    ext = os.path.splitext(path.split("?")[0])[1].lower()
    return "image" if ext in IMAGE_EXT else "audio" if ext in AUDIO_EXT else "video"


# ---------------------------------------------------------------- container (ffmpeg)

_META_LINE = re.compile(r"^\s{2,}([A-Za-z0-9_.:\-]+)\s*:\s?(.*)$")
_STREAM = re.compile(r"Stream #\d+:\d+(?:\[[^\]]*\])?(?:\([^)]*\))?: (Video|Audio|Data|Subtitle): (.*)")


def container(path: str) -> dict:
    """Parse `ffmpeg -i` output (no ffprobe needed): format tags, streams and their tags."""
    exe = find_ffmpeg()
    if not exe:
        return {"error": "ffmpeg unavailable"}
    txt = subprocess.run([exe, "-hide_banner", "-i", path], capture_output=True, text=True, errors="replace").stderr
    out: dict = {"format": {}, "streams": []}
    target = out["format"]
    in_meta = False
    for line in txt.splitlines():
        m = _STREAM.search(line)
        if m:
            target = {"type": m.group(1).lower(), "desc": m.group(2).strip(), "tags": {}}
            out["streams"].append(target)
            target = target["tags"]
            in_meta = False
            continue
        if line.strip() in ("Metadata:", "Side data:"):
            in_meta = line.strip() == "Metadata:"
            continue
        if line.lstrip().startswith("Duration:"):
            out["duration_line"] = line.strip()
            in_meta = False
            continue
        mm = _META_LINE.match(line)
        if in_meta and mm and mm.group(1) not in ("Metadata",):
            k, v = mm.group(1).strip(), mm.group(2).strip()
            target[k] = f"{target[k]} {v}".strip() if k in target else v  # multi-line values
    for s in out["streams"]:
        d = s["desc"]
        if s["type"] == "video":
            if (m := re.search(r"(\d{2,5})x(\d{2,5})", d)) is not None:
                s["width"], s["height"] = int(m.group(1)), int(m.group(2))
            if (m := re.search(r"([\d.]+) fps", d)) is not None:
                s["fps"] = float(m.group(1))
            s["codec"] = d.split(" ", 1)[0].rstrip(",")
            s["hdr"] = next((t for t in ("smpte2084", "arib-std-b67") if t in d), None)
            s["dolby_vision"] = "dovi" in txt.lower() or "dolby vision" in txt.lower()
        elif s["type"] == "audio":
            s["codec"] = d.split(" ", 1)[0].rstrip(",")
        if (m := re.search(r"(\d+) kb/s", d)) is not None:
            s["bitrate_kbps"] = int(m.group(1))
    return out


# ---------------------------------------------------------------- raw bytes: XMP, C2PA, PNG text

_CRS_KEYS = (
    "Exposure2012",
    "Contrast2012",
    "Highlights2012",
    "Shadows2012",
    "Whites2012",
    "Blacks2012",
    "Texture",
    "Clarity2012",
    "Dehaze",
    "Vibrance",
    "Saturation",
    "Temperature",
    "Tint",
    "SplitToningShadowHue",
    "SplitToningShadowSaturation",
    "SplitToningHighlightHue",
    "SplitToningHighlightSaturation",
    "ColorGradeShadowHue",
    "ColorGradeShadowSat",
    "ColorGradeMidtoneHue",
    "ColorGradeMidtoneSat",
    "ColorGradeHighlightHue",
    "ColorGradeHighlightSat",
    "GrainAmount",
    "GrainSize",
    "PostCropVignetteAmount",
    "Sharpness",
    "LookName",
    "ProcessVersion",
    "CameraProfile",
)


def _read_edges(path: str, head: int = 8 << 20, tail: int = 2 << 20) -> bytes:
    size = os.path.getsize(path)
    with open(path, "rb") as f:
        if size <= head + tail:
            return f.read()
        a = f.read(head)
        f.seek(size - tail)
        return a + f.read()


def _xmp_value(xmp: str, key: str) -> str | None:
    m = re.search(rf'{key}="([^"]*)"', xmp) or re.search(rf"<[\w]*:?{key}>(.*?)</[\w]*:?{key}>", xmp, re.S)
    if not m:
        return None
    v = re.sub(r"<[^>]+>", " ", m.group(1))
    return re.sub(r"\s+", " ", v).strip() or None


def xmp(raw: bytes) -> dict:
    """XMP packet: creator tool, edit history agents, IPTC digital source type, Camera Raw (Lightroom) settings."""
    s, e = raw.find(b"<x:xmpmeta"), raw.find(b"</x:xmpmeta>")
    if s < 0 or e < 0:
        return {}
    x = raw[s : e + 12].decode("utf-8", "replace")
    out = {k: _xmp_value(x, k) for k in ("CreatorTool", "Software", "DigitalSourceType", "CreateDate", "ModifyDate")}
    out["history_agents"] = sorted(set(re.findall(r'softwareAgent="([^"]+)"', x)))
    crs = {}
    for k in _CRS_KEYS:
        v = re.search(rf'crs:{k}="([^"]*)"', x)
        if v:
            crs[k] = v.group(1)
    if crs:
        out["camera_raw_settings"] = crs
    return {k: v for k, v in out.items() if v}


def png_text(path: str) -> dict:
    """PNG text chunks: A1111 `parameters`, ComfyUI `prompt`/`workflow`, Software/Comment."""
    if not path.lower().endswith(".png"):
        return {}
    try:
        from PIL import Image
    except ImportError:
        return {}
    with Image.open(path) as im:
        info = {k: v for k, v in im.info.items() if isinstance(v, str)}
    out = {}
    for k in ("parameters", "prompt", "workflow", "Software", "Comment", "Description", "Title", "Author"):
        if k in info:
            v = info[k]
            if k in ("prompt", "workflow"):
                with contextlib.suppress(ValueError):  # keep the raw string when it is not JSON
                    v = json.loads(v)
            out[k] = v
    return out


# ---------------------------------------------------------------- EXIF

_EXIF_TAGS = {
    271: "Make",
    272: "Model",
    305: "Software",
    306: "DateTime",
    33434: "ExposureTime",
    33437: "FNumber",
    34855: "ISO",
    36867: "DateTimeOriginal",
    37386: "FocalLength",
    41989: "FocalLengthIn35mmFilm",
    42035: "LensMake",
    42036: "LensModel",
    37385: "Flash",
    41987: "WhiteBalance",
    37383: "MeteringMode",
    34850: "ExposureProgram",
}


def exif(path: str) -> dict:
    try:
        from PIL import Image
    except ImportError:
        return {"note": "Pillow not installed: EXIF skipped"}
    try:
        with Image.open(path) as im:
            ex = im.getexif()
            tags = dict(ex.items())
            tags.update(ex.get_ifd(0x8769).items())  # Exif sub-IFD holds exposure/lens tags
    except Exception:
        return {}
    out = {}
    for code, name in _EXIF_TAGS.items():
        if code in tags:
            v = tags[code]
            if isinstance(v, bytes):
                v = v.decode("utf-8", "replace").strip("\x00 ")
            elif hasattr(v, "numerator"):
                v = round(float(v), 4) if v.denominator else None
            elif isinstance(v, tuple):
                v = list(v)
            out[name] = v
    if isinstance(out.get("ExposureTime"), float) and 0 < out["ExposureTime"] < 1:
        out["ShutterSpeed"] = f"1/{round(1 / out['ExposureTime'])}"
    return out


# ---------------------------------------------------------------- tool fingerprints

# (regex over all gathered metadata text, tool, category, what it tells you)
RULES: list[tuple[str, str, str, str]] = [
    (r"capcut", "CapCut", "edit", "exported from CapCut"),
    (r"premiere", "Adobe Premiere Pro", "edit", "edited/exported in Premiere Pro"),
    (r"after effects", "Adobe After Effects", "motion", "rendered from After Effects"),
    (r"davinci|resolve|blackmagic", "DaVinci Resolve", "edit/color", "rendered from DaVinci Resolve"),
    (r"final ?cut|com\.apple\.proapps", "Final Cut Pro", "edit", "exported from Final Cut Pro"),
    (r"imovie", "iMovie", "edit", "exported from iMovie"),
    (r"handbrake", "HandBrake", "transcode", "re-encoded with HandBrake"),
    (r"inshot", "InShot", "edit", "exported from InShot"),
    (r"lightroom", "Adobe Lightroom", "photo/color", "photo developed in Lightroom"),
    (r"photoshop", "Adobe Photoshop", "photo", "saved from Photoshop"),
    (r"camera raw", "Adobe Camera Raw", "photo/color", "processed with Adobe Camera Raw"),
    (r"snapseed", "Snapseed", "photo", "edited in Snapseed"),
    (r"vsco", "VSCO", "photo/color", "edited in VSCO"),
    (r"canva", "Canva", "design", "made or exported in Canva"),
    (r"firefly", "Adobe Firefly", "ai-image", "generated/edited with Adobe Firefly"),
    (r"dall[·\-\s]?e|openai|chatgpt", "OpenAI image model", "ai-image", "generated by an OpenAI image model"),
    (r"midjourney", "Midjourney", "ai-image", "generated by Midjourney"),
    (r"comfyui|\"class_type\"", "ComfyUI (Stable Diffusion/Flux workflow)", "ai-image", "ComfyUI workflow embedded"),
    (r"steps: \d+, sampler:", "Automatic1111/Forge (Stable Diffusion)", "ai-image", "A1111 generation parameters embedded"),
    (r"trainedalgorithmicmedia", "AI-generated (IPTC declaration)", "ai", "file declares AI-generated content"),
    (r"compositewithtrainedalgorithmicmedia", "AI-edited (IPTC declaration)", "ai", "file declares AI-edited content"),
    (r"google inc|youtube", "YouTube/Google processing", "platform", "re-encoded by Google/YouTube"),
    (r"com\.apple\.quicktime|core media", "Apple capture/AVFoundation pipeline", "capture", "Apple device or framework"),
    (r"com\.android", "Android device", "capture", "recorded on Android"),
    (r"lavf|lavc|libx264|libx265", "FFmpeg libraries", "encode", "muxed/encoded with FFmpeg libs (used by many apps)"),
    (r"lame", "LAME MP3 encoder", "audio", "MP3 encoded with LAME"),
    (r"logic pro", "Logic Pro", "audio", "bounced from Logic Pro"),
    (r"ableton", "Ableton Live", "audio", "exported from Ableton Live"),
    (r"fl studio|image-line", "FL Studio", "audio", "exported from FL Studio"),
    (r"pro tools|avid", "Avid Pro Tools / Media Composer", "audio/edit", "Avid software"),
    (r"elevenlabs", "ElevenLabs", "ai-audio", "AI voice from ElevenLabs"),
    (r"suno", "Suno", "ai-audio", "AI music from Suno"),
    (r"runway", "Runway", "ai-video", "generated/edited in Runway"),
    (r"\bsora\b", "OpenAI Sora", "ai-video", "generated by Sora"),
    (r"\bkling\b", "Kling", "ai-video", "generated by Kling"),
    (r"\bveo\b", "Google Veo", "ai-video", "generated by Veo"),
    (r"heygen", "HeyGen", "ai-video", "HeyGen avatar video"),
    (r"higgsfield", "Higgsfield", "ai-video", "generated in Higgsfield"),
]


def _flatten(d, out: list[str]) -> list[str]:
    if isinstance(d, dict):
        for k, v in d.items():
            out.append(str(k))
            _flatten(v, out)
    elif isinstance(d, list):
        for v in d:
            _flatten(v, out)
    elif d is not None:
        out.append(str(d))
    return out


def fingerprints(meta: dict, level: str = "measured") -> list[dict]:
    """`level`: "measured" for file metadata; "creator_mention" for the post's title/description/tags."""
    text = "\n".join(_flatten(meta, []))
    low = text.lower()
    hits = []
    for pat, tool, cat, means in RULES:
        m = re.search(pat, low)
        if m:
            i = m.start()
            ctx = text[max(0, i - 40) : i + 60].replace("\n", " | ")
            hits.append({"tool": tool, "category": cat, "means": means, "evidence": ctx.strip(), "level": level})
    # a specific editor beats the generic FFmpeg-libs line; keep both but order specific first
    hits.sort(key=lambda h: h["tool"] == "FFmpeg libraries")
    return hits


def gather(path: str, platform: dict | None = None) -> dict:
    """Everything recoverable about the file, plus tool fingerprints and what is missing."""
    kind = media_kind(path)
    raw = _read_edges(path)
    meta = {
        "kind": kind,
        "file": {"name": os.path.basename(path), "bytes": os.path.getsize(path)},
        "container": container(path),
        "xmp": xmp(raw),
        "c2pa_manifest_present": b"c2pa" in raw and b"jumb" in raw,
    }
    if kind == "image":
        meta["exif"] = exif(path)
        meta["png_text"] = png_text(path)
    meta["tool_fingerprints"] = fingerprints({k: v for k, v in meta.items() if k != "file"})
    post = {k: (platform or {}).get(k) for k in ("title", "description", "tags")}
    meta["tools_mentioned_in_post"] = fingerprints(post, "creator_mention") if any(post.values()) else []
    stripped = (
        not meta["xmp"]
        and not meta.get("exif")
        and not meta.get("png_text")
        and not any(
            k.lower()
            not in ("major_brand", "minor_version", "compatible_brands", "encoder", "handler_name", "vendor_id", "duration")
            for k in meta["container"].get("format", {})
        )
    )
    meta["metadata_stripped_likely"] = stripped
    meta["notes"] = [
        "Metadata is measured but can be stripped or rewritten; social platforms usually re-encode uploads.",
        "c2pa_manifest_present is a byte-signature check only; validate with a C2PA verifier before relying on it.",
    ]
    return meta
