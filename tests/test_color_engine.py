"""Generic metadata profiles, with no song/artist-name exceptions."""
import itertools
import re

import pytest

from app.services import color_engine
from app.services.mood_engine import analyze_tags, palette_from_axes
from app.services.tag_lexicon import HUE_PROFILES, LEXICON

PROFILES = {
    "heavy": ["rock", "alternative rock", "metal", "rap metal", "hard rock"],
    "artist_heavy": ["heavy metal", "glam metal", "k-rock", "pop", "folk metal", "hard rock"],
    "ambient": ["ambient", "dreamy", "ethereal", "atmospheric"],
    "folk": ["folk", "acoustic", "country", "singer-songwriter"],
    "electronic": ["electronic", "techno", "house", "trance"],
    "dream_pop": ["dream pop", "shoegaze", "dreamy"],
    "warm_dreamy": ["folk", "romantic", "dreamy", "mellow"],
}


def data(names):
    return [{"name": name, "count": 100} for name in names]


def distance(a, b):
    return abs((a - b + 180) % 360 - 180)


def test_circular_mean_wraps_at_red_instead_of_cyan():
    assert distance(color_engine.circular_mean([350, 10], [1, 1]), 0) < 0.001
    assert distance(color_engine.circular_mean([350, 10], [9, 1]), 350) < 3


def test_circular_mean_handles_opposition_without_order_bias():
    first = color_engine.circular_mean([0, 180], [1, 1])
    assert first in (0, 180)
    assert first == color_engine.circular_mean([180, 0], [1, 1])
    assert color_engine.circular_mean([], [], fallback=210) == 210


def test_every_lexicon_tag_has_an_explicit_hue_policy():
    assert set(HUE_PROFILES) == set(LEXICON)
    for name in LEXICON:
        result = analyze_tags(data([name]))
        assert len(result["palette"]) == 5
        assert all(re.fullmatch(r"#[0-9A-F]{6}", c["hex"]) for c in result["palette"])


@pytest.mark.parametrize("name", ["heavy", "artist_heavy"])
def test_heavy_tags_preserve_red_identity_instead_of_violet(name):
    result = analyze_tags(data(PROFILES[name]), source="artist" if name == "artist_heavy" else "track")
    primary, secondary = [c["hsl"][0] for c in result["palette"][:2]]
    assert distance(primary, 5) < 35
    assert distance(secondary, 20) < 45
    assert result["palette"][4]["hsl"][2] < 12


def test_ambient_is_cool_soft_and_low_energy():
    result = analyze_tags(data(PROFILES["ambient"]))
    assert 175 <= result["palette"][0]["hsl"][0] <= 240
    assert result["palette"][0]["hsl"][1] < 40
    assert result["palette"][3]["hsl"][1] < 20
    assert result["palette"][3]["hsl"][2] > result["palette"][0]["hsl"][2]


def test_folk_is_earthy_and_electronic_is_cyan_blue():
    folk = analyze_tags(data(PROFILES["folk"]))
    electronic = analyze_tags(data(PROFILES["electronic"]))
    assert 25 <= folk["palette"][0]["hsl"][0] <= 90
    assert 175 <= electronic["palette"][0]["hsl"][0] <= 240
    assert electronic["palette"][0]["hsl"][1] > folk["palette"][0]["hsl"][1]


def test_distinct_musical_identities_do_not_collapse_to_one_primary():
    hues = [analyze_tags(data(PROFILES[name]))["palette"][0]["hsl"][0] for name in ("heavy", "folk", "electronic", "dream_pop")]
    assert all(distance(a, b) >= 35 for a, b in itertools.combinations(hues, 2))


def test_warm_dreamy_profile_keeps_peach_gold_identity():
    result = analyze_tags(data(PROFILES["warm_dreamy"]))
    assert 0 <= result["palette"][0]["hsl"][0] <= 90
    assert 0 <= result["palette"][3]["hsl"][0] <= 90


def test_dreaminess_changes_softness_and_spread_without_rotating_primary():
    axes = dict(energy=50, warmth=50, dreaminess=0, darkness=50, tension=50)
    grounded = palette_from_axes(axes, base_hue=30, supporting_hue=65)
    dreamy = palette_from_axes(axes | {"dreaminess": 100}, base_hue=30, supporting_hue=65)
    assert grounded[0]["hsl"][0] == dreamy[0]["hsl"][0]
    assert dreamy[3]["hsl"][1] < grounded[3]["hsl"][1]
    assert distance(dreamy[0]["hsl"][0], dreamy[1]["hsl"][0]) < distance(grounded[0]["hsl"][0], grounded[1]["hsl"][0])


