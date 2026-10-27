"""Preserve weighted musical families as independent palette anchors (v3)."""
import math

from app.services.color_engine import (
    NEUTRAL_HUE, circular_mean, contrast_text, hue_distance, palette_from_axes,
)
from app.services.genre_families import FAMILIES
from app.services.tag_lexicon import HUE_PROFILES
import colorsys

MIN_FAMILY_SHARE = 0.04
STRONG_FAMILY_SHARE = 0.15
ROLE_SEPARATION = 30.0
MAX_COMPOSITION_NUDGE = ROLE_SEPARATION / 2


def genre_families(contributions):
    grouped = {}
    for item in contributions:
        profile = HUE_PROFILES[item["matched"]]
        # As in v2, source-independent votes avoid source-scaling roundoff
        # changing the winner. Source influence affects confidence/properties.
        weight = math.sqrt(item["count"]) * item["match_quality"] * profile.influence
        if weight <= 0:
            continue
        for vote in profile.genre_families:
            spec = FAMILIES[vote.family]
            grouped.setdefault(vote.family, []).append((weight * vote.share, spec.hues[0], item["tag"]))
    total = math.fsum(w for votes in grouped.values() for w, _, _ in votes)
    if not total:
        return []
    result = []
    for family, votes in grouped.items():
        score = math.fsum(w for w, _, _ in votes)
        spec = FAMILIES[family]
        # Circular means are local to one identity, never across all families.
        hue = circular_mean([h for _, h, _ in votes], [w for w, _, _ in votes])
        result.append({"family": family, "label": spec.label, "score": score,
                       "share": round(score / total * 100, 4), "hues": [hue, *spec.hues[1:]],
                       "tags": sorted({tag for _, _, tag in votes})})
    result.sort(key=lambda family: (-family["score"], family["hues"][0], family["family"]))
    # A minor hybrid influence may be a valid accent even when one family has
    # many related tags. A second cutoff relative to the leader would erase it.
    threshold = MIN_FAMILY_SHARE
    for family in result:
        family["meaningful"] = family["score"] / total >= threshold
        family["strong"] = family["score"] / total >= STRONG_FAMILY_SHARE
    return result


def _distance(a, b):
    return abs(hue_distance(a, b))


def _separate(hue, existing):
    """Nearest feasible point; only a half-gap nudge around a real anchor."""
    candidates = [hue % 360] + [(other + sign * ROLE_SEPARATION) % 360
                               for other in existing for sign in (-1, 1)]
    valid = [h for h in candidates if _distance(hue, h) <= MAX_COMPOSITION_NUDGE + 1e-8
             and all(_distance(h, other) >= ROLE_SEPARATION - 1e-8 for other in existing)]
    return min(valid, key=lambda h: (_distance(hue, h), h)) if valid else None


def _role(family, hue, anchor=None, source="genre_family"):
    return {"family": family["family"], "label": family["label"], "hue": hue % 360,
            "anchor_hue": hue % 360 if anchor is None else anchor % 360, "source": source}


def _choices(family, existing):
    # Try actual declared anchor endpoints before moving a nearby identity.
    for hue in family["hues"]:
        if all(_distance(hue, other) >= ROLE_SEPARATION - 1e-8 for other in existing):
            yield _role(family, hue)
    for hue in family["hues"]:
        separated = _separate(hue, existing)
        if separated is not None:
            if _distance(hue, separated) > 1e-8:
                yield _role(family, separated, anchor=hue)


def _select(family, existing):
    return next(_choices(family, existing), None)


def _select_mixture(primary, meaningful):
    # Search secondary endpoints jointly with the third family. A greedy first
    # endpoint can block a third identity even when another supported layout
    # exists. Family rank takes precedence over endpoint preference.
    for secondary_family in meaningful[1:]:
        for accent_family in meaningful[1:]:
            if accent_family["family"] == secondary_family["family"]:
                continue
            for secondary in _choices(secondary_family, [primary["hue"]]):
                accent = _select(accent_family, [primary["hue"], secondary["hue"]])
                if accent:
                    return secondary, accent
    secondary = next((choice for family in meaningful[1:]
                      if (choice := _select(family, [primary["hue"]])) is not None), None)
    return secondary, None


def _warm(hue, warmth, influence):
    w = warmth / 100
    delta = hue_distance(hue, 40 if w >= 0.5 else 220)
    return (hue + math.copysign(min(abs(delta), 8 * abs(2*w - 1) * influence), delta)) % 360


