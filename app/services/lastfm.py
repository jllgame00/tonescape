"""Last.fm HTTP adapter. Never log request URLs: they contain the API key.

Official methods: https://www.last.fm/api (see README for individual links).
The cache is bounded, process-local and TTL-based; errors are never cached.
"""

import asyncio
from collections import OrderedDict
from copy import deepcopy
import time
from urllib.parse import urlsplit

import httpx

from app.services.mood_engine import analyze_tags

API_URL = "https://ws.audioscrobbler.com/2.0/"
USER_AGENT = "TONESCAPE/1.0 (educational music metadata visualizer)"


class LastFMError(Exception):
    def __init__(self, code, message, status=502):
        super().__init__(message)
        self.code, self.message, self.status = code, message, status


def malformed():
    return LastFMError("invalid_response", "Last.fm returned an unexpected response. Please try again.")


def object_at(payload, key):
    value = payload.get(key)
    if not isinstance(value, dict):
        raise malformed()
    return value


def as_list(value):
    if value is None or value == "":
        return []
    if isinstance(value, dict):
        return [value]
    if isinstance(value, list):
        return [item for item in value if isinstance(item, dict)]
    raise malformed()


def safe_url(value, artwork=False):
    if not isinstance(value, str):
        return None
    try:
        parsed = urlsplit(value)
        host = (parsed.hostname or "").lower()
        allowed = ("lastfm.freetls.fastly.net", "lastfm-img2.akamaized.net", "userserve-ak.last.fm") if artwork else ("www.last.fm", "last.fm")
        if parsed.scheme in ("http", "https") and host in allowed and not parsed.username and not parsed.password and parsed.port in (None, 80, 443):
            return parsed._replace(scheme="https", netloc=host).geturl()
    except ValueError:
        pass
    return None


def artwork_from(images):
    for image in reversed(as_list(images)):
        url = safe_url(image.get("#text"), artwork=True)
        # Last.fm sometimes returns its universal blank artwork placeholder.
        if url and "2a96cbd8b46e442fc41c2b86b821562f" not in url:
            return url
    return None


def track_from(data, artist=None):
    raw_artist = data.get("artist", artist)
    if isinstance(raw_artist, dict):
        raw_artist = raw_artist.get("name")
    title = data.get("name")
    if not isinstance(title, str) or not isinstance(raw_artist, str) or not title.strip() or not raw_artist.strip():
        return None
    return {"title": title[:300], "artist": raw_artist[:200], "artwork": artwork_from(data.get("image")), "url": safe_url(data.get("url")), "album": None}


