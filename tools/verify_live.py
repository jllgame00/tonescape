"""Smoke-check an already running app without printing credentials.

python -m tools.verify_live [http://127.0.0.1:8000]
Requires the server to have LASTFM_API_KEY configured. Network calls go through
the actual backend. Fails clearly if any expected step fails.
"""

import json
import sys
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import urlopen


def main():
    base = (sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000").rstrip("/")

    def get(path, **params):
        try:
            with urlopen(base + path + ("?" + urlencode(params) if params else ""), timeout=40) as response:
                return json.load(response)
        except HTTPError as error:
            try:
                message = json.load(error).get("error", {}).get("message", "Request failed")
            except (ValueError, AttributeError):
                message = "Request failed"
            raise SystemExit(f"FAIL: HTTP {error.code}: {message}") from None
        except URLError:
            raise SystemExit("FAIL: Could not reach the app. Start Uvicorn first.") from None

    health = get("/health")
    if health.get("status") != "ok" or not health.get("lastfm_configured"):
        raise SystemExit("FAIL: Start the real FastAPI app with LASTFM_API_KEY configured; fixture servers are not valid for this check.")
    print("PASS /health; key configured (validity checked by next request)")
    search = get("/api/search", q="Believe")
    if not search.get("tracks"):
        raise SystemExit("FAIL: Last.fm returned no search results for Believe.")
    track = search["tracks"][0]
    print("PASS live track search")
    result = get("/api/analyze", artist=track["artist"], track=track["title"])
    if len(result.get("analysis", {}).get("palette", [])) != 5:
        raise SystemExit("FAIL: Analysis did not produce five colors.")
    print(f"PASS live analysis; tag source={result['source']}; confidence={result['analysis']['confidence']}")
    print("Next: verify browser search, selection, artwork and HEX copy on your deployed URL.")


if __name__ == "__main__":
    main()
