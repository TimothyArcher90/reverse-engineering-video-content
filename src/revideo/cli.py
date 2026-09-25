"""revideo command line."""

from __future__ import annotations

import argparse
import json
import os
import sys


def main(argv=None) -> int:
    for stream in (sys.stdout, sys.stderr):  # Windows consoles may not encode ✓ → ▸
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(errors="replace")
    from . import __version__

    p = argparse.ArgumentParser(prog="revideo", description="Reverse engineering for video content.")
    p.add_argument("--version", action="version", version=f"revideo {__version__}")
    sub = p.add_subparsers(dest="cmd", required=True)

    a = sub.add_parser("analyze", help="measure a video, photo or audio file (path or URL) → analysis.json, reports, plan")
    a.add_argument("source")
    a.add_argument("--kind", choices=["video", "image", "audio"], help="force the input type (default: from the extension)")
    a.add_argument("-o", "--out", default=None, help="output dir (default: runs/<name>)")
    a.add_argument("--threshold", type=float, default=0.3, help="builtin cut detector sensitivity (lower = more cuts)")
    a.add_argument(
        "--engine",
        choices=["builtin", "scenedetect"],
        default="builtin",
        help="cut detector (builtin is validated with flash rejection; scenedetect needs PySceneDetect)",
    )
    a.add_argument("--no-audio", action="store_true")
    a.add_argument("--no-motion", action="store_true")
    a.add_argument("--whisper", default=None, help="faster-whisper model name if no subtitles (e.g. small)")
    a.add_argument("-q", "--quiet", action="store_true")

    i = sub.add_parser("index-ref", help="fingerprint a reference film you have on disk")
    i.add_argument("film")
    i.add_argument("-o", "--out", required=True, help="index path (.npz)")
    i.add_argument("--fps", type=float, default=2.0, help="sampling rate for the coarse index")
    i.add_argument("--title")
    i.add_argument("--director")
    i.add_argument("--dp", help="director of photography")
    i.add_argument("--year", type=int)

    m = sub.add_parser("match-ref", help="find exact film frames for each shot of an analysis")
    m.add_argument("analysis_dir")
    m.add_argument("index", nargs="+", help="one or more .npz indexes")
    m.add_argument("--max-distance", type=int, default=12, help="pHash Hamming distance accepted as a match (0–64)")
    m.add_argument("--min-correlation", type=float, default=0.8, help="thumbnail correlation required (0–1)")

    rp = sub.add_parser("report", help="rebuild report.md / report.html from analysis.json")
    rp.add_argument("analysis_dir")

    c = sub.add_parser("compare", help="score a replica against the original (0–100)")
    c.add_argument("original")
    c.add_argument("replica")
    c.add_argument("--json", action="store_true")

    pl = sub.add_parser("plan", help="(re)write replication_plan.md: per-shot specs, grade recipe, gear and tools per budget")
    pl.add_argument("analysis_dir")

    sub.add_parser("tools", help="list the tool catalog used by replication plans")
    sub.add_parser("doctor", help="check dependencies")

    args = p.parse_args(argv)

    if args.cmd == "analyze":
        from .advise import write_plan
        from .forensics import media_kind

        name = os.path.splitext(os.path.basename(args.source.split("?")[0].rstrip("/")))[0] or "media"
        out = args.out or os.path.join("runs", "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in name)[:60])
        os.makedirs(out, exist_ok=True)
        kind = args.kind or media_kind(args.source)
        if kind == "image":
            from .media import analyze_image

            analyze_image(args.source, out, quiet=args.quiet)
        elif kind == "audio":
            from .media import analyze_audio

            analyze_audio(args.source, out, whisper=args.whisper, quiet=args.quiet)
        else:
            from .pipeline import analyze

            analyze(
                args.source,
                out,
                threshold=args.threshold,
                engine=args.engine,
                no_audio=args.no_audio,
                no_motion=args.no_motion,
                whisper=args.whisper,
                quiet=args.quiet,
            )
        plan_path = write_plan(out)
        if not args.quiet:
            print(f"▸ replication plan → {plan_path}")
        return 0

    if args.cmd == "plan":
        from .advise import write_plan

        print(f"replication plan → {write_plan(args.analysis_dir)}")
        return 0

    if args.cmd == "tools":
        from .advise import load_catalog

        cat = load_catalog()
        print(f"catalog {cat['catalog_date']} · prices verified: {cat['prices_verified']}")
        for t in cat["tools"]:
            print(f"- {t['name']:<22} {t['category']:<12} {'/'.join(t['tiers']):<20} {t['pricing_model']:<40} {t['url']}")
        return 0

    if args.cmd == "index-ref":
        from .references import index_reference

        path = index_reference(args.film, args.out, args.fps, args.title, args.director, args.year, args.dp)
        print(f"indexed → {path}")
        return 0

    if args.cmd == "match-ref":
        from .references import best_per_shot, match
        from .report import write_reports

        apath = os.path.join(args.analysis_dir, "analysis.json")
        with open(apath, encoding="utf-8") as f:
            res = json.load(f)
        kf = {s["index"]: {k: os.path.join(args.analysis_dir, v) for k, v in s["keyframes"].items()} for s in res["shots"]}
        allm = []
        qf = {s["index"]: {**s.get("keyframe_frames", {}), "start": s["start_frame"]} for s in res["shots"]}
        qfps = res["source"]["video"]["fps"]
        for idx in args.index:
            allm.extend(match(kf, idx, args.max_distance, args.min_correlation, query_frames=qf, query_fps=qfps))
        merged = best_per_shot(allm)
        with open(os.path.join(args.analysis_dir, "reference_matches.json"), "w", encoding="utf-8") as f:
            json.dump(merged, f, ensure_ascii=False, indent=2)
        by_shot = {m["shot"]: m for m in merged if m["match"]}
        for s in res["shots"]:
            s["reference_match"] = by_shot.get(s["index"])
        with open(apath, "w", encoding="utf-8") as f:
            json.dump(res, f, ensure_ascii=False, indent=2)
        write_reports(res, args.analysis_dir)
        for h in by_shot.values():
            film = h["film"].get("title") or h["index"]
            at = f" [{h['query_keyframe']} {h.get('query_timecode', '')}]"
            print(
                f"shot {h['shot']:>3}{at} → {film} @ {h['film_timecode']} (frame {h['film_frame']}, "
                f"r={h['correlation']}, dist {h['hash_distance']}, crop {h['crop']}{', mirrored' if h['mirrored'] else ''})"
            )
        print(f"{len(by_shot)} verified matches / {len(kf)} shots → reference_matches.json (merged into analysis.json)")
        return 0

    if args.cmd == "report":
        from .report import write_reports

        with open(os.path.join(args.analysis_dir, "analysis.json"), encoding="utf-8") as f:
            write_reports(json.load(f), args.analysis_dir)
        print(f"reports written → {args.analysis_dir}")
        return 0

    if args.cmd == "compare":
        from .compare import compare, to_markdown

        res = compare(args.original, args.replica)
        print(json.dumps(res, indent=2) if args.json else to_markdown(res))
        return 0

    if args.cmd == "doctor":
        from .video import find_ffmpeg

        ok = True
        for mod in ("numpy", "cv2", "PIL", "scenedetect", "yt_dlp", "faster_whisper"):
            try:
                __import__(mod)
                print(f"✓ {mod}")
            except ImportError:
                req = mod in ("numpy", "cv2", "PIL")
                ok &= not req
                print(f"{'✗' if req else '·'} {mod} {'(required)' if req else '(optional)'}")
        print(f"{'✓' if find_ffmpeg() else '·'} ffmpeg (optional, needed for audio)")
        return 0 if ok else 1
    return 1


if __name__ == "__main__":
    sys.exit(main())
