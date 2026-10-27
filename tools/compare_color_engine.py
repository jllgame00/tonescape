"""Snapshot public Last.fm tag evidence for before/after engine comparisons.

No API key, request URL, raw exception or private account metadata is written.
Run with --case ARTIST TRACK (repeatable). Output goes under ignored artifacts/.
"""

import argparse
import asyncio
import json
import os
from pathlib import Path

from dotenv import load_dotenv

from app.services.lastfm import LastFMError, LastFMService
from app.services.mood_engine import analyze_tags


async def capture(cases):
    load_dotenv(Path(__file__).resolve().parents[1] / ".env")
    service = LastFMService(os.getenv("LASTFM_API_KEY"))
    output = []
    try:
        for artist, track in cases:
            try:
                tags = await service.top_tags(artist, track)
                source = "track"
                analysis = analyze_tags(tags)
                if len(analysis["contributions"]) < 2:
                    artist_tags = await service.top_tags(artist)
                    if len(analyze_tags(artist_tags)["contributions"]) > len(analysis["contributions"]):
                        tags, source = artist_tags, "artist"
                analysis = analyze_tags(tags, source=source)
                output.append({"artist": artist, "track": track, "source": source, "tags": tags, "analysis": analysis})
                print(f"Captured {track}: source={source}; confidence={analysis['confidence']}")
            except LastFMError as error:
                output.append({"artist": artist, "track": track, "error": error.code})
                print(f"Live capture unavailable: {error.code}")
    finally:
        await service.close()
    destination = Path("artifacts/color_engine_comparison.json")
    destination.parent.mkdir(exist_ok=True)
    destination.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case", action="append", nargs=2, required=True, metavar=("ARTIST", "TRACK"))
    asyncio.run(capture(parser.parse_args().case))
