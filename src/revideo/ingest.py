"""Acquire the source: URL (via yt-dlp) or local file, plus platform metadata and subtitles."""

from __future__ import annotations

import glob
import json
import os
import re
import shutil

# Platform metadata worth keeping: it is part of "what was published and how".
META_KEYS = (
    "id",
    "title",
    "description",
    "uploader",
    "uploader_id",
    "channel",
    "upload_date",
    "timestamp",
    "duration",
    "view_count",
    "like_count",
    "comment_count",
    "repost_count",
    "tags",
    "categories",
    "webpage_url",
    "extractor",
    "track",
    "artist",
    "album",
)


def is_url(s: str) -> bool:
    return bool(re.match(r"^https?://", s))


def acquire(source: str, workdir: str, max_height: int = 1080) -> dict:
    """Return {"video": path, "meta": {...}, "subtitles": [paths]}."""
    src_dir = os.path.join(workdir, "source")
    os.makedirs(src_dir, exist_ok=True)

    if not is_url(source):
        if not os.path.isfile(source):
            raise FileNotFoundError(source)
        dest = os.path.join(src_dir, os.path.basename(source))
        if os.path.abspath(dest) != os.path.abspath(source):
            shutil.copy2(source, dest)
        subs = [p for p in glob.glob(os.path.splitext(source)[0] + "*.vtt") + glob.glob(os.path.splitext(source)[0] + "*.srt")]
        return {"video": dest, "meta": {"source": "local_file", "filename": os.path.basename(source)}, "subtitles": subs}

    try:
        import yt_dlp
    except ImportError as e:  # pragma: no cover
        raise RuntimeError("URL input needs yt-dlp: pip install yt-dlp") from e

    opts = {
        "outtmpl": os.path.join(src_dir, "video.%(ext)s"),
        "format": (
            f"bv*[height<={max_height}][ext=mp4]+ba[ext=m4a]/b[height<={max_height}][ext=mp4]/bv*[height<={max_height}]+ba/b"
        ),
        "merge_output_format": "mp4",
        "writesubtitles": True,
        "writeautomaticsub": True,
        "subtitleslangs": ["es.*", "en.*", "orig"],
        "subtitlesformat": "vtt",
        "writeinfojson": True,
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
    }
    from .video import find_ffmpeg

    if find_ffmpeg():
        opts["ffmpeg_location"] = find_ffmpeg()
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(source, download=True)
        video = ydl.prepare_filename(info)
    if not os.path.exists(video):
        cands = [p for p in glob.glob(os.path.join(src_dir, "video.*")) if not p.endswith((".json", ".vtt"))]
        if not cands:
            raise RuntimeError("download finished but no video file was found")
        video = cands[0]
    meta = {k: info.get(k) for k in META_KEYS if info.get(k) is not None}
    meta["source"] = "url"
    meta["input_url"] = source
    with open(os.path.join(src_dir, "platform_meta.json"), "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)
    return {"video": video, "meta": meta, "subtitles": sorted(glob.glob(os.path.join(src_dir, "*.vtt")))}


_TS = re.compile(r"(\d+):(\d{2}):(\d{2})[.,](\d{3})|(\d{2}):(\d{2})[.,](\d{3})")


def _secs(s: str) -> float:
    m = _TS.search(s)
    if not m:
        return 0.0
    if m.group(1):
        h, mi, se, ms = (int(m.group(i)) for i in range(1, 5))
    else:
        h, mi, se, ms = 0, int(m.group(5)), int(m.group(6)), int(m.group(7))
    return h * 3600 + mi * 60 + se + ms / 1000


def parse_subtitles(path: str) -> list[dict]:
    """Parse VTT/SRT into [{start, end, text}], de-duplicating rolling auto-captions."""
    with open(path, encoding="utf-8", errors="ignore") as f:
        blocks = re.split(r"\n\s*\n", f.read())
    out: list[dict] = []
    for b in blocks:
        lines = [ln for ln in b.strip().splitlines() if ln.strip()]
        arrow = next((i for i, ln in enumerate(lines) if "-->" in ln), None)
        if arrow is None:
            continue
        start_s, end_s = lines[arrow].split("-->")[:2]
        text = " ".join(re.sub(r"<[^>]+>", "", ln).strip() for ln in lines[arrow + 1 :]).strip()
        if not text:
            continue
        if out and (text == out[-1]["text"] or text.startswith(out[-1]["text"])):
            out[-1]["text"] = text
            out[-1]["end"] = _secs(end_s)
            continue
        out.append({"start": round(_secs(start_s), 3), "end": round(_secs(end_s), 3), "text": text})
    return out


def transcribe_whisper(audio_path: str, model: str = "small") -> list[dict] | None:
    """Optional local transcription with faster-whisper, if installed."""
    try:
        from faster_whisper import WhisperModel
    except ImportError:
        return None
    wm = WhisperModel(model, device="auto", compute_type="auto")
    segments, _ = wm.transcribe(audio_path, vad_filter=True)
    return [{"start": round(s.start, 3), "end": round(s.end, 3), "text": s.text.strip()} for s in segments]
