# TONESCAPE implementation plan

The supplied user specification is the product contract. Work only in HW2;
do not initialize/push Git or change external account settings in this phase.

Architecture: one FastAPI process serves static HTML/CSS/JavaScript and JSON.
Last.fm is accessed only on the server. A pure Python mood engine translates
normalized weighted community tags into five axes, then a deterministic HSL
palette. No LLM, audio download, frontend build, or user upload is involved.

## Tasks

- [x] 1. Tests first: mood reproducibility, valid/ranged output, weight behavior,
  monotonic color controls, aliases, unknown/empty tags, confidence.
  Implement `app/services/tag_lexicon.py` and `mood_engine.py`; run pytest.
- [ ] 2. Tests first: real Last.fm adapter with HTTP transport mocks; search,
  no results, invalid key, timeout, rate limit, malformed response, TTL cache,
  track analysis and artist/neutral fallbacks. Implement `lastfm.py` and
  `main.py`, input validation, security headers and lifespan-owned client.
- [ ] 3. Build editorial responsive static UI, accessible state messages,
  stale-request cancellation, result explanation, contributions, HEX copying.
  Verify real local server with HTTP and browser; mocked Last.fm stays in
  test tooling only, never silently replaces production data.
- [x] 4. Add pinned dependencies, CI, Render blueprint, setup instructions,
  report notes and verification evidence. Review, run full tests, stop all
  servers started for verification and check ports.

## Review focus

- Track search is title-oriented: artist discovery needs artist.search then
  artist.getTopTracks when track search cannot find results.
- Missing/zero counts and malformed upstream payloads must not invent evidence.
- Artist fallback is explicitly labeled and lowers confidence.
- Browser race conditions must not replace a new selection with an old result.
- Untrusted titles/tags must render as text, with HTTPS-only artwork URLs.

## Source confirmation

Official Last.fm method docs and Render FastAPI/Blueprint docs were read before
implementation (2026-10-27). Valid live payloads require a user-owned API key;
documented examples and HTTP mocks cover success shapes until it is provided.

## Execution ledger

- Task 1: complete. 25 pure-engine tests pass on Python 3.13.1/pytest 9.1.1.
- Task 2: implementation and HTTP mock tests written; runtime verification blocked
  by unavailable FastAPI/httpx and disabled package network. Not complete.
- Task 3: UI implemented, JS syntax checked and explicit stdlib fixture HTTP
  verified. Chrome control was rejected by automatic approval review, so visual,
  responsive and clipboard behavior remain unverified. Not complete.
- Task 4: files written; no external GitHub/Render configuration was performed.
- Ruling: user explicitly requested implementation without design approval
  questions, and all writes must stay here. No worktree or Git initialization.
- Final review: independent reviewer found malformed-name evidence and weak
  swatch contrast. Both were reproduced with failing tests, fixed, and verified
  against 25 engine tests (RED -> GREEN). Palette text now uses black/white.
- Final review: cleared stale search aria-busy on cancelled analysis/new search.
  JavaScript syntax passes; browser behavior still awaits permitted validation.
- No deferred code-review findings. Full suite remains blocked at collection
  (ModuleNotFoundError: httpx); no whole-project passing claim is made.