class LastFMService:
    def __init__(self, api_key, client=None, ttl=300, clock=time.monotonic):
        self.api_key = (api_key or "").strip()
        self.client = client or httpx.AsyncClient(follow_redirects=False, limits=httpx.Limits(max_connections=12, max_keepalive_connections=6))
        self.ttl, self.clock = ttl, clock
        self.cache = OrderedDict()
        self.inflight = {}
        self.semaphore = asyncio.Semaphore(8)

    async def close(self):
        await self.client.aclose()

    async def request(self, method, **params):
        if not self.api_key:
            raise LastFMError("setup_required", "Live search needs LASTFM_API_KEY. Add your Last.fm API key to .env locally or Environment on Render, then restart the service.", 503)
        key = (method, tuple(sorted(params.items())))
        cached = self.cache.get(key)
        if cached and cached[0] > self.clock():
            self.cache.move_to_end(key)
            return deepcopy(cached[1])
        if key not in self.inflight:
            task = asyncio.create_task(self._fetch_and_cache(key, method, params))
            self.inflight[key] = task
            task.add_done_callback(lambda done: self._finish_request(key, done))
        return deepcopy(await asyncio.shield(self.inflight[key]))

    def _finish_request(self, key, task):
        self.inflight.pop(key, None)
        if not task.cancelled():
            task.exception()  # Consume an exception even if all callers disconnected.

    async def _fetch_and_cache(self, key, method, params):
        try:
            async with self.semaphore:
                response = await self.client.get(API_URL, params={"method": method, "api_key": self.api_key, "format": "json", **params}, headers={"User-Agent": USER_AGENT}, timeout=httpx.Timeout(8, connect=4))
            if response.status_code == 429:
                raise LastFMError("rate_limited", "Last.fm is receiving too many requests. Please wait a moment and retry.", 429)
            if response.status_code in (401, 403):
                raise LastFMError("invalid_api_key", "Last.fm rejected the configured API key. The service owner must check LASTFM_API_KEY.", 503)
            response.raise_for_status()
            data = response.json()
        except httpx.TimeoutException:
            raise LastFMError("upstream_timeout", "Last.fm took too long to respond. Please try again.", 504) from None
        except httpx.RequestError:
            raise LastFMError("network_error", "Could not reach Last.fm. Please try again shortly.") from None
        except (httpx.HTTPStatusError, ValueError):
            raise LastFMError("upstream_unavailable", "Last.fm is temporarily unavailable. Please try again.") from None
        if not isinstance(data, dict):
            raise malformed()
        if "error" in data:
            code = str(data["error"])
            if code in ("4", "9", "10", "26"):
                raise LastFMError("invalid_api_key", "Last.fm rejected the configured API key. The service owner must check LASTFM_API_KEY.", 503)
            if code == "29":
                raise LastFMError("rate_limited", "Last.fm rate limit reached. Please wait a moment and retry.", 429)
            if code in ("6", "7"):
                raise LastFMError("not_found", "This track or artist could not be found on Last.fm.", 404)
            raise LastFMError("upstream_unavailable", "Last.fm is temporarily unavailable. Please try again.")
        self.cache[key] = (self.clock() + self.ttl, data)
        self.cache.move_to_end(key)
        while len(self.cache) > 256:
            self.cache.popitem(last=False)
        return data

    async def search(self, query, mode="track"):
        if mode == "artist":
            data = await self.request("artist.search", artist=query, limit=1)
            artists = as_list(object_at(object_at(data, "results"), "artistmatches").get("artist"))
            if not artists or not isinstance(artists[0].get("name"), str):
                return []
            artist = artists[0]["name"]
            data = await self.request("artist.getTopTracks", artist=artist, limit=10, autocorrect=1)
            tracks = as_list(object_at(data, "toptracks").get("track"))
        else:
            artist = None
            data = await self.request("track.search", track=query, limit=10)
            tracks = as_list(object_at(object_at(data, "results"), "trackmatches").get("track"))
        unique = {}
        for item in tracks[:10]:
            track = track_from(item, artist)
            if track:
                unique.setdefault((track["title"], track["artist"]), track)
        return list(unique.values())

    async def track_info(self, artist, track):
        data = await self.request("track.getInfo", artist=artist, track=track, autocorrect=1)
        info = object_at(data, "track")
        result = track_from(info, artist)
        if not result:
            raise malformed()
        album = info.get("album", {})
        if isinstance(album, dict):
            result["artwork"] = artwork_from(album.get("image")) or result["artwork"]
            result["album"] = album.get("title") if isinstance(album.get("title"), str) else None
        return result

    async def top_tags(self, artist, track=None):
        params = {"artist": artist, "autocorrect": 1}
        if track is not None:
            params["track"] = track
        data = await self.request("track.getTopTags" if track is not None else "artist.getTopTags", **params)
        return as_list(object_at(data, "toptags").get("tag"))[:50]

    async def analyze(self, artist, title):
        # Metadata is optional enrichment, tags are the analysis evidence.
        results = await asyncio.gather(self.track_info(artist, title), self.top_tags(artist, title), return_exceptions=True)
        track, raw_tags = results
        warnings = []
        if isinstance(track, LastFMError):
            if track.code == "invalid_api_key" or track.code == "setup_required":
                raise track
            track = {"title": title, "artist": artist, "artwork": None, "url": None, "album": None}
            warnings.append("Album metadata is unavailable; using the selected track name.")
        elif isinstance(track, Exception):
            raise track
        source = "track"
        if isinstance(raw_tags, LastFMError):
            if raw_tags.code != "not_found":
                raise raw_tags
            raw_tags = []
        elif isinstance(raw_tags, Exception):
            raise raw_tags
        analysis = analyze_tags(raw_tags)
        if len(analysis["contributions"]) < 2:
            try:
                artist_tags = await self.top_tags(track["artist"])
                artist_analysis = analyze_tags(artist_tags, source="artist")
                if len(artist_analysis["contributions"]) > len(analysis["contributions"]):
                    raw_tags, analysis, source = artist_tags, artist_analysis, "artist"
                    warnings.append("Artist tags were used because this track had too few interpretable tags. They may not describe this particular song.")
            except LastFMError as error:
                if error.code in ("invalid_api_key", "setup_required"):
                    raise
                warnings.append("Artist fallback tags are unavailable; confidence reflects the remaining track evidence.")
        if analysis["fallback"]:
            source = "neutral"
        tags = []
        for tag in raw_tags[:12]:
            if isinstance(tag.get("name"), str):
                tags.append({"name": tag["name"][:100], "count": str(tag.get("count", 0))[:20]})
        return {"track": track, "source": source, "tags": tags, "warnings": warnings, "analysis": analysis}
