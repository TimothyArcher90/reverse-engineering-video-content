"""Evidence levels used across every output.

Reverse engineering is only useful if the reader can tell a measurement from
a guess. Every claim in analysis.json and in the agent-written dossier carries
one of these tags.
"""

MEASURED = "measured"    # computed from pixels/samples; reproducible
OBSERVED = "observed"    # seen directly by a human/vision model in a frame
INFERRED = "inferred"    # hypothesis derived from measurements or observation
VERIFIED = "verified"    # hypothesis confirmed against an external source
UNKNOWN = "unknown"      # cannot be determined from the available material

LEVELS = (MEASURED, OBSERVED, INFERRED, VERIFIED, UNKNOWN)


def tag(value, level, **extra):
    """Wrap a value with its evidence level (and optional method/confidence)."""
    if level not in LEVELS:
        raise ValueError(f"unknown evidence level: {level}")
    out = {"value": value, "evidence": level}
    out.update({k: v for k, v in extra.items() if v is not None})
    return out
