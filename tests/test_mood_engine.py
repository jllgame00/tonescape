import re

import pytest

from app.services.mood_engine import analyze_tags, palette_from_axes


def tags(*names):
    return [{"name": name, "count": 100} for name in names]


def axes(**changes):
    return dict(energy=50, warmth=50, dreaminess=50, darkness=50, tension=50, **{}) | changes


def test_deterministic_including_input_order():
    data = [{"name": "rock", "count": 100}, {"name": "dreamy", "count": 36}]
    assert analyze_tags(data) == analyze_tags(list(reversed(data)))


@pytest.mark.parametrize("data", [[], tags("unknown123"), tags("metal", "dark"), tags("folk", "happy")])
def test_axes_and_hex_are_valid(data):
    result = analyze_tags(data)
    assert set(result["axes"]) == {"energy", "warmth", "dreaminess", "darkness", "tension"}
    assert all(0 <= value <= 100 for value in result["axes"].values())
    assert 0 <= result["confidence"] <= 100
    assert len(result["palette"]) == 5
    for color in result["palette"]:
        assert re.fullmatch(r"#[0-9A-F]{6}", color["hex"])
        assert color["text"] in ("#000000", "#FFFFFF")


def test_weighted_average_uses_sqrt_and_baseline():
    # metal energy=95, ambient=15. sqrt(100):sqrt(25)=2:1;
    # one baseline prior of energy=50 gives (950+75+50)/16=67.1875.
    result = analyze_tags([{"name": "metal", "count": 100}, {"name": "ambient", "count": 25}])
    assert result["axes"]["energy"] == pytest.approx(67.2, abs=0.1)
    assert sum(t["share"] for t in result["contributions"]) == pytest.approx(100, abs=0.2)


def test_energy_increases_saturation():
    high = palette_from_axes(axes(energy=90))
    low = palette_from_axes(axes(energy=10))
    assert all(h["hsl"][1] > l["hsl"][1] for h, l in zip(high, low))


def test_high_energy_tag_mix_is_more_saturated_than_low_energy_mix():
    high = analyze_tags(tags("punk", "energetic"))
    low = analyze_tags(tags("ambient", "calm"))
    assert high["axes"]["energy"] > low["axes"]["energy"]
    assert all(h["hsl"][1] > l["hsl"][1] for h, l in zip(high["palette"], low["palette"]))


def test_dark_tag_mix_is_darker_than_bright_mix():
    dark = analyze_tags(tags("metal", "dark"))
    bright = analyze_tags(tags("folk", "happy"))
    assert dark["axes"]["darkness"] > bright["axes"]["darkness"]
    assert all(d["hsl"][2] < b["hsl"][2] for d, b in zip(dark["palette"], bright["palette"]))


def test_non_mood_tags_do_not_change_analysis():
    assert analyze_tags(tags("rock", "korean", "female vocalists", "seen live")) == analyze_tags(tags("rock"))


def test_darkness_decreases_lightness():
    dark = palette_from_axes(axes(darkness=90))
    bright = palette_from_axes(axes(darkness=10))
    assert all(d["hsl"][2] < b["hsl"][2] for d, b in zip(dark, bright))


def test_warmth_moves_from_cool_blue_to_warm_orange():
    cool = palette_from_axes(axes(warmth=0, dreaminess=0))[0]["hsl"][0]
    warm = palette_from_axes(axes(warmth=100, dreaminess=0))[0]["hsl"][0]
    assert 190 <= cool <= 250
    assert 0 <= warm <= 65


def test_warm_dreamy_keeps_warm_identity():
    warm = palette_from_axes(axes(warmth=100, dreaminess=100))[0]["hsl"][0]
    assert warm < 80 or warm > 320


def test_tension_increases_accent_contrast():
    def distance(p):
        d = abs(p[0]["hsl"][0] - p[2]["hsl"][0])
        return min(d, 360 - d)
    assert distance(palette_from_axes(axes(tension=100))) > distance(palette_from_axes(axes(tension=0)))


def test_aliases_and_word_boundaries():
    assert analyze_tags(tags("  HIP-HOP! ")) == analyze_tags(tags("hip hop"))
    assert analyze_tags(tags("post_punk"))["axes"]["tension"] > 50
    assert analyze_tags(tags("dreamy indie music"))["confidence"] > 0
    assert analyze_tags(tags("poppyseed"))["confidence"] == 0


def test_unknown_and_empty_use_explicit_neutral_fallback():
    for data in ([], tags("my favourites", "unknown123", "korean", "seen live")):
        result = analyze_tags(data)
        assert result["fallback"] is True
        assert result["confidence"] == 0
        assert result["axes"] == axes()
        assert "limited mood tags" in result["notice"]


def test_confidence_rewards_coverage_count_and_track_source():
    rich = analyze_tags(tags("rock", "indie", "dreamy", "alternative"))
    partial = analyze_tags(tags("rock", "unknown123", "unmapped123"))
    single = analyze_tags(tags("rock"))
    artist = analyze_tags(tags("rock", "indie", "dreamy", "alternative"), source="artist")
    assert rich["confidence"] > single["confidence"] > partial["confidence"] > 0
    assert artist["confidence"] < rich["confidence"]


def test_invalid_and_zero_counts_never_create_evidence():
    data = [{"name": "rock", "count": value} for value in [0, -1, "nan", "inf", "oops", None]]
    assert analyze_tags(data)["confidence"] == 0


def test_duplicate_tags_do_not_inflate_confidence():
    assert analyze_tags(tags("rock", "ROCK")) == analyze_tags(tags("rock"))


@pytest.mark.parametrize("name", [["rock"], {"genre": "rock"}, None, 123, True])
def test_malformed_names_do_not_invent_mood_evidence(name):
    result = analyze_tags([{"name": name, "count": 100}])
    assert result["fallback"] is True
    assert result["confidence"] == 0


def test_swatch_text_meets_normal_text_contrast_on_quantized_hex():
    from itertools import product
    def luminance(hex_value):
        rgb = [int(hex_value[i:i + 2], 16) / 255 for i in (1, 3, 5)]
        linear = [x / 12.92 if x <= 0.04045 else ((x + 0.055) / 1.055) ** 2.4 for x in rgb]
        return sum(a * b for a, b in zip(linear, [0.2126, 0.7152, 0.0722]))
    cases = [analyze_tags(tags(name))["palette"] for name in ("punk", "ambient")]
    cases += [palette_from_axes(dict(zip(axes(), values))) for values in product((0, 50, 100), repeat=5)]
    for palette in cases:
        for color in palette:
            bg, fg = luminance(color["hex"]), luminance(color["text"])
            assert (max(bg, fg) + 0.05) / (min(bg, fg) + 0.05) >= 4.5
