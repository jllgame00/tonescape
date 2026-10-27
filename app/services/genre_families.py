"""Musical family membership and declared visual identities, not finished colors.

Hybrid shares conserve a tag's evidence. Related tags accumulate in one family;
different families are deliberately NOT collapsed into a global hue average.
"""
from typing import NamedTuple


class FamilyVote(NamedTuple):
    family: str
    share: float = 1.0


class FamilySpec(NamedTuple):
    label: str
    hues: tuple[float, ...]


FAMILIES = {
    "rock": FamilySpec("Rock", (12, 30, 65)),
    "metal": FamilySpec("Metal", (355, 18)),
    "punk": FamilySpec("Punk", (4, 65)),
    "rap": FamilySpec("Hip-hop / Rap", (50, 75, 275)),
    "soul": FamilySpec("Soul / R&B", (350, 15, 45)),
    "funk": FamilySpec("Funk / Disco", (50, 95, 285)),
    "psychedelic": FamilySpec("Psychedelic", (175, 280, 28)),
    "electronic": FamilySpec("Electronic / Synth", (205, 265, 185)),
    "jazz": FamilySpec("Jazz", (345, 42, 185)),
    "swing": FamilySpec("Swing", (42, 350)),
    "lounge": FamilySpec("Easy listening", (185, 42)),
    "ambient": FamilySpec("Ambient", (192, 210)),
    "dream": FamilySpec("Dream / Shoegaze", (250, 215)),
    "folk": FamilySpec("Folk / Acoustic", (65, 45, 80)),
    "pop": FamilySpec("Pop", (12, 215, 330)),
    "indie": FamilySpec("Indie", (210, 20)),
    "classical": FamilySpec("Classical / Orchestral", (225, 45)),
    "blues": FamilySpec("Blues", (220, 35)),
    "reggae": FamilySpec("Reggae", (100, 48)),
    "post_rock": FamilySpec("Post-rock", (215, 40)),
    "post_punk": FamilySpec("Post-punk", (205, 18)),
    "emo": FamilySpec("Emo", (350, 215)),
    "reflective": FamilySpec("Melancholic", (215, 245)),
    "experimental": FamilySpec("Experimental", (280, 170, 28)),
    "romantic": FamilySpec("Romantic / Ballad", (18, 345)),
}

# Every lexicon entry is explicitly assigned below. Empty membership means a
# property-only descriptor, not unknown data. HUE_PROFILES supplies influence.
TAG_FAMILIES = {
    tag: (FamilyVote(family),)
    for family, tags in {
        "rock": ("rock", "alternative rock", "hard rock", "classic rock", "progressive rock"),
        "metal": ("metal", "heavy metal", "death metal", "black metal"),
        "punk": ("punk",),
        "rap": ("hip hop", "rap"),
        "soul": ("soul", "rnb", "neo soul", "smooth soul"),
        "funk": ("funk", "disco", "p funk"),
        "electronic": ("electronic", "house", "techno", "trance", "drum and bass", "dance", "synth"),
        "psychedelic": ("psychedelic",),
        "jazz": ("jazz", "vocal jazz"),
        "swing": ("swing",),
        "lounge": ("easy listening",),
        "ambient": ("ambient", "atmospheric", "chill", "calm"),
        "dream": ("dream pop", "dreamy", "shoegaze", "ethereal"),
        "folk": ("folk", "acoustic", "singer songwriter", "country", "mellow"),
        "pop": ("pop", "happy"),
        "indie": ("indie",),
        "classical": ("classical", "orchestral"),
        "blues": ("blues",),
        "reggae": ("reggae",),
        "post_rock": ("post rock",),
        "post_punk": ("post punk",),
        "emo": ("emo",),
        "reflective": ("melancholic", "sad"),
        "experimental": ("experimental",),
        "romantic": ("romantic", "ballad"),
    }.items() for tag in tags
}
TAG_FAMILIES.update({
    "indie rock": (FamilyVote("rock", 0.5), FamilyVote("indie", 0.5)),
    "alternative": (FamilyVote("rock", 0.5), FamilyVote("indie", 0.5)),
    "psychedelic soul": (FamilyVote("soul", 0.55), FamilyVote("psychedelic", 0.45)),
    "synth funk": (FamilyVote("funk", 0.6), FamilyVote("electronic", 0.4)),
    "synthpop": (FamilyVote("pop", 0.45), FamilyVote("electronic", 0.55)),
    "synthwave": (FamilyVote("electronic", 0.7), FamilyVote("dream", 0.3)),
    "rap metal": (FamilyVote("metal", 0.55), FamilyVote("rap", 0.45)),
    "rapcore": (FamilyVote("rock", 0.5), FamilyVote("rap", 0.5)),
    "glam metal": (FamilyVote("metal", 0.5), FamilyVote("pop", 0.5)),
    "folk metal": (FamilyVote("metal", 0.65), FamilyVote("folk", 0.35)),
    "lo fi": (FamilyVote("folk", 0.5), FamilyVote("ambient", 0.5)),
    "trip hop": (FamilyVote("rap", 0.4), FamilyVote("electronic", 0.6)),
    "downtempo": (FamilyVote("ambient", 0.5), FamilyVote("electronic", 0.5)),
    "dark": (), "energetic": (), "instrumental": (),
})
