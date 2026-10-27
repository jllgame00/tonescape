# Color Engine v3: preserve musical mixtures

## Design / implementation plan

Starting point: clean checkout c5ab458, 70 existing tests passing. Work in HW2;
no Git commit/push, deployment, UI redesign, new dependency or secret changes.

The v2 failure is dimensional collapse: tag hues -> one mean -> every chromatic
role near that mean. Funk's orange anchor and soul's warm red exacerbate warm
convergence. Single-match resolution also discards hybrid genre components.

- [x] Reproduce with generic shared fixture profiles and freeze actual v2 results.
- [x] Declare genre family membership for every tag, including multi-family
  shares for hybrid genres. Preserve sqrt(count), match quality, hue influence
  and source-independent hue identity; artist source weight stays 0.45.
- [x] Aggregate scores and circular hues WITHIN families. Select role anchors
  from meaningful families instead of averaging all families into one hue.
- [x] Enforce 30-degree separation when distinct family evidence supports it,
  preferring declared alternate anchors. Nearby families may receive <=15-degree
  composition adjustment, half the separation target; never add random colors.
  Single-family/cool analogous music may remain tonal. Mood controls properties.
- [x] Add family distribution and role provenance, update explanations without
  exposing new controls. Keep old response fields; v2 global hue is diagnostic
  only and no longer drives palette composition.
- [x] Run the entire suite, independent review and profile comparison. Try live
  Last.fm metadata; report fixtures explicitly if outbound access still fails.

Meaningful family threshold: at least 4% of hue evidence. This allows a supported minor accent (e.g. psychedelic soul)
without letting a tiny unrelated tag hijack a role. There is no second cutoff
relative to the leading family: that would suppress hybrid flavors simply
because the leading family has several related tags. Strong means >=15% total.
All family scores are normalized after split weights; multi-family shares sum
to one so a hybrid does not create extra evidence.

The global v2 diagnostic fields remain for compatibility and investigation.
Role metadata is authoritative for v3 colors. Same-family tonal colors and a
declared alternate anchor under energetic/tense moods are legitimate; an
unconditional rainbow/minimum spread for all music is not.

## Final algorithm and provenance

75 tag entries retain mood vectors and match-quality behavior. Every entry has
an explicit family policy; hybrid shares sum to one. Source-independent family
scores are `sum(sqrt(count) * match_quality * hue_influence * family_share)`.
The distribution is normalized over interpreted hue evidence; confidence still
accounts for uninterpreted tag weight separately.

Primary uses the highest score, with equal scores ordered by lowest hue then
family ID. Secondary/Accent are allocated jointly: try ranked families and
declared alternative endpoints before discarding a meaningful third family.
A <=15-degree composition nudge separates nearby genuine identities. Warmth
correction remains <=8 degrees and is reduced if it conflicts with separation.
Soft blends the selected Primary/Secondary, and Background is a dark dominant
tint. Data-free Neutral retains **all five v2 HEX/HSL/text results exactly**.

When a third distinct family cannot be represented, high energy/tension may
select an already declared contrast endpoint; quiet single-family music remains
tonal. This is documented role provenance (`genre_family`, `family_contrast`,
`tonal`, `primary_secondary_blend`, `dominant_tint`, `neutral_baseline`).

Artist source retains the exact family distribution and selection identity.
Fallback endpoint selection uses nominal source-independent tag mood; rendered
saturation/lightness properties and the displayed mood axes use the 0.45 source
discount, as does confidence. This avoids changing genre identity simply because
the same tags came from an artist rather than a track.

`genre_families` exposes label, normalized share, score, hue candidates, tags,
meaningful/strong flags. `palette_anchors` exposes role source, family, raw
anchor and rendered hue. Existing UI layout is unchanged; the existing Why
paragraph now describes actual role provenance and the existing Artist notice
still explains lower confidence. No extra controls/large metadata panels added.

## Generic fixture comparison (equal synthetic count=100)

These are **not live captures** of particular songs. The 8 profiles are committed
in `tests/fixtures/genre_profiles.json`. Actual v2 results were frozen from the
clean c5ab458 code before edits, then exactly the same inputs were passed to v3.

