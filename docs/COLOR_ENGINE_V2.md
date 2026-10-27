# Color Engine v2 design and verification

## Problem and design

Version 1 computed hue as `220 + 180 * warmth` and pulled it toward 275 degrees
with dreaminess. Common warmth scores 30..60 therefore collapsed to violet and
magenta regardless of genre. Track names played no role and will continue not to.

Implement in place under HW2; preserve existing uncommitted/user changes and do
not create a worktree outside this directory, commit, push or change deployment.
The starting checkout was clean at `55d7779`, branch main.

1. Add explicit hue identities for every lexicon entry: primary anchor,
   supporting anchor, visual family and influence. Broad descriptors may carry
   zero/weak hue influence while still affecting axes. Genre aliases include
   k-rock, rapcore/rap metal, glam metal and folk metal; nationalities stay ignored.
2. Use sqrt(count) * match quality * hue influence for weighted unit-circle
   vectors. Resolve low-resultant/antipodal mixtures to the strongest tag, with
   deterministic tie-breaking, instead of unstable atan2 noise. No random hue.
3. Derive palette identity from those tags. Mood controls saturation, lightness,
   analogous spread and accent distance; warmth nudges by at most 8 degrees.
   Dreaminess does not rotate every genre toward lavender.
4. Artist evidence uses source weight 0.45 against the existing neutral axis
   prior and confidence. Uniform scaling cancels in a circular mean, so reduce
   palette saturation/contrast too, rather than claiming scaling alone changes
   hue. Retain musical hue identity and the existing artist fallback label.
5. Preserve response fields and role ordering; add color_identity metadata,
   update deterministic explanation/notice and documentation.

## Implementation plan (tests first)

- [x] Add generic regression tests for genre separation, circular wraparound,
  ambiguous mixtures, weights, source influence, warm/dreamy identity, palette
  diversity and all-profile readability. Update obsolete warmth-determines-hue
  assertions to the new bounded-adjustment contract. Run and observe RED.
- [x] Implement `app/services/color_engine.py`, lexicon hue profiles and mood
  integration. Run engine and full backend tests; retain existing unknown/empty,
  deterministic, range, HEX and backend fallback checks.
- [x] Update fallback explanation, README, report notes and before/after record.
  Obtain an independent review and verify findings with regressions as needed.

## Live comparison constraints

Both requested Last.fm calls were attempted with the configured key; both
returned the adapter's sanitized `network_error`. Do not print credentials or
upstream request URLs and do not bypass network restrictions. The supplied tag
lists are therefore compared with equal synthetic count=100 for every tag.
These are reproducible profile comparisons, not captures of deployed results.

Baseline: existing `.venv` suite passed **48 tests**, with one upstream
Starlette/httpx deprecation warning. Final results are recorded below after work.

## Before / after comparison

These are the user's tag lists with **equal synthetic count=100**, not live Last.fm
measurements. All five roles below are in Primary / Secondary / Accent / Soft /
Background order. Baseline was captured using the actual v1 code and lexicon
before any production edits; the same input is then run through v2.

| Reference case | Engine | Primary | Secondary | Accent | Soft | Background |
| --- | --- | --- | --- | --- | --- | --- |
| Rage Against the Machine — Killing in the Name (track) | v1 | #B426C0 | #972B70 | #45C5E3 | #C381BD | #211624 |
| same profile | v2 | #B93624 | #985B2B | #B6E540 | #BBA393 | #161313 |
| Touched — 새벽별 (artist fallback) | v1 | #C422C0 | #9B2763 | #42C0E7 | #C57DB7 | #231625 |
| same profile | v2 | #A35A4B | #8A6A4A | #BCBC61 | #B9AFA6 | #181515 |

- Track profile: rock, alternative rock, metal, political, alternative, rapcore,
  rap metal, 90s. Primary hue **295.4° -> 7.2°**, Secondary **321.5° -> 26.7°**.
  Confidence **66 -> 86** because rapcore/rap metal are now explicitly interpreted.
- Artist profile: heavy metal, glam metal, k-rock, korean, pop, folk metal,
  hard rock. Primary **301.2° -> 10.3°**, Secondary **328.8° -> 30.5°**.
  Confidence **56 -> 45** despite broader genre coverage, due to weaker source.
- Both profiles reasonably remain in the heavy/red family; the goal is musical
  distinction between different genre families, not forcing every song to have
  unrelated colors. The artist palette has visibly less chroma and contrast.
- Rock's yellow-green accent follows the high-tension contrast rule; other roles
  retain burnt red, orange, dusty warm tones and near-black charcoal.
- Tests use generic tag profiles, never track/artist names as algorithm inputs.

The optional `tools/compare_color_engine.py --case ARTIST TRACK` command snapshots
public tag evidence and the current analysis (including engine_version) under
ignored artifacts/. It never writes the API key or request URLs. Before/after
snapshots from this run are also in ignored artifacts/; this document is the
portable record.

## Verification and review

Command: `.\.venv\Scripts\python -m pytest -q -p no:cacheprovider`

**70 passed**, with the existing upstream Starlette/httpx deprecation warning.
No dependency change or warning suppression was introduced.

- Existing deterministic, weighted-axis, aliases, invalid/empty/unknown tags,
  confidence, color monotonicity, HEX, readability and Backend mocks remain.
- Added **22 color regression cases**: wraparound/weighting, opposite vectors,
  all 66 hue policies, heavy/red, ambient/soft, folk/earthy, electronic/cyan,
  inter-genre hue separation, warm/dreamy preservation, hue role diversity,
  source influence, explanations, ordering and contrast.
- Updated the obsolete warmth-selects-the-entire-hue assertion to a maximum
  8° adjustment around the supplied genre hue. Warm/dreamy tests supply the
  existing warm hue explicitly, consistent with the new algorithm.
- Backend fallback test now checks source_weight=0.45, confidence<=45 and the
  user-visible explanation. Legacy response role ordering/fields are unchanged;
  color_identity and source_weight are additive.
- An independent reviewer reproduced 68 passing tests and identified one P2:
  0.45 scaling could turn equal hue votes into 1.3499999999999999 vs 1.35,
  causing a 177° flip in an ambiguous mix. A failing regression reproduced it.
  Hue aggregation now uses source-independent weights, so that flip is removed.
- Also reproduced and fixed the minor ambiguous-mixture explanation gap: the
  selected tag and the equal-weight deterministic tie rule are now explicit.
  After both fixes the full suite passed 70/70. No deferred reviewer findings.
- Supporting anchors guide bounded/analogous secondary spread; they are not a
  promise to reproduce every family anchor literally in a swatch. This is an
  editorial choice, not a direct tag-to-HEX lookup.

Live Last.fm attempts returned `network_error` for both cases. No server was
started for this change, no process was left running, and no commit/push/deploy
was performed. Existing UI layout and environment secrets were not modified.
