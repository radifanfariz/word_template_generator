# Word Template Generator

Python 3.14+ project that fills `.docx` templates with `{{ placeholder }}` syntax. Zero external runtime dependencies — stdlib only.

## Quick start

```bash
python run.py                              # http://127.0.0.1:8000
python run.py --host 0.0.0.0 --port 8000   # custom bind
python scripts/create_sample_template.py    # regenerate sample .docx
```

## Architecture

- `run.py` — CLI entrypoint (argparse, starts `ThreadingHTTPServer`)
- `app/server.py` — HTTP handler, API endpoints, multipart/CSV parsing
- `app/docx_engine.py` — core library: field extraction, fill, batch ZIP
- `static/` — vanilla HTML/CSS/JS SPA (no framework, no bundler)

**API** (all `POST` use `multipart/form-data`):
| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/health` | GET | `{"status": "ok"}` |
| `/api/templates/scan` | POST | Returns `{{ fields }}` from uploaded `.docx` |
| `/api/generate` | POST | Single doc fill |
| `/api/generate/batch` | POST | CSV → ZIP of filled docs |

## Notable quirks

- No test framework or test files exist. No lint/format/typecheck configured.
- Project has **no Git commits yet** (`master` branch, empty tree).
- No `.env` — zero environment variable configuration.
- Docker: `docker build -t word-template-generator . && docker run -p 8000:8000 word-template-generator`
- Placeholder regex: `\{\{\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*\}\}`
- `.docx` is a ZIP; engine reads `word/document.xml`, headers, footers, footnotes, endnotes.
- `.gitignore` excludes generated `*.docx` (keeps `samples/*.docx`), `uploads/`, `.env`, `__pycache__`.
- Only dependency is Python 3 stdlib. `requirements.txt` lists only `ruff` as optional dev tool.
