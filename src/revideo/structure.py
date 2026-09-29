"""Reel structure from measured cuts: hook, body and payoff, with timing and pacing per part.

The cut times are measured [M]; where each part starts and ends is a heuristic [I] stated in
`rules`, so the plan can say exactly why a boundary sits where it does.
"""

from __future__ import annotations

import statistics

HOOK_MIN, HOOK_MAX, HOOK_DEFAULT = 1.5, 3.5, 3.0  # s: the first cut in this range closes the hook
PAYOFF_ZONE = 0.30  # the payoff starts at a cut in, or just before, the final 30 % of the piece
RULES = [
    f"hook ends at the first cut between {HOOK_MIN} and {HOOK_MAX} s, else at {HOOK_DEFAULT} s",
    f"payoff starts at the last cut inside the final {int(PAYOFF_ZONE * 100)} % of the piece, else at the start "
    "of the shot running when that zone begins",
    "pacing: body first half vs second half cut rate; ±25 % or more is accelerating/decelerating",
]


def _part(name: str, a: float, b: float, cuts: list[float], shots: list[dict]) -> dict:
    inside = [s for s in shots if s["start_sec"] < b - 1e-6 and s["end_sec"] > a + 1e-6]
    n_cuts = sum(1 for t in cuts if a < t < b)
    d = max(1e-6, b - a)
    return {
        "part": name,
        "start_sec": round(a, 3),
        "end_sec": round(b, 3),
        "duration_sec": round(b - a, 3),
        "shots": [s["index"] for s in inside],
        "cuts": n_cuts,
        "cuts_per_sec": round(n_cuts / d, 3),
    }


def analyze(r: dict) -> dict:
    if r.get("kind", "video") != "video" or not r.get("shots"):
        raise SystemExit("reel structure needs a video analysis with shots")
    shots = r["shots"]
    dur = float(shots[-1]["end_sec"])
    cuts = [float(s["start_sec"]) for s in shots[1:]]
    hook_end = next((t for t in cuts if HOOK_MIN <= t <= HOOK_MAX), min(HOOK_DEFAULT, dur))
    late = [t for t in cuts if t >= dur * (1 - PAYOFF_ZONE) and t > hook_end]
    zone = dur * (1 - PAYOFF_ZONE)
    running = next((float(s["start_sec"]) for s in shots if s["start_sec"] <= zone < s["end_sec"]), zone)
    payoff_start = late[-1] if late else max(hook_end, running)
    parts = [
        _part("hook", 0.0, hook_end, cuts, shots),
        _part("body", hook_end, payoff_start, cuts, shots),
        _part("payoff", payoff_start, dur, cuts, shots),
    ]
    mid = (hook_end + payoff_start) / 2
    first = sum(1 for t in cuts if hook_end < t < mid) / max(1e-6, mid - hook_end)
    second = sum(1 for t in cuts if mid <= t < payoff_start) / max(1e-6, payoff_start - mid)
    pacing = (
        "accelerating"
        if second > first * 1.25 and second > 0
        else "decelerating"
        if first > second * 1.25 and first > 0
        else "steady"
    )
    durs = [s["duration_sec"] for s in shots]
    longest = max(shots, key=lambda s: s["duration_sec"])
    return {
        "duration_sec": round(dur, 3),
        "parts": parts,
        "body_pacing": pacing,
        "body_cut_rate_first_second_half": [round(first, 3), round(second, 3)],
        "median_shot_sec": round(statistics.median(durs), 3),
        "longest_shot": {"index": longest["index"], "start_sec": longest["start_sec"], "duration_sec": longest["duration_sec"]},
        "rules": RULES,
    }


def plan_lines(st: dict) -> list[str]:
    L = ["| Part | From → to (s) | Dur (s) | Shots | Cuts/s |", "|---|---|---|---|---|"]
    for p in st["parts"]:
        L.append(
            f"| {p['part']} | {p['start_sec']} → {p['end_sec']} | {p['duration_sec']} | "
            f"{', '.join(map(str, p['shots'])) or '–'} | {p['cuts_per_sec']} |"
        )
    ls = st["longest_shot"]
    L += [
        "",
        f"- Body pacing *{st['body_pacing']}* (cuts/s first vs second half {st['body_cut_rate_first_second_half']}) [M/I]",
        f"- Longest hold: shot {ls['index']} at {ls['start_sec']} s for {ls['duration_sec']} s "
        f"(median shot {st['median_shot_sec']} s)",
        "- Boundaries are heuristics [I]: " + "; ".join(st["rules"]),
    ]
    return L
