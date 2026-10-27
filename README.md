# TONESCAPE

**Search a song. See its color.**

Last.fm의 community genre/mood tag를 다섯 Mood Axis로 해석하고 5색 팔레트와
gradient로 변환하는 음악 탐색 웹 서비스입니다. 동일한 태그 데이터는 항상 같은
결과를 만듭니다. 음원이나 Spotify Audio Features를 사용하지 않으며, runtime LLM
호출도 없습니다.

> **Color Engine v2 검증:** 기존 기능을 포함한 전체 pytest **70 tests PASS**.
> 태그 기반 circular hue 합성으로 장르별 색상을 분리하고 Artist fallback 영향을 낮췄습니다.
> 설정된 키로 두 곡의 라이브 조회를 시도했지만 실행 환경의 네트워크 오류로 실패했습니다.
> 제공된 태그 목록·동일한 합성 count로 변경 전후를 비교했습니다. 이번 수정의 실제 배포,
> 브라우저 화면 검증은 수행하지 않았습니다.
> [v2 비교·검증](docs/COLOR_ENGINE_V2.md) / [세션별 검증 기록](docs/VERIFICATION.md).

## 기능

- Songs 검색: 곡명 관련 결과 최대 10건. Artists 검색: 가장 가까운 아티스트의 top tracks.
- 곡명·아티스트·가능한 artwork, loading/empty/error/setup 상태.
- Track Top Tags 우선, 해석 가능한 태그가 두 개 미만이면 Artist Top Tags 검토.
- 태그 부족 시 명시적인 neutral baseline, confidence 및 출처 표시.
- Energy / Warmth / Dreaminess / Darkness / Tension, 주요 태그 기여도와 규칙 기반 설명.
- Primary / Secondary / Accent / Soft / Background, HEX 복사 및 결과 gradient.
- 반응형 dark editorial UI, 키보드 조작, 상태 알림, reduced-motion 지원.
- timeout, API 오류 분류, bounded TTL cache 및 같은 진행 중 요청 병합.
- GitHub Actions CI와 Render Blueprint. 프런트엔드 build 단계나 DB는 필요 없습니다.

## 구조와 Data Flow

```text
Browser: HTML + CSS + Vanilla JS
  GET /api/search?q=...&mode=track|artist
    -> FastAPI -> Last.fm service -> track.search
                                or artist.search -> artist.getTopTracks
  GET /api/analyze?artist=...&track=...
    -> track.getInfo + track.getTopTags (parallel)
    -> if sparse: artist.getTopTags
    -> normalize / weighted mood analysis
    -> tags -> weighted circular base/supporting hue
    -> 5 Mood Axes + source influence -> HSL -> HEX + gradient + explanation
    -> JSON -> Browser renders text, bars, colors
```

```text
app/main.py                    Routes, lifecycle, validation, safe errors, headers
app/services/lastfm.py          HTTP adapter, parsing, TTL cache, fallback orchestration
app/services/tag_lexicon.py     Mood vectors, aliases, weak/non-mood tags
app/services/mood_engine.py     Pure deterministic analysis and color generation
app/services/color_engine.py    Circular hue identity and mood-adjusted palette
app/templates/index.html       Page structure
app/static/css/style.css       Responsive visual system
app/static/js/app.js            Search/select UI and clipboard
tests/test_mood_engine.py       Pure-engine tests
tests/test_backend.py           Real routes/adapter with mocked external HTTP
tools/ui_fixture_server.py     Explicit standalone UI fixture; NOT production backend
tools/verify_live.py            Real-server /health -> search -> analysis smoke check
tools/compare_color_engine.py   Public tag/analysis snapshot with the configured key
.github/workflows/ci.yml        Offline test and syntax checks on main/PR
render.yaml                    Render Web Service blueprint
docs/HW2_REPORT_NOTES.md        Coursework report notes
```

## Mood Engine

