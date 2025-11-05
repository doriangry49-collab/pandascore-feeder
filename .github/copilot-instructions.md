## pandascore-feeder — quick orientation for AI coding agents

This repository is a tiny Vercel Python serverless function that fetches upcoming CS:GO matches from the PandaScore API and stores them into a Postgres database. The primary source file is `api/index.py` and deployment is configured via `vercel.json`.

Key facts you should know (short):
- Runtime: Vercel Python serverless function (see `vercel.json` -> `builds`).
- Main dependencies: `requests`, `psycopg2-binary` listed in `requirements.txt`.
- Env vars used: `PANDASCORE_API_KEY` (required), `DATABASE_URL` (required), optional `cron_secret` (if set, requests must include `Authorization: Bearer <cron_secret>`).
- Endpoint: the function is mounted at `/api` and Vercel Cron triggers it hourly (see `vercel.json` -> `crons`).

What to look for in the codebase:
- `api/index.py` — single handler that:
  - calls PandaScore: GET https://api.pandascore.co/csgo/matches/upcoming?sort=-scheduled_at&per_page=50
  - connects to Postgres using `psycopg2` and `DATABASE_URL`
  - ensures a `matches` table exists (creates it if missing) and inserts new rows using `ON CONFLICT (id) DO NOTHING` so runs are idempotent
  - stores full API response in `raw_data` (JSONB)
- `vercel.json` — shows the Vercel build target and the cron schedule. Use this to understand production invocation.

Conventions & important patterns to preserve when editing:
- Idempotency: new inserts use `ON CONFLICT DO NOTHING`. Keep or improve this behavior when changing DB writes.
- Defensive env checks: the handler responds with JSON error and 500 status when `PANDASCORE_API_KEY` or `DATABASE_URL` are missing — preserve clear error responses.
- Security: optional `cron_secret` gate is implemented — if present, requests must include `Authorization: Bearer <cron_secret>`.

Common pitfalls and explicit notes for modifications:
- `api/index.py` currently contains duplicated import/class blocks and minor formatting issues — safe to refactor for clarity, but keep the same env var names and response JSON shape.
- The function uses `psycopg2` (Postgres). Locally you will need a reachable Postgres instance pointed to by `DATABASE_URL` (e.g., `postgres://user:pass@host:5432/dbname`).
- Vercel serverless cold starts and connection reuse: prefer short-lived DB connections or implement connection pooling if you add higher volume/parallelism.

Local dev and testing tips (discoverable from files):
- Install deps: `pip install -r requirements.txt`.
- Set env vars before running/tests: `PANDASCORE_API_KEY`, `DATABASE_URL`, (optional) `cron_secret`.
- You can test the handler by invoking a GET request against the Vercel deployment path `/api` or by running a small local wrapper that instantiates `HTTPServer` with the provided `handler` class. Alternatively use `vercel dev` to emulate Vercel locally (not present in repo).

Examples to reference when changing logic:
- API call: `https://api.pandascore.co/csgo/matches/upcoming?sort=-scheduled_at&per_page=50` (see `api/index.py`).
- Table schema: `matches (id INTEGER PRIMARY KEY, team1_name VARCHAR(255), team2_name VARCHAR(255), scheduled_at TIMESTAMP WITH TIME ZONE, league_name VARCHAR(255), raw_data JSONB, inserted_at TIMESTAMP WITH TIME ZONE DEFAULT NOW())` — keep compatibility if other services read this table.

If you update behavior, also update these places:
- `requirements.txt` when adding/removing packages.
- `vercel.json` if you change the route or add additional serverless functions.

If something is unclear or you need expanded guidance (local runner snippet, tests, or DB migrations), tell me which part you want and I will add a concrete change (example: small local `dev_server.py` or a unit test that mocks requests and a test database).

Notes:
- No existing `.github/copilot-instructions.md` was found before this file was added. README.md is minimal.
- Keep edits minimal and explicitly note DB schema or API contract changes in this file.

Please review and tell me which section to expand or correct (local-run example, test harness, or DB migration plan).
