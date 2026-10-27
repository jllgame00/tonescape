"""Generic musical mixtures; no song names or exact preferred HEX values."""
import itertools
import json
from pathlib import Path
import re

import pytest

from app.services.mood_engine import analyze_tags
from app.services.genre_families import FAMILIES, TAG_FAMILIES
from app.services.tag_lexicon import HUE_PROFILES, LEXICON

PROFILES = json.loads((Path(__file__).parent / "fixtures/genre_profiles.json").read_text(encoding="utf-8"))


def result(name):
    case = PROFILES[name]
    return analyze_tags(case["tags"], source=case["source"])


def dist(a, b):
    return abs((a - b + 180) % 360 - 180)


def hues(analysis):
    return [c["hsl"][0] for c in analysis["palette"][:3]]


def test_all_lexicon_entries_have_complete_conserved_family_policies():
    assert set(TAG_FAMILIES) == set(LEXICON) == set(HUE_PROFILES)
    for tag, profile in HUE_PROFILES.items():
        if profile.genre_families:
            assert sum(v.share for v in profile.genre_families) == pytest.approx(1)
            assert all(v.family in FAMILIES and v.share > 0 for v in profile.genre_families)
        else:
            assert profile.influence == 0


def test_composite_family_matching_retains_quality_discount():
    direct = analyze_tags([{"name":"synth funk", "count":100}])
    related = analyze_tags([{"name":"synth funk live mix", "count":100}])
    assert {f["family"]:f["share"] for f in direct["genre_families"]} == {"funk":60, "electronic":40}
    assert sum(f["score"] for f in direct["genre_families"]) == pytest.approx(10)
    assert sum(f["score"] for f in related["genre_families"]) == pytest.approx(6)
    assert related["confidence"] < direct["confidence"]


def test_soul_funk_psychedelic_mixture_retains_warm_gold_and_cool_roles():
    analysis = result("soul_funk")
    p, s, a = hues(analysis)
    assert dist(p, 350) <= 25
    assert 35 <= s <= 100
    assert 160 <= a <= 290
    assert dist(p, s) >= 30 and dist(p, a) >= 30


def test_soul_funk_and_heavy_mixtures_have_different_compositions():
    soul, heavy = result("soul_funk"), result("heavy")
    assert sum(dist(a, b) for a, b in zip(hues(soul), hues(heavy))) > 100
    assert dist(hues(heavy)[0], 5) < 30
    assert heavy["palette"][4]["hsl"][2] < 12
    assert heavy["axes"]["energy"] > soul["axes"]["energy"]


def test_family_scores_split_hybrid_tags_without_double_counting():
    analysis = analyze_tags([{"name":"psychedelic soul", "count":100}])
    families = {f["family"]: f for f in analysis.get("genre_families", [])}
    assert set(families) == {"soul", "psychedelic"}
    assert families["soul"]["share"] == pytest.approx(55)
    assert families["psychedelic"]["share"] == pytest.approx(45)
    assert sum(f["score"] for f in families.values()) == pytest.approx(10)


def test_family_scores_use_sqrt_counts_and_retain_minor_supported_anchors():
    analysis = analyze_tags([{"name":"jazz", "count":100}, {"name":"ambient", "count":25}])
    families = {f["family"]: f for f in analysis.get("genre_families", [])}
    assert set(families) == {"jazz", "ambient"}
    assert families["jazz"]["share"] == pytest.approx(66.6667, abs=0.01)
    assert families["ambient"]["share"] == pytest.approx(33.3333, abs=0.01)


@pytest.mark.parametrize("names", [("rock","metal"), ("rock","pop"), ("soul","funk"), ("jazz","ambient")])
def test_two_strong_families_have_distinct_primary_secondary(names):
    analysis = analyze_tags([{"name":n,"count":100} for n in names])
    assert dist(*hues(analysis)[:2]) >= 29.9
    anchors = analysis.get("palette_anchors", {})
    assert anchors.get("Primary", {}).get("family") != anchors.get("Secondary", {}).get("family")


def test_third_distinct_family_supplies_the_accent():
    analysis = analyze_tags([{"name":n,"count":100} for n in ("soul","funk","electronic")])
    anchors = analysis.get("palette_anchors", {})
    assert len({anchors.get(role, {}).get("family") for role in ("Primary","Secondary","Accent")}) == 3
    assert dist(hues(analysis)[0], hues(analysis)[2]) >= 30
    assert anchors["Accent"]["source"] == "genre_family"


def test_secondary_alternatives_are_considered_before_dropping_a_third_family():
    # Greedy Soul=15 blocks Metal, but Soul=45 permits Metal near its18 anchor.
    analysis = analyze_tags([{"name":name,"count":100} for name in ("jazz","soul","metal")])
    anchors = analysis["palette_anchors"]
    assert {anchors[role]["family"] for role in ("Primary","Secondary","Accent")} == {"jazz","soul","metal"}
    assert anchors["Accent"]["source"] == "genre_family"
    assert all(dist(a,b) >= 29.9 for a,b in itertools.combinations(hues(analysis),2))