Lexicon vector 순서는 `(Energy, Warmth, Dreaminess, Darkness, Tension)`이며 0~100
범위입니다. rock, indie rock, shoegaze, ambient, metal, jazz, electronic, folk,
hip hop, rnb, classical, post-punk, lo-fi 등 66개 genre/mood를 정의합니다.
각 vector는 TONESCAPE의 편집적 heuristic이며 객관적인 감정 측정값이 아닙니다.

1. **정규화:** Unicode NFKC, casefold, 공백·구두점 정리. `HIP-HOP` → `hip hop`,
   `r&b` → `rnb`, `post_punk` → `post punk`. 문자열이 아닌 name은 제외합니다.
2. **해석:** exact/alias를 먼저 적용하고, unknown tag는 단어 경계가 맞는 가장 구체적인
   genre family를 찾습니다. `poppyseed`는 `pop`으로 해석하지 않습니다. Family match의
   신뢰 가중치는 0.6, 직접 match는 1.0입니다. 외부 LLM으로 추론하지 않습니다.
3. **선별:** 비양수·잘못된·누락 count, 비문자열 name, 국가/성별/seen live 등은 제외.
   중복 canonical tag는 가장 큰 count 한 번만 사용합니다. 유효 상위 50개를 확인하고,
   해석 가능한 상위 12개를 axis 계산에 사용합니다. 동률은 canonical name으로 정렬합니다.
4. **가중 평균:** `w = sqrt(count) × match_quality × source_weight`.
   `axis = (50 + Σ(vector_axis × w)) / (1 + Σw)`.
   sqrt는 지배적인 태그의 독점을 줄이며, weight 1의 neutral baseline은 빈약한 근거를
   약하게 정규화합니다. Track source_weight=1, Artist source_weight=0.45이며,
   Artist 축은 같은 neutral prior에 대해 영향력이 낮습니다. 최종 axis는 소수 첫째 자리까지 반올림합니다.
5. **Confidence:** `coverage = Σ(sqrt(count) × match_quality) / Σsqrt(eligible_counts)`;
   `confidence = 100 × coverage × sqrt(min(1, used_tag_count/4))`.
   Artist fallback에는 0.45를 한 번만 곱합니다. Coverage에는 source factor를 중복 적용하지 않습니다.
   Artist confidence의 상한은 45입니다. 최종 값은 0~100 정수이며, 50 미만이면
   `Low confidence — limited mood tags were available.` 안내를 표시합니다.
   Metadata 태그 품질에 대한 지표이며 결과의 과학적 정확도나 확률이 아닙니다.
6. **Fallback:** track에 해석 가능한 tag가 두 개 미만일 때 artist를 조회합니다.
   Artist에 더 많은 해석 가능한 태그가 있으면 **artist evidence로 대체**하여 source와
   경고를 표시합니다. 두 소스의 count 규모가 달라 단순 합산하지 않습니다. 여전히
   하나뿐이면 낮은 confidence로 그 근거를 유지하며, 해석 가능 태그가 0개면 모든 axis=50,
   confidence=0의 neutral 팔레트를 생성합니다. Track tag 조회의 네트워크 오류는
   정상적인 '태그 없음'으로 가장하지 않고 오류로 반환합니다.

`contributions`는 normalized tag, matched family, count, normalized share,
5-axis vector와 최종 axis에 보태진 점수를 제공합니다. 기여도 share는 baseline을 제외한
사용 태그 사이 비율이고, axis point는 baseline을 포함한 분모를 사용합니다.

## Tag identity + Mood → Color (engine v2)

모든 lexicon 항목에 primary/supporting hue anchor와 hue influence를 명시합니다.
Rock/metal은 red/crimson, ambient/electronic은 cyan/blue, folk/acoustic은 olive/ochre,
dream pop/shoegaze는 lavender, jazz/soul은 amber/burgundy 계열입니다. `dreamy` 등의
넓은 mood descriptor는 0.2~0.3의 약한 hue 투표를 하고 `energetic`, `dark`,
`instrumental`은 hue 투표 없이 축 특성만 조정합니다. 국가/성별/seen live/90s 등은 제외합니다.

`hue_weight = sqrt(count) × match_quality × hue_influence`로 단위 원 위에서 합성합니다:

