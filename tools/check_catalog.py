"""Daily freshness check: every tool URL in the catalog must still answer.

Run by .github/workflows/daily.yml. 401/403/429 count as reachable (many sites block bots).
Timeouts are warnings: some CDNs (adobe.com) stall non-browser clients instead of answering.
DNS/TLS errors and 404/5xx fail the run so the catalog gets fixed.

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
HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}


def status(url: str) -> int | str:
    req = urllib.request.Request(url, headers=HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return r.status
    except urllib.error.HTTPError as e:
        return e.code
    except TimeoutError:
        return "timeout"
    except urllib.error.URLError as e:
        return "timeout" if isinstance(e.reason, TimeoutError) else f"URLError({e.reason})"
    except Exception as e:  # DNS, TLS
        return type(e).__name__


def main() -> int:
    with open(CATALOG, encoding="utf-8") as f:
        tools = json.load(f)["tools"]
    bad, slow = [], []
    for t in tools:
        s = status(t["url"])
        ok = isinstance(s, int) and (s < 400 or s in BOT_BLOCKED)
        tag = "ok  " if ok else "WARN" if s == "timeout" else "BAD "
        print(f"{tag} {s!s:>18}  {t['name']:<22} {t['url']}")
        if s == "timeout":
            slow.append(t["name"])
        elif not ok:
            bad.append(t["name"])
    if slow:
        print(f"\n{len(slow)} timed out (warning, often bot throttling): {', '.join(slow)}")
    if bad:
        print(f"\n{len(bad)} unreachable: {', '.join(bad)} — update src/revideo/data/tools.json")
        return 1
    print(f"\nall {len(tools)} tool URLs reachable")
    return 0


if __name__ == "__main__":
    sys.exit(main())