def test_source_discount_changes_properties_without_switching_contrast_identity():
    tags = [{"name":"rock","count":10}, {"name":"techno","count":10}]
    track, artist = analyze_tags(tags), analyze_tags(tags, source="artist")
    for role in ("Primary","Secondary","Accent"):
        assert track["palette_anchors"][role]["family"] == artist["palette_anchors"][role]["family"]
        assert track["palette_anchors"][role]["anchor_hue"] == artist["palette_anchors"][role]["anchor_hue"]


def test_tiny_unrelated_family_does_not_hijack_a_role():
    analysis = analyze_tags([{"name":"folk","count":100}, {"name":"metal","count":0.001}])
    anchors = analysis.get("palette_anchors", {})
    assert anchors
    assert all(anchors[role].get("family") != "metal" for role in ("Primary","Secondary","Accent"))


def test_ambient_dream_allows_an_analogous_cool_composition():
    analysis = result("ambient_dream")
    assert all(175 <= h <= 270 for h in hues(analysis))
    assert max(dist(a,b) for a,b in itertools.combinations(hues(analysis),2)) <= 75
    assert analysis["palette"][0]["hsl"][1] < 40
    assert analysis["palette"][3]["hsl"][1] < 20


def test_folk_and_electronic_keep_their_tonal_properties():
    folk, electronic = result("folk"), result("electronic")
    assert all(35 <= h <= 95 for h in hues(folk))
    assert 180 <= hues(electronic)[0] <= 235
    assert electronic["palette"][0]["hsl"][1] > 55
    assert electronic["palette"][0]["hsl"][1] > folk["palette"][0]["hsl"][1]


def test_jazz_swing_is_burgundy_amber_and_restrained():
    jazz, heavy = result("jazz_swing"), result("heavy")
    assert dist(hues(jazz)[0], 345) <= 25
    assert 25 <= hues(jazz)[1] <= 65
    assert jazz["palette"][0]["hsl"][1] < heavy["palette"][0]["hsl"][1]
    assert jazz["palette"][4]["hsl"][2] > heavy["palette"][4]["hsl"][2]


@pytest.mark.parametrize("name", ["folk", "ambient"])
def test_low_tension_single_family_does_not_get_forced_rainbow(name):
    analysis = analyze_tags([{"name":name,"count":100}])
    assert len(analysis.get("genre_families", [])) == 1
    assert max(dist(a,b) for a,b in itertools.combinations(hues(analysis),2)) <= 25


def test_artist_preserves_distribution_and_role_identity_with_lower_influence():
    data = PROFILES["artist_heavy"]["tags"]
    track, artist = analyze_tags(data), analyze_tags(data, source="artist")
    assert artist.get("genre_families") == track.get("genre_families") and artist.get("genre_families")
    assert artist["source_weight"] == 0.45 and artist["confidence"] <= 45
    for role in ("Primary","Secondary","Accent"):
        assert artist["palette_anchors"][role]["family"] == track["palette_anchors"][role]["family"]
    assert artist["palette"][0]["hsl"][1] < track["palette"][0]["hsl"][1]


def test_family_explanation_describes_each_actual_role():
    analysis = result("soul_funk")
    text = analysis["explanation"].lower()
    assert all(word in text for word in ("soul", "funk", "psychedelic", "primary", "secondary", "accent"))


def test_no_evidence_keeps_neutral_without_inventing_families():
    analysis = result("neutral")
    assert analysis.get("genre_families") == []
    assert analysis["fallback"] and analysis["confidence"] == 0
    assert all(c["hsl"][1] <= 12 for c in analysis["palette"])


@pytest.mark.parametrize("name", list(PROFILES))
def test_generic_profiles_are_deterministic_valid_readable_and_accounted_for(name):
    case = PROFILES[name]
    analysis = result(name)
    assert analysis == analyze_tags(list(reversed(case["tags"])), source=case["source"])
    families = analysis.get("genre_families", [])
    if name != "neutral":
        assert families and sum(f["share"] for f in families) == pytest.approx(100, abs=0.01)
    for color in analysis["palette"]:
        assert re.fullmatch(r"#[0-9A-F]{6}", color["hex"])
        rgb = [int(color["hex"][i:i+2],16)/255 for i in (1,3,5)]
        linear = [v/12.92 if v<=0.04045 else ((v+0.055)/1.055)**2.4 for v in rgb]
        luma = sum(x*y for x,y in zip(linear,(0.2126,0.7152,0.0722)))
        foreground = 1 if color["text"] == "#FFFFFF" else 0
        assert (max(luma,foreground)+0.05)/(min(luma,foreground)+0.05) >= 4.5