```text
x = Σ(weight × cos(hue))
y = Σ(weight × sin(hue))
base_hue = atan2(y, x) mod 360
coherence = sqrt(x² + y²) / Σweight
```

350°와 10°는 0° 부근이 됩니다. Coherence가 0.2 미만이면 거의 반대인 투표가
상쇄된 경우이므로 가장 강한 태그를 사용하며, 동률은 낮은 hue와 canonical tag 이름으로
결정합니다. 이 선택과 근거를 metadata/설명에 표시합니다. 입력 정렬과 `math.fsum`으로
순서에 무관한 결과를 유지합니다. Supporting anchor도 같은 방법으로 합성한 뒤,
각 role의 hue spread 규칙에 반영합니다. Anchor가 최종 swatch hue와 항상 같다는 뜻은 아닙니다.

동일한 source factor는 원형 평균에서 수학적으로 상쇄됩니다. **Hue 투표는 source와
독립적으로 계산**하여 0.45 곱셈의 미세한 반올림이 동률 승자를 바꾸지 않도록 합니다.
Artist 영향력 감소는 axis prior, 실제 saturation/contrast 및 confidence에 적용합니다.
곡명·아티스트명은 색 생성 입력이 아닙니다.

입력 axis는 0~1로 환산한 뒤 HSL 색상 특성을 조정합니다.

| Axis | 색상에 미치는 영향 |
| --- | --- |
| Warmth | 이미 계산한 base hue를 warm/cool 방향으로 최대 8°만 보정 |
| Energy | saturation `12 + source_weight × (12 + 56e) × (1 - 0.12d)`: muted → vivid |
| Darkness | base lightness `68 - 37k`; Background는 `14 - 9k` |
| Dreaminess | Primary hue를 유지하고 supporting spread·채도를 낮추며 Soft 명도를 높임 |
| Tension | Accent hue/lightness distance 증가; Artist source는 contrast를 낮춤 |

Primary는 musical identity, Secondary는 supporting anchor 방향의 관련색,
Accent는 energy/tension에 따른 대비색, Soft는 저채도·고명도, Background는 저명도·저채도입니다.
각 role에 hue/saturation/lightness offset을 적용하여 다섯 색을 만들며 채도·명도는
clamp합니다. Background는 같은 hue 계열의 낮은 명도를 사용합니다. Gradient의
중간 stop도 Dreaminess로 바뀝니다. HEX 양자화 후 밝기를 계산해 흑백 중 대비가 높은
텍스트를 선택합니다. 검증한 모든 표본에서 normal-text 4.5:1 이상입니다.
페이지 본문은 고정된 읽기 쉬운 dark surface를 사용하고 결과색은 artwork 배경,
ambient glow, bars, swatches에 반영합니다.

Keywords는 50에서 가장 멀리 떨어진 축 순서로 3~4개를 고릅니다. 설명은 hue,
saturation, lightness, softness와 accent contrast 규칙을 문장으로 조합합니다.
랜덤 seed, timestamp, Python hash, 곡명에 따른 임의 색상은 사용하지 않습니다.
**동일한 정규화 태그 데이터와 engine version에 대해서만 재현성을 보장**합니다.
Last.fm 태그 자체가 바뀌면 같은 노래도 결과가 달라질 수 있습니다.

## 기술 및 요구 사항

Python 3.13, FastAPI, Uvicorn, httpx, python-dotenv, pytest,
HTML/CSS/Vanilla JS, GitHub Actions, Render Web Service.
Node는 JS 문법 검사와 CI에서만 사용하며 서비스 실행에는 필요하지 않습니다.
직접 의존성은 버전을 고정했습니다. 전체 전이 의존성 lockfile은 포함하지 않습니다.

## 설치 / Local 실행 (Windows PowerShell)

아래 명령은 이 repository의 root에서 실행합니다. 초기 환경이면 먼저 clone한 폴더로
이동하세요. PowerShell activation policy를 바꾸지 않도록 venv Python을 직접 호출합니다.

