"""Pure deterministic tag -> mood -> HSL engine (version 1).

Counts are sqrt-scaled to reduce popular-tag dominance. A single neutral
pseudoweight regularizes sparse evidence without introducing randomness.
Canonical sorting and deduplication make results independent of input order.
"""

import colorsys
import math
import re
import unicodedata

from app.services.tag_lexicon import ALIASES, AXES, IGNORED, LEXICON


def clamp(value, low=0, high=100):
    return min(high, max(low, value))


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


def contrast_text(rgb):
    def luminance(values):
        linear = [v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4 for v in values]
        return sum(v * c for v, c in zip(linear, (0.2126, 0.7152, 0.0722)))
    light = luminance(rgb)
    # Pure black/white guarantees at least 4.5:1 for normal-size HEX labels.
    return "#FFFFFF" if 1.05 / (light + 0.05) > (light + 0.05) / 0.05 else "#000000"


def palette_from_axes(axes):
    e, w, d, k, t = (clamp(float(axes.get(a, 50))) / 100 for a in AXES)
    # A continuous circular path: cyan -> violet -> magenta -> amber.
    hue = (220 + 180 * w) % 360
    # Dreaminess nudges toward lavender along the shortest arc. Warmth reduces
    # this nudge, preserving warm dreamy tracks instead of painting all blue.
    blend = 0.24 * d * (1 - 0.65 * w)
    hue = (hue + ((275 - hue + 180) % 360 - 180) * blend) % 360
    saturation = 27 + 51 * e
    lightness = 67 - 34 * k
    spread = 12 + 122 * t
    specs = [
        ("Primary", hue, saturation, lightness),
        ("Secondary", hue + 13 + 20 * (1 - d), saturation - 8 - 10 * d, lightness - 7),
        ("Accent", hue - spread, saturation + 7, lightness + 7 + 8 * t),
        ("Soft", hue + 10, saturation * (0.58 - 0.15 * d), lightness + 17 + 4 * d),
        ("Background", hue - 8, saturation * 0.35, 16 - 7 * k),
    ]
    palette = []
    for label, h, s, l in specs:
        h, s, l = round(h % 360, 1), round(clamp(s, 10, 88), 1), round(clamp(l, 8, 88), 1)
        rgb = colorsys.hls_to_rgb(h / 360, l / 100, s / 100)
        hex_value = "#" + "".join(f"{round(v * 255):02X}" for v in rgb)
        # Use quantized RGB for the contrast comparison, matching the HEX.
        quantized = tuple(int(hex_value[i:i + 2], 16) / 255 for i in (1, 3, 5))
        palette.append({"label": label, "hex": hex_value, "hsl": [h, s, l], "text": contrast_text(quantized)})
    return palette


def mood_keywords(axes):
    pairs = [
        ("dreaminess", "Dreamy", "Grounded"), ("energy", "Energetic", "Calm"),
        ("warmth", "Warm", "Cool"), ("darkness", "Dark", "Bright"),
        ("tension", "Tense", "Soft"),
    ]
    ranked = sorted(enumerate(pairs), key=lambda p: (-abs(axes[p[1][0]] - 50), p[0]))
    words = [high if axes[axis] >= 50 else low for _, (axis, high, low) in ranked[:4]]
    return words if any(abs(v - 50) > 8 for v in axes.values()) else ["Balanced", "Soft", "Understated"]


def explain(axes, fallback):
    if fallback:
        return "Too few interpretable mood tags were available. A neutral baseline creates this balanced palette; it does not describe the song's sound."
    warmth = "Warm hues" if axes["warmth"] >= 60 else "Cool hues" if axes["warmth"] <= 40 else "Violet and transitional hues"
    energy = "vivid saturation" if axes["energy"] >= 65 else "muted saturation" if axes["energy"] <= 35 else "balanced saturation"
    darkness = "deeper tones" if axes["darkness"] >= 60 else "lighter tones" if axes["darkness"] <= 40 else "mid-range lightness"
    dream = " A lavender undertone and softer secondary colors reflect the dreamy tags." if axes["dreaminess"] >= 60 else ""
    tension = " A contrasting accent reflects higher tension." if axes["tension"] >= 60 else " Closely related accent hues keep the palette gentle." if axes["tension"] <= 40 else " The accent adds moderate contrast."
    return f"{warmth} follow the warmth score, while energy sets {energy} and darkness creates {darkness}.{dream}{tension}"


def analyze_tags(tags, source="track"):
    prepared = prepare_tags(tags)
    resolved = [(name, count, resolve_tag(name)) for name, count in prepared]
    used = [(name, count, match) for name, count, match in resolved if match][:12]
    evidence = [(name, count, match, math.sqrt(count) * match[2]) for name, count, match in used]
    total = sum(weight for _, _, _, weight in evidence)
    axes = {
        axis: round((50 + sum(match[1][i] * weight for _, _, match, weight in evidence)) / (1 + total), 1)
        for i, axis in enumerate(AXES)
    }
    coverage = total / sum(math.sqrt(count) for _, count in prepared) if prepared else 0
    confidence = round(clamp(100 * coverage * min(1, len(used) / 4) ** 0.5 * (0.7 if source == "artist" else 1)))
    contributions = [
        {"tag": name, "matched": match[0], "count": count, "share": round(weight / total * 100, 1),
         "match_quality": match[2], "axes": dict(zip(AXES, match[1])),
         "contribution": {axis: round(match[1][i] * weight / (1 + total), 2) for i, axis in enumerate(AXES)}}
        for name, count, match, weight in evidence
    ]
    palette = palette_from_axes(axes)
    dreamy = axes["dreaminess"] / 100
    stops = [f"{palette[4]['hex']} 0%", f"{palette[1]['hex']} {round(42 + 15 * dreamy)}%", f"{palette[0]['hex']} 100%"]
    return {
        "engine_version": "1.0", "axes": axes, "confidence": confidence,
        "coverage": round(coverage * 100, 1), "fallback": not used,
        "contributions": contributions, "keywords": mood_keywords(axes),
        "palette": palette, "gradient": "linear-gradient(125deg, " + ", ".join(stops) + ")",
        "explanation": explain(axes, not used),
        "notice": "Low confidence — limited mood tags were available." if confidence < 50 else None,
    }