@pytest.mark.parametrize("names", list(PROFILES.values()))
def test_profiles_are_deterministic_diverse_valid_and_readable(names):
    result = analyze_tags(data(names))
    assert result == analyze_tags(list(reversed(data(names))))
    hues = [c["hsl"][0] for c in result["palette"]]
    meaningful = [f for f in result["genre_families"] if f["meaningful"]]
    if len(meaningful) > 1:
        assert max(distance(a, b) for a, b in itertools.combinations(hues, 2)) > 20
    elif result["axes"]["energy"] < 60 and result["axes"]["tension"] < 60:
        # v3 preserves single-family music instead of forcing v2's minimum
        # spread even when all tags describe the same quiet/dream identity.
        assert max(distance(a, b) for a, b in itertools.combinations(hues[:3], 2)) <= 30
    for color in result["palette"]:
        assert re.fullmatch(r"#[0-9A-F]{6}", color["hex"])
        rgb = [int(color["hex"][i:i+2], 16) / 255 for i in (1, 3, 5)]
        linear = [v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4 for v in rgb]
        luma = sum(v * w for v, w in zip(linear, [0.2126, 0.7152, 0.0722]))
        text = 1 if color["text"] == "#FFFFFF" else 0
        assert (max(luma, text) + 0.05) / (min(luma, text) + 0.05) >= 4.5


def test_artist_source_reduces_real_influence_and_confidence():
    tags = data(PROFILES["heavy"])
    track, artist = analyze_tags(tags), analyze_tags(tags, source="artist")
    assert artist["source_weight"] == 0.45
    assert artist["confidence"] == round(track["confidence"] * 0.45)
    assert artist["contributions"][0]["effective_weight"] == pytest.approx(track["contributions"][0]["effective_weight"] * 0.45)
    assert abs(artist["axes"]["energy"] - 50) < abs(track["axes"]["energy"] - 50)
    assert artist["palette"][0]["hsl"][1] < track["palette"][0]["hsl"][1]
    assert distance(artist["palette"][0]["hsl"][0], track["palette"][0]["hsl"][0]) < 2
    assert "Artist" in artist["notice"]


def test_artist_scaling_cannot_flip_an_ambiguous_genre_identity():
    # sqrt(100)*0.3 == sqrt(9)*1 == 3. Scaling by 0.45 used to turn
    # this exact tie into 1.3499999999999999 vs 1.35 and flip 177 degrees.
    tags = [{"name": "romantic", "count": 100}, {"name": "electronic", "count": 9}]
    track, artist = analyze_tags(tags), analyze_tags(tags, source="artist")
    assert track["color_identity"]["base_hue"] == 18
    assert artist["color_identity"]["base_hue"] == track["color_identity"]["base_hue"]
    assert distance(track["palette"][0]["hsl"][0], artist["palette"][0]["hsl"][0]) <= 8


def test_ambiguous_hue_explains_the_selected_tag_and_tie_break():
    result = analyze_tags(data(["ambient", "rock"]))
    identity = result["color_identity"]
    assert identity["method"] == "dominant_tag"
    assert identity["dominant_tag"] == "rock"
    assert identity["tie_break_used"] is True
    assert "rock" in result["explanation"] and "equal" in result["explanation"]


def test_hue_weights_follow_tag_counts_and_ignore_non_mood_tags():
    a = analyze_tags([{"name": "rock", "count": 100}, {"name": "electronic", "count": 4}])
    b = analyze_tags([{"name": "rock", "count": 4}, {"name": "electronic", "count": 100}])
    assert distance(a["color_identity"]["base_hue"], 12) < distance(b["color_identity"]["base_hue"], 12)
    assert analyze_tags(data(["rock", "korean", "90s", "seen live"])) == analyze_tags(data(["rock"]))


def test_explanation_names_actual_hue_evidence_and_not_warmth_as_cause():
    heavy = analyze_tags(data(PROFILES["heavy"]))
    assert "rock" in heavy["explanation"] and "metal" in heavy["explanation"]
    assert "crimson" in heavy["explanation"] or "red" in heavy["explanation"]
    assert "saturation" in heavy["explanation"] and "tension" in heavy["explanation"]
    assert heavy["color_identity"]["method"] == "weighted_circular_mean"
