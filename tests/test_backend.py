"""Keep the HTTP adapter, fallback orchestration and routes real; mock only Last.fm."""
import httpx
import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.services.lastfm import LastFMService


TRACK = {"name": "Space Song", "artist": "Beach House", "url": "https://www.last.fm/music/Beach+House/_/Space+Song", "listeners": "1234", "mbid": "", "streamable": "0", "image": [{"#text": "", "size": "small"}]}
SEARCH = {"results": {"opensearch:Query": {"role": "request", "searchTerms": "Space Song", "startPage": "1"}, "opensearch:totalResults": "1", "opensearch:startIndex": "0", "opensearch:itemsPerPage": "10", "trackmatches": {"track": [TRACK]}, "@attr": {"for": "Space Song"}}}
TAGS = {"toptags": {"tag": [{"name": "dream pop", "count": "100", "url": "https://www.last.fm/tag/dream+pop"}, {"name": "shoegaze", "count": 60, "url": "https://www.last.fm/tag/shoegaze"}], "@attr": {"artist": "Beach House", "track": "Space Song"}}}
INFO = {"track": {"name": "Space Song", "url": TRACK["url"], "duration": "320000", "listeners": "1234", "playcount": "10000", "artist": {"name": "Beach House", "mbid": "", "url": "https://www.last.fm/music/Beach+House"}, "album": {"title": "Depression Cherry", "artist": "Beach House", "image": [{"size": "extralarge", "#text": "https://lastfm.freetls.fastly.net/i/u/300x300/example.jpg"}]}, "toptags": {"tag": [{"name": "dream pop", "url": "https://www.last.fm/tag/dream+pop"}]}}}


def client_for(handler, key="test-only-key", **kwargs):
    transport = httpx.MockTransport(handler)
    upstream = httpx.AsyncClient(transport=transport)
    service = LastFMService(key, client=upstream, **kwargs)
    return TestClient(create_app(service=service))


def fixture_handler(request):
    method = request.url.params["method"]
    assert request.url.params["format"] == "json"
    assert request.headers["user-agent"].startswith("TONESCAPE/")
    assert request.extensions["timeout"]["read"] <= 10
    payload = {"track.search": SEARCH, "track.getInfo": INFO, "track.getTopTags": TAGS}[method]
    return httpx.Response(200, json=payload)


def test_health_and_missing_key_are_explicit():
    with client_for(lambda _: pytest.fail("Missing key must not call upstream"), key="") as client:
        assert client.get("/health").json() == {"status": "ok", "lastfm_configured": False}
        response = client.get("/api/search", params={"q": "hello"})
        assert response.status_code == 503
        assert response.json()["error"]["code"] == "setup_required"
        assert "LASTFM_API_KEY" in response.json()["error"]["message"]


def test_search_parses_title_artist_and_safe_artwork():
    with client_for(fixture_handler) as client:
        response = client.get("/api/search", params={"q": "Space Song"})
        assert response.status_code == 200
        track = response.json()["tracks"][0]
        assert (track["title"], track["artist"], track["artwork"]) == ("Space Song", "Beach House", None)


def test_search_empty():
    with client_for(lambda _: httpx.Response(200, json={"results": {"trackmatches": {"track": []}}})) as client:
        response = client.get("/api/search", params={"q": "notfound"})
        assert response.status_code == 200
        assert response.json()["tracks"] == []


@pytest.mark.parametrize("payload,status,code", [
    ({"error": 10, "message": "secret upstream message"}, 503, "invalid_api_key"),
    ({"error": 26, "message": "suspended"}, 503, "invalid_api_key"),
    ({"error": 29, "message": "rate limited"}, 429, "rate_limited"),
    ({"error": 11, "message": "offline"}, 502, "upstream_unavailable"),
    ({"error": 6, "message": "Track not found"}, 404, "not_found"),
])
def test_api_errors_are_classified_and_sanitized(payload, status, code):
    with client_for(lambda _: httpx.Response(200, json=payload)) as client:
        response = client.get("/api/search", params={"q": "anything"})
        assert response.status_code == status
        assert response.json()["error"]["code"] == code
        assert "secret upstream" not in response.text
        assert "test-only-key" not in response.text


def test_timeout_does_not_crash_server():
    def timeout(request):
        raise httpx.ReadTimeout("sensitive details", request=request)
    with client_for(timeout) as client:
        response = client.get("/api/search", params={"q": "song"})
        assert response.status_code == 504
        assert response.json()["error"]["code"] == "upstream_timeout"
        assert client.get("/health").status_code == 200


def test_network_failure_is_classified_without_leaking_details():
    def failed(request):
        raise httpx.ConnectError("sensitive connection string", request=request)
    with client_for(failed) as client:
        response = client.get("/api/search", params={"q": "song"})
        assert response.status_code == 502
        assert response.json()["error"]["code"] == "network_error"
        assert "sensitive" not in response.text


