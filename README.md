# FixMyBlock

A local campus-maintenance prototype with a Next.js interface, FastAPI + SQLite backend, and a LangGraph workflow. Gemini is optional; the application visibly labels its deterministic demo mode when no key is configured.

## Run on Windows

Requirements: Node.js 20.9+ and Python 3.11+.

```powershell
git clone https://github.com/JishnuMadav/FixMyBlock.git
cd FixMyBlock
python -m venv .venv
.venv/Scripts/python -m pip install -r requirements.lock.txt
npm ci
Copy-Item .env.example .env
```

Open two terminals in this directory:

```powershell
# Terminal 1
.venv/Scripts/python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

```powershell
# Terminal 2
npm run dev
```

Visit http://localhost:3000. Keep both terminals running. Ctrl+C stops each server. Next.js proxies /api requests to FastAPI on port 8000.

## Enable Gemini

Copy `.env.example` to `.env` and set `GEMINI_API_KEY` in that file (never in browser code or chat). Set `GEMINI_MODEL` to a tool/structured-output-capable model available to your account; the default is `gemini-3.8-flash`. Restart the Python server. The interface shows whether the server is configured for Gemini or demo rules; a configured key does not guarantee API access. Model failures return an explicit error, roll back ticket mutations, and can be retried. No live model call was needed to run the demo.

Gemini receives complaint text, relevant candidate tickets, and submitted maintenance notes. Avoid private information in this prototype. Logs do not print the API key. `.env` and the SQLite database are ignored by Git.

## Student sign-in with WorkOS

Student sign-in is enabled by default. In the [WorkOS dashboard](https://dashboard.workos.com), choose your environment, enable **Magic Auth** in Authentication, and leave WorkOS email delivery enabled. Copy its API key and Client ID into the existing `.env` placeholders:

```dotenv
AUTH_REQUIRED=true
WORKOS_API_KEY=your_workos_api_key
WORKOS_CLIENT_ID=your_workos_client_id
WORKOS_OPERATOR_EMAILS=
COOKIE_SECURE=false
```

Restart FastAPI after configuring them. Never put the API key in `NEXT_PUBLIC_` variables or commit `.env`. The custom email/code UI calls the WorkOS Magic Auth API through FastAPI; no OAuth callback is needed for this flow. Missing credentials leave login locked with a setup message rather than admitting anonymous users.

Only exact `@nitk.edu.in` addresses are accepted on the server. WorkOS sends and verifies a six-digit code, valid for 10 minutes. Sending is limited to once per address per minute; verification attempts are limited by address and IP. WorkOS responses containing codes and tokens never reach the browser or application logs. Real inbox delivery must be tested after credentials are configured.

Verified users receive an opaque HttpOnly, SameSite cookie with an eight-hour absolute lifetime. Only its hash is stored; sign-out revokes the local session. Sign in again when it expires. Reports use the stable WorkOS user ID, so they persist across logins and devices. Older anonymous demo reports stay in the database without being assigned to an unverified account. This verifies email ownership, not enrollment status.

The maintenance queue requires a verified email explicitly listed in `WORKOS_OPERATOR_EMAILS` (comma-separated). Students cannot enable operator access using the old demo cookie. Set `COOKIE_SECURE=true` behind HTTPS before deployment. The current server still accepts only localhost hosts/origins. These local sessions expire independently of WorkOS dashboard session revocation; centralized revocation/webhooks are not implemented.

For isolated offline demonstrations only, `AUTH_REQUIRED=false` restores the old anonymous session mode. Keep that mode on localhost.

## What works

- Report intake with category/location clarification.
- Interactive NITK campus map, 12 searchable landmarks, draggable report pins, and optional location details.
- Saved coordinates and nearby duplicate candidates within 120 metres; Gemini compares the complaint with those candidates before suggesting a link.
- Google Maps links for selected locations (no Google Maps API key required).
- Explicit review before ticket creation; confirmation before duplicate linking.
- Gemini structured interpretation and candidate comparison when configured.
- LangGraph conditional workflow; conversation state persisted between turns in SQLite.
- Idempotent chat requests; repeated submit requests do not create extra tickets.
- Real database tickets, resident subscriptions, activity history, and personal reports.
- Operator work queue, validated status transitions, and required work notes.
- Resident-only resolution confirmation and reopening.
- A 60-second background deadline monitor while FastAPI runs.
- Manual demo-clock advancement; context-aware follow-up suggestions and operator approval.
- Responsive interface with keyboard-accessible native dialogs and error recovery.

## Demo walkthrough

1. Choose a location on the map, such as E-Library, and add a detail such as “Near the entrance — fictional demo.” Describe a broken streetlight, review, and submit.
2. Start a new report for the same broken streetlight at the same pin. Review the possible duplicate and confirm the link. Only one repair ticket is needed.
3. Open Work queue (explicit local operator demo), open that ticket, add a note, and start work.
4. Add “The crew could not find the location” and select Suggest next step. Review and approve the location follow-up. It is recorded in the local queue; no message is sent externally.
5. Add a completion note and request repair verification. Open My reports and confirm the fix or reopen it.
6. Advance demo time by 24 hours to flag overdue work. The offset is for deadline demonstrations only; activity timestamps remain real time.

## Important limits

This is an independent single-machine demonstration, not an official NITK reporting service. All ten starter tickets are fictional: six original examples and four mapped campus examples. Existing records are preserved without inventing coordinates. No municipal system, real maintenance crew, email, or SMS integration is connected. Approved follow-ups become queue items; they do not contact anyone. Team reassignment is not implemented in this first version.

The map uses Leaflet and OpenStreetMap tiles, which require an internet connection. Google Maps opens through location links, not an embedded Google Maps SDK. Approximate landmark coordinates and source links are in `shared/campus.json`, retrieved on 24 October 2026. The rectangular selection area is a demo constraint, not an official campus boundary. Sample incident pins do not assert real faults at these places. Map attribution remains visible.

With student sign-in enabled, all report API access requires a verified session and maintenance mutations require an approved operator. The optional anonymous offline mode uses an insecure demo operator switch and must stay local. Deployment additionally needs HTTPS, configured hosts/origins, data retention policies, and operational monitoring. Campus reports are visible to all signed-in users; email addresses are not added to report payloads.

Demo rules only support English keywords and the supplied locations. Gemini mode is designed to improve ambiguous input and contextual comparisons, but requires evaluation with a live key. A saved chat can resume through its conversation ID at the API; the current UI starts a new conversation on page reload. Tickets remain saved.

## Public demo hosting

Use a production build for a shared demo:

```powershell
npm run build
npm run start -- --port 3100
```

Run FastAPI separately as described above. A Cloudflare Tunnel can forward an HTTPS address to `http://127.0.0.1:3100`. Set `PUBLIC_ORIGIN` in `.env` to the exact HTTPS origin (no path), set `COOKIE_SECURE=true`, and restart FastAPI. Keep `AUTH_REQUIRED=true` and configure WorkOS first. The backend rejects public hosting without configured authentication. Only the configured origin is added to the local origin allowlist. A temporary tunnel URL changes when a new tunnel is created; update `PUBLIC_ORIGIN` and restart the backend each time.

Keep the laptop awake and online. This is a prototype, not a managed production deployment. Never publish `.env`, database files, logs, or dependency/build folders. The repository includes only a blank environment template; configure your own credentials after cloning.

## Verification

```powershell
.venv/Scripts/python -m pytest -q
npm run build
npm run typecheck
```

Tests use temporary databases; they do not modify your demo data. They cover clarification, confirmation, idempotency, duplicate/separate cases, role and ownership checks, completion/reopening, follow-up approval, foreign-origin rejection, model-failure rollback, coordinate storage, nearby filtering, invalid pins, changed-pin review, and repeatable campus migration.

## Structure

```text
app/page.tsx          Resident and maintenance UI
app/campus-map.tsx    Interactive map and location picker
app/globals.css       Responsive visual system
shared/campus.json    Sourced landmarks and demo area
backend/geo.py       Distance and location helpers
backend/main.py      API, access gates, follow-up monitor
backend/agent.py     LangGraph nodes and Gemini adapter
backend/db.py        SQLite schema, seed records, audit history
tests/               Isolated integration tests
data/                Local runtime database (ignored)
```