def _realize(roles, warmth, influence):
    # If opposing warmth corrections consume the diversity gap, reduce them.
    # Family identity/diversity takes priority over an optional mood nudge.
    for correction in (1.0, 0.5, 0.0):
        actual = []
        for index, role in enumerate(roles):
            hue = _warm(role["anchor_hue"], warmth, influence * correction)
            distinct = role["source"] in ("genre_family", "family_contrast")
            if index and distinct:
                hue = _separate(hue, actual)
                if hue is None:
                    break
            actual.append(hue)
        if len(actual) == len(roles):
            return actual
    raise ValueError("Declared family anchors could not satisfy the composition")


def _accent(primary, secondary, meaningful, axes):
    existing = [primary["hue"], secondary["hue"]]
    occupied = {primary["family"], secondary["family"]}
    for family in meaningful:
        if family["family"] not in occupied:
            choice = _select(family, existing)
            if choice:
                return choice
    e, t, d = (axes[name] / 100 for name in ("energy", "tension", "dreaminess"))
    # Energetic/tense single-family music may use a DECLARED contrasting hue;
    # quiet single-family music stays tonal rather than receiving a rainbow.
    if max(e, t) >= 0.6:
        candidates = []
        for family in meaningful:
            for hue in family["hues"][1:]:
                chosen = _separate(hue, existing)
                if chosen is not None:
                    desired = 30 + 70 * t
                    candidates.append((abs(_distance(existing[0], chosen) - desired), -family["score"],
                                       chosen, family["family"], _role(family, chosen, hue, "family_contrast")))
        if candidates:
            return min(candidates, key=lambda c: c[:4])[-1]
    direction = -1 if hue_distance(primary["hue"], secondary["hue"]) < 0 else 1
    blend = circular_mean(existing, [0.6, 0.4])
    spread = (10 * e + 25 * t) * (1 - 0.6 * d)
    return {"family": primary["family"], "label": primary["label"],
            "hue": (blend + direction * spread) % 360,
            "anchor_hue": (blend + direction * spread) % 360, "source": "tonal"}


def _recolor(color, hue):
    h, s, l = round(hue % 360, 1) % 360, color["hsl"][1], color["hsl"][2]
    rgb = colorsys.hls_to_rgb(h/360, l/100, s/100)
    value = "#" + "".join(f"{round(v*255):02X}" for v in rgb)
    quantized = tuple(int(value[i:i+2], 16)/255 for i in (1, 3, 5))
    return color | {"hex": value, "hsl": [h, s, l], "text": contrast_text(quantized)}


def compose_palette(axes, families, influence=1.0, selection_axes=None):
    if not families:
        palette = palette_from_axes(axes, base_hue=NEUTRAL_HUE, supporting_hue=NEUTRAL_HUE + 25, influence=influence)
        anchors = {color["label"]: {"family": None, "source": "neutral_baseline", "hue": color["hsl"][0]}
                   for color in palette}
        return palette, anchors
    meaningful = [family for family in families if family["meaningful"]]
    lead = meaningful[0]
    primary = _role(lead, lead["hues"][0])
    secondary, accent = _select_mixture(primary, meaningful)
    if secondary is None:
        delta = hue_distance(primary["hue"], lead["hues"][1])
        spread = min(abs(delta), 12 * (1 - 0.6 * axes["dreaminess"]/100))
        secondary = _role(lead, primary["hue"] + math.copysign(spread, delta), source="tonal")
    accent = accent or _accent(primary, secondary, meaningful, selection_axes or axes)
    roles = [primary, secondary, accent]
    actual = _realize(roles, axes["warmth"], influence)
    # Reuse the tested property mapping (saturation/lightness), but every
    # chromatic hue is independently selected above. No global mean is input.
    palette = palette_from_axes(axes, base_hue=primary["hue"], supporting_hue=secondary["hue"], influence=influence)
    actual.extend([circular_mean(actual[:2], [0.6, 0.4]), actual[0]])
    palette = [_recolor(color, hue) for color, hue in zip(palette, actual)]
    anchors = {label: role | {"hue": palette[index]["hsl"][0],
                              "composition_adjustment": round(hue_distance(_warm(role["anchor_hue"], axes["warmth"], influence), actual[index]), 3)}
               for index, (label, role) in enumerate(zip(("Primary", "Secondary", "Accent"), roles))}
    anchors["Soft"] = {"family": None, "source": "primary_secondary_blend", "hue": palette[3]["hsl"][0]}
    anchors["Background"] = {"family": primary["family"], "source": "dominant_tint", "hue": palette[4]["hsl"][0]}
    return palette, anchors
