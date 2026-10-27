# TONESCAPE verification record

Date: 2026-10-27. Workspace: `D:\univ\3-1\OpenSW\HW2`.
Python 3.13.1; installed global pytest 9.1.1; Node 24.13.0.

## Performed

| Check | Command / observation | Actual result |
| --- | --- | --- |
| Workspace | Get-Location; Get-ChildItem -Force | Exact requested path; initially empty |
| Git | git rev-parse --show-toplevel; git status --short | Not a repository, including parent search; no Git changes performed |
| Mood tests | `python -m pytest -q -p no:cacheprovider tests/test_mood_engine.py` | **25 passed** |
| JavaScript syntax | `node --check app/static/js/app.js` | Exit 0 |
| Python syntax | `python -m compileall -q app tests tools` | Exit 0 |
| Explicit fixture server | `python -m tools.ui_fixture_server` | Started on 127.0.0.1:8765 |
| Fixture HTTP | stdlib urllib with loopback-only request | fixture health, 8 search results, 5-color analysis with dreaminess >80, empty results passed |
| Source/config review | Read route/static/config/env files | .env ignored, .env.example supplied; no production credential included |
| Independent review | Separate read-only reviewer | Found malformed-name evidence + swatch text contrast; fixed with failing regression tests then passing tests |
| Port cleanup | Ctrl+C fixture session; socket.connect_ex | Port 8765 closed after verification |

The explicit fixture server uses synthetic tags and the real pure mood engine.
It is **not** FastAPI/Uvicorn and is **not** a live Last.fm integration test.
No screenshot or clipboard observation was obtained.

## Failed / blocked checks

1. `python -m venv .venv` failed in ensurepip: PermissionError while accessing a
   temporary directory. Retried with a workspace-local TEMP directory; Python's
   restricted-mode temporary-directory creation still failed. Ordinary normal-mode
   directory/file writes inside the workspace worked. Security/ACL settings were
   not changed. An incomplete ignored `.venv` may remain; recreate it in a normal
   local terminal using the README commands.
   The first pytest run also left restricted temporary `pytest-cache-files-*`
   directories. The cleanup command was rejected by tool policy ("blocked by
   policy"); those directories were left intact and excluded by .gitignore.
   Later runs disabled pytest's cache provider to avoid more such directories.
2. Package installation failed. The managed runner sets `PIP_NO_INDEX=1`;
   PyPI requests through its configured proxy were refused. Relevant offline
   packages were not present. No proxy, network isolation, or security setting was
   changed. FastAPI/httpx/Uvicorn/dotenv are unavailable to this runner.
3. Full suite command:
   `python -m pytest -q -p no:cacheprovider`
   **Failed during collection** with `ModuleNotFoundError: No module named 'httpx'`
   in `tests/test_backend.py`. This is NOT a Backend test PASS or a skipped success.
4. Browser tool inventory succeeded, but selecting the intended Chrome window
   returned **"Computer Use was not approved to use Google Chrome"**.
   No detailed reason was supplied. No alternate UI channel was used to bypass
   that denial. Landing/search/select/result, desktop/mobile layout and HEX copy
   therefore remain unverified in a real browser.
5. User selected **continue without a key**. No valid Last.fm response was
   available. Official method docs were read, but mock response shapes are
   documented-example-based, not captured current live success responses.
6. No Git repository/remote was created and no push was performed. No Render
   login, repository authorization, service creation, live deploy or auto-deploy
   history verification was performed.

Raw test outputs from this session are in ignored `artifacts/pytest-mood.txt`
and `artifacts/pytest-full.txt`; this file is the portable repository record.

## Requirements still unverified

- Fresh dependency install and `pip check` in the normal local/Render environment.
- Actual FastAPI startup and real `/health` response with and without a key.
- Backend test suite PASS (provided tests cover real routes/parser/cache with
  mocked external transport).
- Live Last.fm search/info/top-tags, artwork and fallback response compatibility.
- Real browser end-to-end flow, error/empty/setup, source labels, neutral fallback.
- Desktop/tablet/mobile layout, keyboard experience, reduced motion, actual clipboard.
- Render Blueprint application/build/start health and GitHub CI checks integration.
- main push automatically redeploys the matching commit on Render.

## Resume verification

From an ordinary terminal with package access:

```powershell
Set-Location 'D:\univ\3-1\OpenSW\HW2'
python -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements-dev.txt
.\.venv\Scripts\python -m pip check
.\.venv\Scripts\python -m pytest -q
node --check app/static/js/app.js
.\.venv\Scripts\python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

With no key, open `/health` and submit a search to verify the setup message.
When a key becomes available, store it in `.env`, restart Uvicorn, then in another
terminal run `.\.venv\Scripts\python -m tools.verify_live` and the browser
checklist in README. Stop Uvicorn with Ctrl+C when finished.

After those checks, use README's GitHub/Render procedure, push a small visible
change and record the actual live URL, commit SHA, CI result and Render deployment
result here. Only then replace the pending status in the coursework report.
