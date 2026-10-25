# Local setup

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

## Verification

```powershell
.venv/Scripts/python -m pytest -q
npm run build
```

Keep API keys and local credentials in `.env`; never commit them.
