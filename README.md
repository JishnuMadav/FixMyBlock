# FixMyBlock

An AI-assisted campus maintenance app built for a hackathon demo at NITK Surathkal. Students describe a problem, review a clear report, and track it through repair.

**Independent student project — not an official NITK service.** Starter tickets are fictional.

## What it does

- Understands informal complaints, asks for missing details, and prepares a report.
- Supports optional photos with Gemini analysis.
- Checks existing tickets and asks before linking a possible duplicate.
- Lets students correct details or cancel before submitting.
- Includes a campus map, report pins, and Google Maps links.
- Provides separate student, maintenance-team, and admin dashboards.
- Lets maintenance teams update progress and students confirm repairs.

## Where AI helps

Gemini interprets complaint text and photos and compares the meaning of possible duplicate reports. The database filters candidates by location and category. LangGraph coordinates interpretation, clarification, duplicate checking, and saving.

Backend rules validate actions and permissions. **AI does not submit reports without user confirmation.** This project uses prompting and workflow controls, not a fine-tuned model. Without a Gemini key, it runs a limited, labelled keyword-based demo.

## Tech stack

| Part | Technology |
| --- | --- |
| Frontend | Next.js, React, TypeScript |
| Backend | Python, FastAPI |
| AI workflow | Gemini API, LangGraph |
| Storage | SQLite |
| Authentication | WorkOS email codes; local admin-managed team accounts |
| Maps | Leaflet, OpenStreetMap, Google Maps links |

## Run locally

Requirements: **Node.js 20.9+** and **Python 3.12**. Commands below use Windows PowerShell.

```powershell
git clone https://github.com/JishnuMadav/FixMyBlock.git
cd FixMyBlock
npm ci
python -m venv .venv
.venv/Scripts/python -m pip install -r requirements.lock.txt
Copy-Item .env.example .env
```

Edit `.env`:

| Variable | Value |
| --- | --- |
| `GEMINI_API_KEY` | Your Gemini API key; leave blank for basic demo rules |
| `GEMINI_MODEL` | Exact model ID available to your account; required when using Gemini |
| `AUTH_REQUIRED` | `true` for student and staff sign-in |
| `WORKOS_API_KEY` | Your WorkOS API key |
| `WORKOS_CLIENT_ID` | Your WorkOS Client ID |
| `COOKIE_SECURE` | `false` for local HTTP; `true` for public HTTPS |
| `PUBLIC_ORIGIN` | Leave blank locally; set the exact HTTPS origin when hosting |

Enable Magic Auth and email delivery in your WorkOS project. Student login accepts exact `@nitk.edu.in` addresses and verifies a six-digit email code. It verifies email ownership, not enrollment status.

For a **local-only demo without WorkOS**, set `AUTH_REQUIRED=false` and keep `PUBLIC_ORIGIN` empty. Do not expose that mode publicly.

Start the backend:

```powershell
.venv/Scripts/python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

In another terminal, start the frontend:

```powershell
npm run dev
```

Open [localhost:3000](http://localhost:3000). Keep both terminals running. Restart the backend after changing `.env`.

## Create the administrator

With authentication enabled, run:

```powershell
.venv/Scripts/python -m backend.create_admin
```

The initial user ID is `fmb-admin`. Its generated temporary password is saved privately in `data/admin-credentials.txt`. Choose **Maintenance / Admin** on the sign-in screen and change the password at first login. Remove the credential file after changing it.

The admin can create, reset, and disable maintenance-team accounts. Teams can access only their assigned work. The four teams are Electrical, Sanitation, Grounds, and Plumbing.

## Quick demo

1. Report: **“There is water all over the floor outside Hostel 1.”**
2. Answer the clarification: **“It is coming from a broken pipe.”**
3. Review the description and location, then submit.
4. Sign in as the plumbing team and mark the report **In progress**.
5. After repair, request verification; the reporting student can confirm or reopen it.

To demonstrate duplicate reasoning, compare **“The lamp at the rear gate of Hostel 3 is still out”** with **“The third-floor bathroom lamp inside Hostel 3 is broken, not the rear gate light.”** Keep the fictional rear-gate ticket open for this demo. AI outputs can vary; rehearse before presenting.

## Tests

```powershell
.venv/Scripts/python -m pytest -q
npm run build
```

The automated suite uses isolated databases and mocks external services. It tests access control, report lifecycle, duplicate confirmation, corrections, cancellation, photo/pin review, and AI error handling. These are software tests, not a model-accuracy benchmark. Live Gemini checks require a configured account and available quota.

## Sharing a laptop demo

```powershell
npm run build
npm run start -- --port 3100
```

Keep FastAPI running on port 8000. Forward an HTTPS tunnel to `http://127.0.0.1:3100`, set `PUBLIC_ORIGIN` to its exact origin, set `COOKIE_SECURE=true`, and restart FastAPI. Public hosting requires `AUTH_REQUIRED=true` and configured WorkOS credentials.

Keep the laptop awake and online. Temporary tunnel URLs can expire or change; update `PUBLIC_ORIGIN` when they do. No temporary demo URL is hard-coded in this repository.

## Privacy and limits

- Never commit `.env`, API keys, passwords, databases, or uploaded photos. `.env.example` contains only blank placeholders and local defaults.
- Complaint text, candidate ticket details, and optional photos are sent to Gemini when configured. Avoid personal information and faces.
- Gemini needs internet access and has usage limits. Failed AI requests do not silently fall back to rules or submit a ticket.
- Campus landmarks are approximate. OpenStreetMap tiles require internet; Google Maps opens through links, without a Google Maps API key.
- This app is not an emergency service and does not dispatch real maintenance crews. Follow-up suggestions are recorded locally, not sent as email or SMS.
- SQLite data stays on the host machine. This is a hackathon prototype, not a managed production deployment.

## Project structure

```text
app/          Frontend, maps, sign-in, and dashboards
backend/      API, AI workflow, authentication, and database
shared/       Campus landmarks and demo map bounds
tests/        Automated regression tests
data/         Local runtime data — excluded from Git
```
