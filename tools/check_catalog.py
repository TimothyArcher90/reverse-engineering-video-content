"""Daily freshness check: every tool URL in the catalog must still answer.

Run by .github/workflows/daily.yml. 401/403/429 count as reachable (many sites block bots);
DNS errors, timeouts and 404/5xx fail the run so the catalog gets fixed.

    python tools/check_catalog.py
"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CATALOG = os.path.join(ROOT, "src", "revideo", "data", "tools.json")
BOT_BLOCKED = {401, 403, 405, 429}


def status(url: str) -> int | str:
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (revideo catalog check)"})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return r.status
    except urllib.error.HTTPError as e:
        return e.code
    except Exception as e:  # DNS, TLS, timeout
        return type(e).__name__


def main() -> int:
    with open(CATALOG, encoding="utf-8") as f:
        tools = json.load(f)["tools"]
    bad = []
    for t in tools:
        s = status(t["url"])
        ok = isinstance(s, int) and (s < 400 or s in BOT_BLOCKED)
        print(f"{'ok ' if ok else 'BAD'} {s!s:>18}  {t['name']:<22} {t['url']}")
        if not ok:
            bad.append(t["name"])
    if bad:
        print(f"\n{len(bad)} unreachable: {', '.join(bad)} — update src/revideo/data/tools.json")
        return 1
    print(f"\nall {len(tools)} tool URLs reachable")
    return 0


if __name__ == "__main__":
    sys.exit(main())
