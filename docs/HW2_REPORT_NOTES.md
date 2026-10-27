# HW2 보고서 작성 메모 — TONESCAPE

## Project purpose

**TONESCAPE — Search a song. See its color.** 노래 검색 후 Last.fm community
tag metadata를 다섯 Mood Axis로 계산하고 5색 Palette/Gradient로 시각화한다.
결과에서 태그·confidence·기여도를 보여 분석 근거를 설명한다.

## Why DevOps

소스를 GitHub에서 version control하고 자동 테스트와 Render 자동 배포를 연결하여,
반복적인 수동 업로드를 줄이고 동일한 절차로 검증·배포한다. Commit 단위로 변경과
배포 기록을 연결해 문제를 추적하고 마지막 정상 commit으로 복원하기 쉽게 한다.

## Service architecture / technologies

Browser(HTML/CSS/Vanilla JS) → FastAPI routes → httpx Last.fm adapter →
pure Python Mood Engine → JSON → browser rendering.
Uvicorn이 실행하며 DB나 frontend build tool은 사용하지 않는다.
python-dotenv는 로컬 환경 설정을 읽고 pytest가 엔진과 backend contract를 검사한다.
Last.fm 외부 HTTP만 MockTransport로 대체하고 parser·fallback·routes는 실제 코드를 사용한다.

## Last.fm API 역할

- track.search 또는 artist.search → artist.getTopTracks: 곡 선택 후보
- track.getInfo: 가능한 album/artwork metadata
- track.getTopTags: count가 포함된 곡의 community tags
- artist.getTopTags: 곡 태그가 적을 때 별도 출처로 표시하는 fallback
- LASTFM_API_KEY는 서버 환경변수에만 저장. .env는 Git ignore.
- Timeout, User-Agent, 오류 분류, TTL cache로 외부 API 실패에 대응한다.

공식 문서는 확인했다. Color Engine v3 검증 시 키가 설정되어 있었으나 네 유형의 곡 조회는
모두 네트워크 오류로 실패했다. **이번 수정의 실제 정상 API 응답은 미검증**이다.
Mock fixture는 공식 sample structure를 참고한 합성 데이터이며 라이브 캡처가 아니다.

## Mood Engine 핵심

1. normalize/alias/deduplicate → non-mood/invalid count 제외
2. 의미 있는 상위 12개 tag와 sqrt(count), family-match 0.6 가중치 사용
3. `(50 + Σ(vector × weight)) / (1 + Σweight)`로 neutral prior와 가중 평균.
   Artist weight는 Track의 0.45로 반영한다.
4. Energy/Warmth/Dreaminess/Darkness/Tension 각 0~100
5. 해석된 weight coverage·tag 개수·artist source로 confidence 계산
6. Hybrid tag를 여러 genre family에 나눠 반영하고 sqrt(count) 기반 family score를 normalize.
   Family를 한 hue로 합치지 않고 Primary/Secondary/Accent에 2~3개의 identity를 보존한다.
   Circular mean은 동일 family 내부에서만 사용한다. Secondary와 Accent는 함께 탐색한다.
   energy→saturation, darkness→lightness, dreaminess→softness/tonal spread,
   tension→지원되는 contrast 선택, warmth→각 anchor 최대 8° 보정.
   Artist는 family 분포를 보존하고 saturation/lightness contrast/confidence를 낮춘다.
7. HSL clamp → 5 HEX, 대비에 맞는 흑백 텍스트, deterministic keywords/설명

음향 신호 자체의 분석이 아니며 색상 관계도 TONESCAPE의 heuristic mapping이다.
태그가 적거나 품질이 낮으면 confidence가 낮아진다. Artist tag는 개별 곡과 다를 수 있다.

## GitHub → Render 자동 배포

main commit/push → GitHub Actions install/pip check/pytest/JS syntax → CI 성공 →
Render `autoDeployTrigger: checksPass` → pip install → Uvicorn → `/health` → live.

Build: `pip install -r requirements.txt`

Start: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`

`render.yaml`: main, Python runtime, healthCheckPath=/health,
LASTFM_API_KEY sync:false. 이번 Color Engine 수정에서는 commit/push나 배포 설정 변경을
수행하지 않았다. 사용자가 확인한 기존 배포와 이번 로컬 수정의 반영 여부를 구분해야 한다.

## Local verification / Test 결과

상세 실행 기록과 한계는 [VERIFICATION.md](VERIFICATION.md)에 기록한다.
Color Engine v3 수정에서는 기존 Backend를 포함한 **전체 pytest 100개가 통과**했다.
기존 circular/axis/source/fallback 검사를 유지하고 hybrid evidence 보존, family별 비중,
2~3개의 role 분리, single-family restraint, 3-family 대안 탐색을 추가 검증했다.
기존 초기 세션의 설치 제약은 현재 `.venv`에서는 해소되어 있다.
라이브 네 유형의 조회가 네트워크 오류로 실패하여 generic profile 8개와 합성 count=100으로 비교했다.
상세 팔레트·한계는 [COLOR_ENGINE_V3.md](COLOR_ENGINE_V3.md)에 기록한다.
이번 수정의 브라우저/모바일/HEX clipboard 검증은 수행하지 않았다.
1페이지 보고서에는 미수행 항목을 성공했다고 쓰지 말고 실제 배포 후 기록으로 보완한다.

## 배포 후 확인할 항목

- GitHub Actions 전체 suite 성공
- Render build/start/deploy 로그, linked main branch, CI-gated auto deploy 설정
- `/health`: status=ok, lastfm_configured=true (키 유효성은 검색으로 확인)
- 실제 Last.fm 검색, track 선택, artwork/태그/5색/설명/axis
- API error/빈 결과, low-confidence/artist/neutral fallback 표시
- Desktop/mobile overflow, 키보드 탐색, HEX clipboard 붙여넣기
- 새 commit push 후 Render History의 commit SHA와 실제 페이지 변경 일치
- screenshot에 키나 계정 credential이 보이지 않는지 확인

## Screenshot 추천

1. **실제 배포 URL**에서 검색 결과와 선택한 곡의 Palette/Mood Axis가 보이는 장면.
   가능하면 같은 브라우저 창에서 검색 결과, 분석 결과를 각각 캡처하여 한 figure로 배치.
2. GitHub main push의 Actions 성공 + Render Deploy History의 동일 commit 자동 배포 성공.

Fixture 화면은 필요하면 'synthetic local fixture'라고 명확히 표기한다. 실제 서비스 화면이나
자동 배포 성공 증거로 대신 제출하지 않는다.

## 1페이지 구성 제안

상단: 프로젝트 목적과 DevOps 필요성 (약 20%).
중단: architecture/data flow와 Mood Engine 핵심 (약 30%).
하단: 실제 서비스 화면 + 자동 배포 증거, 테스트 결과와 한계 (약 50%).