def test_http_rate_limit_has_retry_after():
    with client_for(lambda _: httpx.Response(429)) as client:
        response = client.get("/api/search", params={"q": "song"})
        assert response.status_code == 429
        assert response.headers["retry-after"] == "30"


@pytest.mark.parametrize("response", [httpx.Response(200, text="not json"), httpx.Response(200, json=[]), httpx.Response(200, json={"results": []}), httpx.Response(500)])
def test_malformed_or_failed_upstream_is_safe(response):
    with client_for(lambda _: response) as client:
        result = client.get("/api/search", params={"q": "song"})
        assert result.status_code == 502
        assert "Traceback" not in result.text


def test_validation_rejects_blank_or_oversize_queries():
    with client_for(fixture_handler) as client:
        for params in ({"q": " "}, {"q": "x" * 201}, {"q": "ok", "mode": "invalid"}):
            assert client.get("/api/search", params=params).status_code == 422
        assert client.get("/api/analyze", params={"artist": " ", "track": "x"}).status_code == 422


def test_analyze_uses_track_tags_and_album_image():
    with client_for(fixture_handler) as client:
        result = client.get("/api/analyze", params={"artist": "Beach House", "track": "Space Song"}).json()
        assert result["source"] == "track"
        assert result["track"]["album"] == "Depression Cherry"
        assert result["track"]["artwork"].startswith("https://")
        assert result["analysis"]["axes"]["dreaminess"] > 85
        assert result["analysis"]["fallback"] is False
        assert len(result["analysis"]["contributions"]) == 2


def test_artist_fallback_is_labeled_and_lowers_confidence():
    def handler(request):
        method = request.url.params["method"]
        payload = INFO if method == "track.getInfo" else {"toptags": {"tag": []}} if method == "track.getTopTags" else TAGS
        return httpx.Response(200, json=payload)
    with client_for(handler) as client:
        result = client.get("/api/analyze", params={"artist": "Beach House", "track": "Space Song"}).json()
        assert result["source"] == "artist"
        assert result["analysis"]["confidence"] <= 45
        assert result["analysis"]["source_weight"] == 0.45
        assert "45%" in result["analysis"]["notice"]
        assert any("Artist" in w for w in result["warnings"])


def test_no_interpretable_tags_uses_neutral():
    def handler(request):
        return httpx.Response(200, json=INFO if request.url.params["method"] == "track.getInfo" else {"toptags": {"tag": [{"name": "seen live", "count": 100}]}})
    with client_for(handler) as client:
        result = client.get("/api/analyze", params={"artist": "Beach House", "track": "Space Song"}).json()
        assert result["source"] == "neutral"
        assert result["analysis"]["confidence"] == 0


def test_artist_search_returns_tracks():
    def handler(request):
        if request.url.params["method"] == "artist.search":
            return httpx.Response(200, json={"results": {"artistmatches": {"artist": [{"name": "Beach House", "mbid": "", "url": "https://www.last.fm/music/Beach+House", "image": []}]}}})
        return httpx.Response(200, json={"toptracks": {"track": [dict(TRACK, artist={"name": "Beach House", "mbid": "", "url": "https://www.last.fm/music/Beach+House"})]}})
    with client_for(handler) as client:
        response = client.get("/api/search", params={"q": "Beach House", "mode": "artist"})
        assert response.status_code == 200
        assert response.json()["tracks"][0]["title"] == "Space Song"


def test_ttl_cache_avoids_repeated_http_and_expires():
    calls = []
    clock = [0]
    def handler(request):
        calls.append(request)
        return httpx.Response(200, json=SEARCH)
    with client_for(handler, clock=lambda: clock[0], ttl=60) as client:
        for _ in range(2):
            assert client.get("/api/search", params={"q": "song"}).status_code == 200
        assert len(calls) == 1
        clock[0] = 61
        assert client.get("/api/search", params={"q": "song"}).status_code == 200
        assert len(calls) == 2


def test_singleton_tags_and_unsafe_image_are_normalized():
    def handler(request):
        if request.url.params["method"] == "track.getInfo":
            return httpx.Response(200, json={"track": {"name": "X", "artist": {"name": "Y"}, "album": {"image": [{"#text": "javascript:alert(1)", "size": "large"}]}}})
        return httpx.Response(200, json={"toptags": {"tag": {"name": "rock", "count": "100"}}})
    with client_for(handler) as client:
        result = client.get("/api/analyze", params={"artist": "Y", "track": "X"}).json()
        assert result["track"]["artwork"] is None
        assert result["analysis"]["confidence"] > 0


def test_security_headers_and_landing():
    with client_for(fixture_handler) as client:
        response = client.get("/")
        assert response.status_code == 200
        assert "TONESCAPE" in response.text
        assert response.headers["x-content-type-options"] == "nosniff"
        assert "script-src 'self'" in response.headers["content-security-policy"]
