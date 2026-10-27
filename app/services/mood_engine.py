"""Pure deterministic tag -> mood + circular hue -> HSL engine (version 2).

Counts are sqrt-scaled to reduce popular-tag dominance. A single neutral
pseudoweight regularizes sparse evidence without introducing randomness.
Canonical sorting and deduplication make results independent of input order.
"""

import math
import re
import unicodedata

from app.services.tag_lexicon import ALIASES, AXES, IGNORED, LEXICON
from app.services.color_engine import clamp, hue_identity, hue_name, palette_from_axes


def normalize_tag(name):
    if not isinstance(name, str):
        return ""
    text = unicodedata.normalize("NFKC", name).casefold().replace("&", " and ")
    text = re.sub(r"[^\w\s]", " ", text).replace("_", " ")
    text = " ".join(text.split())
    return ALIASES.get(text, text)


def resolve_tag(name):
    if name in IGNORED or not name:
        return None
    if name in LEXICON:
        return name, LEXICON[name], 1.0
    # Whole phrases only: 'poppyseed' must never match 'pop'. Prefer specific
    # multi-word genres, then deterministic lexical order for tied families.
    for family in sorted(LEXICON, key=lambda k: (-len(k.split()), -len(k), k)):
        if f" {family} " in f" {name} ":
            return family, LEXICON[family], 0.6
    return None


def prepare_tags(tags):
    unique = {}
    for tag in tags:
        if not isinstance(tag, dict):
            continue
        name = normalize_tag(tag.get("name", ""))
        try:
            count = float(tag.get("count", 0))
        except (ValueError, TypeError):
            continue
        if not name or not math.isfinite(count) or count <= 0 or name in IGNORED:
            continue
        # Repeated aliases describe the same evidence, never additional votes.
        unique[name] = max(unique.get(name, 0), min(count, 1_000_000))
    return sorted(unique.items(), key=lambda t: (-t[1], t[0]))[:50]


def mood_keywords(axes):
    pairs = [
        ("dreaminess", "Dreamy", "Grounded"), ("energy", "Energetic", "Calm"),
        ("warmth", "Warm", "Cool"), ("darkness", "Dark", "Bright"),
        ("tension", "Tense", "Soft"),
    ]
    ranked = sorted(enumerate(pairs), key=lambda p: (-abs(axes[p[1][0]] - 50), p[0]))
    words = [high if axes[axis] >= 50 else low for _, (axis, high, low) in ranked[:4]]
    return words if any(abs(v - 50) > 8 for v in axes.values()) else ["Balanced", "Soft", "Understated"]


def explain(axes, fallback, identity, source):
    if fallback:
        return "Too few interpretable mood tags were available. A neutral baseline creates this balanced palette; it does not describe the song's sound."
    evidence = sorted(identity["tags"], key=lambda vote: (-vote["weight"], vote["tag"]))[:3]
    names = ", ".join(vote["tag"] for vote in evidence)
    origin = (f"The {names} tags set a {hue_name(identity['base_hue'])} base palette. " if evidence else
              "No hue-bearing genre or mood tags were available, so the palette uses a neutral slate base. ")
    if identity["method"] == "dominant_tag":
        origin += f"Conflicting hue votes nearly cancelled, so {identity['dominant_tag']} sets the base hue. "
        if identity["tie_break_used"]:
            origin += "The strongest weights are equal; the deterministic tie-break uses lowest hue, then tag name. "
    energy = "tempered saturation" if source == "artist" else "vivid saturation" if axes["energy"] >= 65 else "muted saturation" if axes["energy"] <= 35 else "balanced saturation"
    darkness = "deeper tones" if axes["darkness"] >= 60 else "lighter tones" if axes["darkness"] <= 40 else "mid-range lightness"
    dream = " High dreaminess softens supporting colors and narrows their hue spread without changing the primary hue." if axes["dreaminess"] >= 60 else ""
    tension = " Higher tension widens the accent contrast." if axes["tension"] >= 60 else " Low tension keeps the accent close and gentle." if axes["tension"] <= 40 else " Moderate tension adds a measured accent contrast."
    artist = " Artist fallback has 45% source influence, reducing saturation, accent contrast and confidence because artist-wide tags may not describe this track." if source == "artist" else ""
    return f"{origin}Energy sets {energy}, while darkness creates {darkness}. Warmth only makes a small hue adjustment.{dream}{tension}{artist}"


def analyze_tags(tags, source="track"):
    prepared = prepare_tags(tags)
    resolved = [(name, count, resolve_tag(name)) for name, count in prepared]
    used = [(name, count, match) for name, count, match in resolved if match][:12]
    source_weight = 0.45 if source == "artist" else 1.0
    evidence = [(name, count, match, math.sqrt(count) * match[2] * source_weight) for name, count, match in used]
    total = sum(weight for _, _, _, weight in evidence)
    axes = {
        axis: round((50 + sum(match[1][i] * weight for _, _, match, weight in evidence)) / (1 + total), 1)
        for i, axis in enumerate(AXES)
    }
    # Coverage describes interpreted tag weight independent of source. Apply
    # the source discount ONCE to confidence, not again through coverage.
    coverage = sum(math.sqrt(count) * match[2] for _, count, match in used) / sum(math.sqrt(count) for _, count in prepared) if prepared else 0
    confidence = round(clamp(100 * coverage * min(1, len(used) / 4) ** 0.5 * source_weight))
    contributions = [
        {"tag": name, "matched": match[0], "count": count, "share": round(weight / total * 100, 1),
         "match_quality": match[2], "axes": dict(zip(AXES, match[1])),
         "effective_weight": weight,
         "contribution": {axis: round(match[1][i] * weight / (1 + total), 2) for i, axis in enumerate(AXES)}}
        for name, count, match, weight in evidence
    ]
    identity = hue_identity(contributions)
    palette = palette_from_axes(axes, base_hue=identity["base_hue"], supporting_hue=identity["supporting_hue"], influence=source_weight if used else 0)
    identity["primary_hue"] = palette[0]["hsl"][0]
    notice = "Low confidence — limited mood tags were available." if confidence < 50 else None
    if source == "artist":
        notice = "Low confidence — limited mood tags were available. Artist fallback uses 45% source influence because artist-wide tags may not describe this track."
    dreamy = axes["dreaminess"] / 100
    stops = [f"{palette[4]['hex']} 0%", f"{palette[1]['hex']} {round(42 + 15 * dreamy)}%", f"{palette[0]['hex']} 100%"]
    return {
        "engine_version": "2.0", "axes": axes, "confidence": confidence,
        "source_weight": source_weight, "color_identity": identity,
        "coverage": round(coverage * 100, 1), "fallback": not used,
        "contributions": contributions, "keywords": mood_keywords(axes),
        "palette": palette, "gradient": "linear-gradient(125deg, " + ", ".join(stops) + ")",
        "explanation": explain(axes, not used, identity, source),
        "notice": notice,
    }