```powershell
Set-Location 'D:\univ\3-1\OpenSW\HW2'
python -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements-dev.txt
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
# 편집기에서 .env의 LASTFM_API_KEY를 채웁니다. 기존 .env가 있다면 덮어쓰지 마세요.
.\.venv\Scripts\python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

`http://127.0.0.1:8000`을 엽니다. 종료는 `Ctrl+C`입니다. 운영 설치만 필요하면
`requirements-dev.txt` 대신 `requirements.txt`를 설치합니다.

macOS/Linux에서는 `python3 -m venv .venv`, `.venv/bin/python -m pip ...`,
`.venv/bin/python -m uvicorn ...`을 사용합니다.

### Last.fm API key

[Last.fm API account creation](https://www.last.fm/api/account/create)에서 본인 계정으로
키를 발급받아 로컬 `.env`에 저장합니다. 이 읽기 전용 기능에는 API secret이나
사용자 session 인증은 필요하지 않습니다. 이미 발급한 키가 있으면 재사용할 수 있습니다.

```dotenv
LASTFM_API_KEY=your_own_key_here
```

키는 채팅, 코드, screenshot, GitHub workflow 변수에 넣지 마세요. `.env`는 Git ignore
대상입니다. Render에서는 파일 업로드 대신 Environment에 저장합니다. OS/Render 환경변수는
`.env`보다 우선하며 변경 후 앱을 재시작합니다. 키가 없어도 landing과 `/health`는
동작하도록 구현했고, 검색 시 setup 안내와 HTTP 503을 반환합니다.

| Variable | Required | Purpose |
| --- | --- | --- |
| `LASTFM_API_KEY` | 라이브 검색/분석에 필요 | 서버에서만 Last.fm 요청에 사용 |
| `PORT` | Render가 제공 | Start Command에서 사용. 로컬은 `--port 8000` |

### API

| Endpoint | Response |
| --- | --- |
| `GET /` | 페이지 HTML |
| `GET /health` | `status: ok`, `lastfm_configured: boolean` (키 유효성 검사는 아님) |
| `GET /api/search?q=Believe&mode=track` | `query`, `mode`, `tracks[{title,artist,artwork,url,album}]` |
| `GET /api/search?q=Cher&mode=artist` | 아티스트 검색 후 top tracks |
| `GET /api/analyze?artist=Cher&track=Believe` | `track`, `source`, `tags`, `warnings`, `analysis` |

`analysis`: engine_version, axes, confidence, coverage, fallback, contributions,
source_weight, color_identity (base/supporting/primary hue, coherence, hue votes, tie-break metadata),
keywords, palette, gradient, explanation, notice. API 명세는 `/docs`에서 확인할 수 있습니다.
오류는 `{ "error": { "code": "...", "message": "..." } }`입니다.

| Error | HTTP |
| --- | --- |
| invalid_input | 422 |
| setup_required / invalid_api_key | 503 |
| not_found | 404 |
| rate_limited | 429 (`Retry-After: 30`) |
| upstream_timeout | 504 |
| network_error / upstream_unavailable / invalid_response | 502 |

Search 최대 200자, artist 최대 200자, track 최대 300자이며 빈칸·control 문자를 거부합니다.
httpx params와 URLSearchParams로 인코딩하며, upstream의 HTML이나 오류 문구를 그대로
전달하지 않습니다. UI는 createElement/textContent만 사용합니다. Artwork/Last.fm 링크는
허용한 host의 HTTPS만 표시합니다. 외부 요청마다 read timeout 8초/connect 4초, User-Agent,
최대 8개의 동시 outbound 요청, 256-entry/300초 process-local TTL cache를 사용합니다.
API 키가 담기는 upstream URL을 로그에 남기지 않습니다.

## 테스트와 남은 검증

```powershell
.\.venv\Scripts\python -m pytest -q
node --check app/static/js/app.js
```

Backend 테스트는 외부 HTTP만 httpx MockTransport로 대체하며 실제 parser, cache,
fallback, mood engine과 FastAPI routes를 통과합니다. 키나 인터넷은 테스트에 필요 없지만
의존성 **최초 설치**에는 PyPI 접근이 필요합니다. CI도 이 테스트를 수행하도록 구성했습니다.

키를 설정한 실제 Uvicorn 서버를 실행한 다음 별도 터미널에서:

```powershell
.\.venv\Scripts\python -m tools.verify_live
# 배포 서비스도 가능:
.\.venv\Scripts\python -m tools.verify_live https://YOUR-SERVICE.onrender.com
```

이 스크립트는 health → 실제 검색 → 선택된 곡 분석을 검사하고, 키·upstream 원문을
출력하지 않습니다. 키가 없으면 명확하게 실패합니다.

키 없이 UI를 수동 점검할 때는 명시적인 fixture를 사용할 수 있습니다:

```powershell
python -m tools.ui_fixture_server
```

`http://127.0.0.1:8765`에서 어떤 검색어든 8개 예시를 보여줍니다. `empty`, `error`,
`setup`은 각각 빈 결과/오류/키 누락 안내 fixture입니다. 곡 선택 결과는 **합성 태그**를
실제 Mood Engine에 넣어 생성합니다. 이 서버는 FastAPI 검증이나 라이브 검증을 대체하지
않으며 Render에서는 절대 실행하지 않습니다. 종료는 Ctrl+C.

브라우저 확인 순서: landing → 검색/Enter → 곡 선택 → 5개 bars/5색/태그·기여도/설명 →
HEX 클릭 후 다른 텍스트 필드에 붙여넣기 → back → 다른 곡 선택. `empty/error/setup`,
neutral fixture, HTML처럼 생긴 곡명도 확인합니다. Desktop 1440px, tablet 768px,
mobile 390px/320px에서 overflow·가독성을 확인합니다. Clipboard가 차단되면 수동 복사할
HEX를 안내합니다. 실제 artwork·브라우저 복사는 아직 검증하지 못했습니다.

## GitHub 저장소 준비

이번 단계에서는 Git initialize/remote 생성/push를 실행하지 않았습니다. 먼저 위 전체
테스트와 브라우저 검증을 마치고, GitHub에서 **빈 repository**를 만든 뒤 실행하세요.
이미 저장소나 remote가 있다면 해당 설정을 보존하고 필요한 단계만 사용합니다.

```powershell
git init -b main
git status --short
git check-ignore .env
git add .
git diff --cached --name-only
# .env / .venv / artifacts 등이 staging되지 않았는지 확인한 뒤:
git commit -m "Build TONESCAPE music color explorer"
git remote add origin https://github.com/YOUR-ACCOUNT/tonescape.git
git push -u origin main
```

`git remote -v`로 먼저 기존 remote를 확인하고, 존재하면 삭제/교체하지 마세요.
GitHub에 README 등 초기 파일을 만들었다면 독립적인 기록일 수 있으니 강제 push하지
말고 정상적인 clone/병합 절차를 사용합니다. Credential은 로그나 문서에 출력하지 않습니다.

## Render 배포 및 자동 배포

[Render 공식 FastAPI 가이드](https://render.com/docs/deploy-fastapi)와
[Blueprint 설정 문서](https://render.com/docs/blueprint-spec)를 기준으로 구성했습니다.

1. GitHub에 코드를 push한 뒤 Render에 로그인합니다.
2. **New → Blueprint**로 repository를 연결하고 `render.yaml`을 적용합니다.
   처음 연결할 때 GitHub repository 접근 권한은 본인이 승인해야 합니다.
3. `LASTFM_API_KEY` 입력란에 키를 저장하고 service를 생성합니다. `sync: false`여서
   실제 값은 소스에 없습니다.
4. 첫 build/deploy 로그와 live URL을 확인합니다. 첫 배포는 계정에서 실제 성공을
   확인해야 하며, 이 저장소 설정만으로 완료된 것으로 취급하지 않습니다.

Web Service를 수동 생성할 때도 다음과 같이 설정합니다:

| Setting | Value |
| --- | --- |
| Runtime | Python 3 |
| Branch | `main` |
| Root Directory | 빈칸 (이 HW2의 내용이 repository root에 있을 때) |
| Build Command | `pip install -r requirements.txt` |
| Start Command | `uvicorn app.main:app --host 0.0.0.0 --port $PORT` |
| Health Check Path | `/health` |
| Auto-Deploy | **After CI Checks Pass** (`autoDeployTrigger: checksPass`) |
| Environment | `LASTFM_API_KEY` |

Python 버전은 `.python-version`으로 지정합니다. `$PORT`는 Render Linux shell에서
확장됩니다. Windows에서 이 Render command를 그대로 실행하지 말고 local command를
사용하세요. `plan: free`는 과제용 설정이며, 생성 시 계정에서 제공하는 요금제와 조건을
직접 확인하세요.

```text
edit -> commit -> push main
  -> GitHub Actions: install -> pip check -> pytest -> JS syntax
  -> CI checks pass
  -> Render: pip install -> Uvicorn start -> /health -> new version live
```

Render와 GitHub의 CI check 연동이 활성화되어야 합니다. 테스트가 실패하면 수정 후
다시 push합니다. `checksPass`는 단순 push 즉시 배포보다 안전한 gate이며 별도 Deploy
Hook secret은 필요하지 않습니다. 상세 동작은
[Render Automatic Deploys](https://render.com/docs/deploys#automatic-deploys)에서 확인하세요.
GitHub Actions workflow가 실행되고 Render가 그 checks를 인식하는지 실제로 확인해야 합니다.

배포 증명: 작은 문구 변경을 main에 commit/push → Actions 성공 → Render Deploy History의
동일 commit 확인 → live page와 `/health` 재확인. 이 실제 증명은 아직 수행하지 않았습니다.

## Known Limitations

- 실제 음향 신호 자체를 분석하는 것이 아니라 **Last.fm community tag metadata**를 기반으로 합니다.
- Tag가 적거나 품질이 낮으면 confidence가 낮아질 수 있습니다. 아티스트 태그는 개별 곡과 다를 수 있습니다.
- 색상과 음악 분위기의 관계는 **TONESCAPE가 정의한 heuristic mapping**입니다.
- Last.fm tag/count는 사용자의 투표를 반영하며 실제 음향 특성이나 심리적 감정의 확률이 아닙니다.
- 미해석/문맥적/부정적 태그의 의미는 완전하게 이해하지 못하며 언어별 lexicon coverage도 제한됩니다.
- Track 검색은 곡명 중심입니다. 아티스트명 검색은 Artists를 선택하며, 가장 가까운 아티스트 한 명의 인기 곡을 표시합니다.
- Artwork와 metadata가 없을 수 있습니다. 이 경우 생성된 색 기반 레코드 illustration을 표시합니다.
- 캐시는 process-local이라 재시작하면 비워집니다. 여러 worker 사이에서 공유되지 않고 persistence는 없습니다.
- Outbound 동시성 제한은 public endpoint에 대한 완전한 per-user rate limiter가 아닙니다.
- 외부 API 장애 시 검색/분석이 제한됩니다. 오류를 태그 부족으로 숨기지 않습니다.
- Backend의 mock HTTP 통합 테스트는 통과했습니다. 이번 수정의 라이브 API 조회는 네트워크 오류로 실패했으며 브라우저/모바일/clipboard와 배포 후 결과는 재검증하지 않았습니다.

## 확인한 공식 API 문서

2026-10-27에 공식 method parameter·sample response·error code를 확인했습니다.
정상 live JSON은 키 부재로 확보하지 못했으며 mock은 문서의 계층을 JSON으로 표현한
검증 데이터입니다. **실제 최신 정상 응답을 캡처한 fixture라고 주장하지 않습니다.**

- [track.search](https://www.last.fm/api/show/track.search)
- [track.getInfo](https://www.last.fm/api/show/track.getInfo)
- [track.getTopTags](https://www.last.fm/api/show/track.getTopTags)
- [artist.getTopTags](https://www.last.fm/api/show/artist.getTopTags)
- [artist.search](https://www.last.fm/api/show/artist.search)
- [artist.getTopTracks](https://www.last.fm/api/show/artist.getTopTracks)
