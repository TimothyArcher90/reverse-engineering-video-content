"""revideo command line."""

from __future__ import annotations

import argparse
import json
import os
import sys


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="revideo", description="Reverse engineering for video content.")
    sub = p.add_subparsers(dest="cmd", required=True)

    a = sub.add_parser("analyze", help="measure a video (URL or file) → analysis.json, report.md, dossier.md")
    a.add_argument("source")
    a.add_argument("-o", "--out", default=None, help="output dir (default: runs/<name>)")
    a.add_argument("--threshold", type=float, default=0.35, help="builtin cut detector sensitivity (lower = more cuts)")
    a.add_argument("--engine", choices=["auto", "builtin", "scenedetect"], default="auto")
    a.add_argument("--no-audio", action="store_true")
    a.add_argument("--no-motion", action="store_true")
    a.add_argument("--whisper", default=None, help="faster-whisper model name if no subtitles (e.g. small)")
    a.add_argument("-q", "--quiet", action="store_true")

    i = sub.add_parser("index-ref", help="fingerprint a reference film you have on disk")
    i.add_argument("film")
    i.add_argument("-o", "--out", required=True, help="index path (.npz)")
    i.add_argument("--fps", type=float, default=2.0, help="sampling rate for the coarse index")
    i.add_argument("--title"); i.add_argument("--director"); i.add_argument("--year", type=int)

    m = sub.add_parser("match-ref", help="find exact film frames for each shot of an analysis")
    m.add_argument("analysis_dir")
    m.add_argument("index", nargs="+", help="one or more .npz indexes")
    m.add_argument("--max-distance", type=int, default=12, help="pHash Hamming distance accepted as a match (0–64)")

    c = sub.add_parser("compare", help="score a replica against the original (0–100)")
    c.add_argument("original"); c.add_argument("replica")
    c.add_argument("--json", action="store_true")

    sub.add_parser("doctor", help="check dependencies")

    args = p.parse_args(argv)

    if args.cmd == "analyze":
        from .pipeline import analyze

        name = os.path.splitext(os.path.basename(args.source.rstrip("/")))[0] or "video"
        out = args.out or os.path.join("runs", "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in name)[:60])
        analyze(args.source, out, threshold=args.threshold, engine=args.engine, no_audio=args.no_audio,
                no_motion=args.no_motion, whisper=args.whisper, quiet=args.quiet)
        return 0

    if args.cmd == "index-ref":
        from .references import index_reference

        index_reference(args.film, args.out, args.fps, args.title, args.director, args.year)
        print(f"indexed → {args.out}")
        return 0

    if args.cmd == "match-ref":
        from .references import match

        with open(os.path.join(args.analysis_dir, "analysis.json"), encoding="utf-8") as f:
            res = json.load(f)
        kf = {s["index"]: {k: os.path.join(args.analysis_dir, v) for k, v in s["keyframes"].items()} for s in res["shots"]}
        allm = []
        for idx in args.index:
            allm.extend(match(kf, idx, args.max_distance))
        hits = [x for x in allm if x["match"]]
        with open(os.path.join(args.analysis_dir, "reference_matches.json"), "w", encoding="utf-8") as f:
            json.dump(allm, f, ensure_ascii=False, indent=2)
        for h in hits:
            film = h["film"].get("title") or "reference"
            print(f"shot {h['shot']:>3} → {film} @ {h['film_timecode']} (frame {h['film_frame']}, "
                  f"dist {h['hash_distance']}, crop {h['crop']}{', mirrored' if h['mirrored'] else ''})")
        print(f"{len(hits)} verified matches / {len(kf)} shots → reference_matches.json")
        return 0

    if args.cmd == "compare":
        from .compare import compare, to_markdown

        res = compare(args.original, args.replica)
        print(json.dumps(res, indent=2) if args.json else to_markdown(res))
        return 0

    if args.cmd == "doctor":
        from .video import find_ffmpeg

        ok = True
        for mod in ("numpy", "cv2", "scenedetect", "yt_dlp", "faster_whisper"):
            try:
                __import__(mod)
                print(f"✓ {mod}")
            except ImportError:
                req = mod in ("numpy", "cv2")
                ok &= not req
                print(f"{'✗' if req else '·'} {mod} {'(required)' if req else '(optional)'}")
        print(f"{'✓' if find_ffmpeg() else '·'} ffmpeg (optional, needed for audio)")
        return 0 if ok else 1
    return 1


if __name__ == "__main__":
    sys.exit(main())
