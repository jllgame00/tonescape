"""Color math and property mapping; v2 global hue is retained as a diagnostic.

Production v3 composition is in palette_composition.py and aggregates musical
families separately. The global diagnostic below never drives its palette.

Primary/supporting anchors are editorial heuristics. Unit-circle means respect
the red seam; low-resultant mixtures use the strongest vote deterministically
instead of letting floating-point noise manufacture a new musical identity.
"""

import colorsys
import math

from app.services.tag_lexicon import AXES, HUE_PROFILES

NEUTRAL_HUE = 210
MIN_COHERENCE = 0.2


def clamp(value, low=0, high=100):
    return min(high, max(low, value))


def hue_distance(start, end):
    """Signed shortest arc, in [-180, 180)."""
    return (end - start + 180) % 360 - 180


def _circular_result(hues, weights, fallback=NEUTRAL_HUE):
    if len(hues) != len(weights):
        raise ValueError("Each hue needs one weight")
    samples = sorted((float(h) % 360, float(w)) for h, w in zip(hues, weights)
                     if math.isfinite(h) and math.isfinite(w) and w > 0)
    total = math.fsum(w for _, w in samples)
    if not total:
        return float(fallback) % 360, 0.0, "neutral_baseline"
    x = math.fsum(math.cos(math.radians(h)) * w for h, w in samples)
    y = math.fsum(math.sin(math.radians(h)) * w for h, w in samples)
    coherence = min(1.0, math.hypot(x, y) / total)
    if coherence < MIN_COHERENCE:
        # Greatest weight, then lowest normalized hue on a tie. Sorting and fsum
        # give identical output even when Last.fm sends tags in another order.
        hue = min(samples, key=lambda item: (-item[1], item[0]))[0]
        return hue, coherence, "dominant_tag"
    return math.degrees(math.atan2(y, x)) % 360, coherence, "weighted_circular_mean"


def circular_mean(hues, weights, fallback=NEUTRAL_HUE):
    hue, _, _ = _circular_result(hues, weights, fallback)
    return round(hue, 6) % 360


def hue_identity(contributions):
    votes = []
    for item in contributions:
        profile = HUE_PROFILES[item["matched"]]
        # Source scaling mathematically cancels in a circular mean, but applying
        # 0.45 before a near-antipodal tie can introduce unequal float roundoff.
        # Aggregate source-independent hue votes, then temper color properties
        # with source influence separately. This preserves genre identity exactly.
        weight = math.sqrt(item["count"]) * item["match_quality"] * profile.influence
        if weight > 0:
            votes.append({"tag": item["tag"], "matched": item["matched"], "hue": profile.primary,
                          "supporting_hue": profile.supporting, "family": profile.family, "weight": weight})
    weights = [v["weight"] for v in votes]
    base, coherence, method = _circular_result([v["hue"] for v in votes], weights)
    supporting, _, _ = _circular_result([v["supporting_hue"] for v in votes], weights, fallback=base + 25)
    total = math.fsum(weights)
    dominant = min(votes, key=lambda vote: (-vote["weight"], vote["hue"], vote["tag"])) if votes else None
    return {"base_hue": round(base, 3) % 360, "supporting_hue": round(supporting, 3) % 360,
            "coherence": round(coherence, 4), "method": method,
            "dominant_tag": dominant["tag"] if method == "dominant_tag" else None,
            "tie_break_used": bool(method == "dominant_tag" and sum(v["weight"] == dominant["weight"] for v in votes) > 1),
            "tags": [v | {"share": round(v["weight"] / total * 100, 1)} for v in votes]}


def contrast_text(rgb):
    linear = [v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4 for v in rgb]
    light = sum(v * c for v, c in zip(linear, (0.2126, 0.7152, 0.0722)))
    return "#FFFFFF" if 1.05 / (light + 0.05) > (light + 0.05) / 0.05 else "#000000"


def palette_from_axes(axes, base_hue=NEUTRAL_HUE, supporting_hue=None, influence=1.0):
    e, w, d, k, t = (clamp(float(axes.get(a, 50))) / 100 for a in AXES)
    influence = clamp(influence, 0, 1)
    # Warmth nudges the already chosen identity by <=8 degrees, never replaces
    # it. Dreaminess does not rotate the primary hue at all.
    target = 40 if w >= 0.5 else 220
    delta = hue_distance(base_hue, target)
    adjustment = math.copysign(min(abs(delta), 8 * abs(2 * w - 1) * influence), delta)
    hue = (base_hue + adjustment) % 360
    support_delta = hue_distance(base_hue, supporting_hue if supporting_hue is not None else base_hue + 35)
    direction = -1 if support_delta < 0 else 1
    secondary_spread = clamp(abs(support_delta), 24, 85) * (1 - 0.6 * d)
    # Artist-only metadata is weaker evidence. Scaling all weights alone would
    # CANCEL in a mean: explicitly temper chroma and accent contrast as well.
    saturation = 12 + influence * (12 + 56 * e) * (1 - 0.12 * d)
    lightness = 68 - 37 * k
    accent_spread = (20 + 65 * t + 8 * e) * (1 - 0.35 * d) * (0.55 + 0.45 * influence)
    specs = [
        ("Primary", hue, saturation, lightness),
        ("Secondary", hue + direction * secondary_spread, saturation * 0.86 * (1 - 0.15 * d), lightness - 6 + 3 * d),
        ("Accent", hue + direction * accent_spread, saturation + 8 * influence, lightness + 6 + 10 * t * influence),
        ("Soft", hue + direction * (12 + 16 * d), saturation * 0.38 * (1 - 0.45 * d), lightness + 20 + 7 * d),
        ("Background", hue - direction * 6, saturation * 0.2 * (1 - 0.5 * k), 14 - 9 * k),
    ]
    palette = []
    for label, h, s, l in specs:
        h = round(h % 360, 1) % 360
        s = round(clamp(s, 2 if label == "Background" else 4, 88), 1)
        l = round(clamp(l, 5, 90), 1)
        rgb = colorsys.hls_to_rgb(h / 360, l / 100, s / 100)
        value = "#" + "".join(f"{round(v * 255):02X}" for v in rgb)
        quantized = tuple(int(value[i:i+2], 16) / 255 for i in (1, 3, 5))
        palette.append({"label": label, "hex": value, "hsl": [h, s, l], "text": contrast_text(quantized)})
    return palette


def hue_name(hue):
    for boundary, name in [(20, "burnt red"), (45, "burnt orange"), (70, "gold and ochre"),
                           (100, "olive"), (160, "green"), (195, "cyan"), (235, "blue"),
                           (285, "lavender and violet"), (345, "rose and magenta"), (360, "crimson")]:
        if hue % 360 < boundary:
            return name
