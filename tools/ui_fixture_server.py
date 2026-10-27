"""Explicit local UI-only fixture. NOT the FastAPI backend or a deployment mode.

Uses only Python's standard library plus the real mood engine. This allows
visual QA without a key or dependencies, but cannot verify FastAPI/httpx.
Run from repository root: python -m tools.ui_fixture_server
"""

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from app.services.mood_engine import analyze_tags

ROOT = Path(__file__).resolve().parents[1]
TRACKS = [
    ("Space Song", "Beach House", ["dream pop", "dreamy", "indie", "shoegaze"]),
    ("Myth", "Beach House", ["dream pop", "ethereal", "indie", "atmospheric"]),
    ("Master of Puppets", "Metallica", ["metal", "energetic", "dark", "heavy metal"]),
    ("Pink Moon", "Nick Drake", ["folk", "acoustic", "mellow", "singer-songwriter"]),
    ("Around the World", "Daft Punk", ["house", "electronic", "dance", "funk"]),
    ("No Tags / Neutral Study", "Fixture artist", []),
    ("<img src=x onerror=alert(1)>", "Untrusted title fixture", ["jazz"]),
    ("Warm Air", "Fixture artist", ["folk", "romantic", "happy", "dreamy"]),
]


class Handler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass

    def send(self, body, status=200, mime="application/json"):
        if isinstance(body, (dict, list)):
            body = json.dumps(body).encode()
        self.send_response(status)
        self.send_header("Content-Type", mime + ("; charset=utf-8" if mime != "image/svg+xml" else ""))
        self.send_header("Content-Length", str(len(body)))
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        url = urlsplit(self.path)
        query = parse_qs(url.query)
        if url.path == "/":
            html = (ROOT / "app/templates/index.html").read_text(encoding="utf-8")
            html = html.replace("<body>", '<body><aside class="fixture-banner">LOCAL UI FIXTURE — synthetic tags, not live Last.fm. FastAPI is not running.</aside>')
            return self.send(html.encode(), mime="text/html")
        if url.path.startswith("/static/"):
            file = (ROOT / "app" / url.path.lstrip("/")).resolve()
            static = (ROOT / "app/static").resolve()
            if file.is_relative_to(static) and file.is_file():
                mime = {".css": "text/css", ".js": "text/javascript", ".svg": "image/svg+xml"}.get(file.suffix, "application/octet-stream")
                return self.send(file.read_bytes(), mime=mime)
        if url.path == "/health":
            return self.send({"status": "fixture", "lastfm_configured": True, "fixture": True})
        if url.path == "/api/search":
            text = query.get("q", [""])[0]
            if text == "empty":
                return self.send({"tracks": []})
            if text == "error":
                return self.send({"error": {"code": "fixture_error", "message": "Simulated Last.fm error. Please retry."}}, 502)
            if text == "setup":
                return self.send({"error": {"code": "setup_required", "message": "Live search needs LASTFM_API_KEY. Add it to .env or Render Environment, then restart."}}, 503)
            return self.send({"tracks": [{"title": title, "artist": artist, "artwork": None, "url": None, "album": None} for title, artist, _ in TRACKS]})
        if url.path == "/api/analyze":
            selected = next((t for t in TRACKS if t[0] == query.get("track", [""])[0]), TRACKS[0])
            title, artist, names = selected
            tags = [{"name": name, "count": 100 - i * 15} for i, name in enumerate(names)]
            result = {"track": {"title": title, "artist": artist, "album": "Synthetic metadata / local UI verification", "artwork": None, "url": None}, "source": "track" if names else "neutral", "tags": tags, "warnings": ["Synthetic fixture tags. This is not a live Last.fm result."], "analysis": analyze_tags(tags)}
            return self.send(result)
        self.send({"error": {"message": "Not found"}}, 404)


if __name__ == "__main__":
    server = ThreadingHTTPServer(("127.0.0.1", 8765), Handler)
    print("UI FIXTURE ONLY: http://127.0.0.1:8765 - synthetic metadata; Ctrl+C to stop", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