| Profile | v2 Primary | v2 Secondary | v2 Accent | v3 Primary | v3 Secondary | v3 Accent |
| --- | --- | --- | --- | --- | --- | --- |
| Soul / Funk / Psychedelic | #CF5A53 | #BC744E | #E1C574 | #CC525C | #B99F4F | #72DECD |
| Rock / Metal / Rap | #B82D20 | #965628 | #B0E73B | #B83C20 | #96284B | #E7CD3B |
| Jazz / Swing | #BE9C59 | #AD5952 | #D37773 | #C36575 | #B2965E | #7ED5D6 |
| Ambient / Dream | #6591B0 | #657DA0 | #768AC5 | #65A0B0 | #6E65A0 | #7693C5 |
| Electronic / Techno / Synth | #298BCA | #4A34A8 | #8E52E5 | #2C81CC | #3765AA | #8955E4 |
| Folk / Acoustic | #BCAA67 | #AB8761 | #D0967D | #BCBC67 | #ABA161 | #D0C37D |
| Artist heavy mixture | #A35A4B | #8A6A4A | #BCBC61 | #A34B52 | #8A6A4A | #6187BC |
| Neutral | #6F7E8D | #686C7E | #80829B | #6F7E8D | #686C7E | #80829B |

Soul mixture: **Soul/R&B 56.875%, Funk 32.5%, Psychedelic 5.625%, Electronic 5%**.
Roles retain Soul -> Funk -> Psychedelic. The cool accent is real hybrid evidence,
not a random or universal complementary color. The Artist heavy distribution is
Metal35.8333%, Rock33.3333%, Pop25%, Folk5.8333%; selected roles preserve Metal,
Rock and Pop. Fourth/lower families remain in metadata and axis properties;
there are only three chromatic role slots, not a promise to show every family.

Offline comparison:

```powershell
.\.venv\Scripts\python -m tools.compare_genre_profiles
```

Outputs ignored JSON `artifacts/color_v3_profiles.json` and a standalone visual
comparison `artifacts/color_engine_v3_comparison.html`. Without the pre-edit
baseline artifact, the command honestly shows current results only.

## Verification

```powershell
.\.venv\Scripts\python -m pytest -q -p no:cacheprovider
```

**100 passed**, one existing upstream Starlette/httpx deprecation warning.
No dependency change or warning suppression was introduced.

- 70 existing cases remain, including circular wraparound, source roundoff,
  determinism, axis weighting, aliases, unknown/empty fallback and Backend HTTP
  mock tests. The prior unconditional minimum-spread assertion now allows quiet
  single-family music to remain tonal, in accordance with v3's requirement.
- 30 additional generic cases cover hybrid conservation/match quality, all
  75 family policies, role diversity, three-family allocation, tiny unrelated
  evidence, cool/earthy/electric profiles, single-family restraint, Artist source,
  neutral, every profile's determinism/valid HEX and quantized 4.5:1 text contrast.
- Backend response verification also checks engine_version=3.0 and family/role
  metadata, passing through the actual route, adapter and mood engine with only
  external HTTP mocked.
- Independent review found greedy Secondary could block a valid third family
  for equal jazz+soul+metal. A failing regression reproduced this; joint role
  allocation now finds the supported [345,45,15] composition instead of dropping
  Metal. Optional warmth adjustment is waived in this tight layout.
- Review also surfaced source-dependent contrast-family selection for rock10 +
  techno10. As a policy choice, endpoint identity now uses nominal tag axes and
  source discount changes rendering properties. Its regression failed before
  the fix and passes after it. No deferred reviewer findings.
- The reviewer checked all 75-tag triples and 15,000 weighted profiles without
  exceptions before the final allocation fix. These exploratory probes are
  review evidence, not a replacement for the committed deterministic regressions.

Configured-key live attempts: Rage Against the Machine / Killing in the Name,
Frank Sinatra / Fly Me to the Moon, Childish Gambino / Redbone, Beach House /
Space Song. **All four returned `network_error`**. No proxy/security restriction
was bypassed and no credential/request URL printed. No live Neutral is claimed;
that case is intentionally a data-free fixture.

This change did not start a server, operate the browser, alter .env, commit,
push or redeploy. Runtime browser/production appearance after deploying v3 has
not been verified in this session.

## Changed files

- `app/services/genre_families.py` (new), `palette_composition.py` (new)
- `app/services/tag_lexicon.py`, `mood_engine.py`, `color_engine.py`
- `tests/test_family_palette.py` (new), `tests/fixtures/genre_profiles.json` (new)
- `tests/test_color_engine.py`, `tests/test_backend.py`
- `tools/compare_genre_profiles.py` (new)
- `README.md`, this document, `docs/VERIFICATION.md`, `docs/HW2_REPORT_NOTES.md`
