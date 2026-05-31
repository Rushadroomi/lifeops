# LifeOps — Complete Setup Guide

---

## Project Structure

After cloning the repo, your folder should look like this:

```
lifeops/
├── backend/
│   ├── main.py           ← FastAPI app (security hardened)
│   ├── dashboard.html    ← Production dashboard
│   ├── requirements.txt
│   ├── Dockerfile
│   └── init.sql          ← DB schema (auto-runs on first start)
├── workflows/
│   └── lifeops_workflow.json   ← Import this into n8n
├── docker-compose.yml
├── .env.example
├── .env                  ← YOU create this (never commit it)
├── .gitignore
└── README.md
```

---

## Step 1 — Create Your `.env` File

Copy the example and fill in your values:

```powershell
Copy-Item .env.example .env
notepad .env
```

Fill in every field:

```env
DB_PASSWORD=PickAStrongPassword123!
LIFEOPS_API_KEY=<generate below>
N8N_USER=your@email.com
N8N_PASSWORD=YourN8nPassword123
N8N_PUBLIC_URL=https://your-tunnel.trycloudflare.com
```

**Generate a secure API key** (run in PowerShell):

```powershell
-join ((48..57 + 65..90 + 97..122) | Get-Random -Count 40 | % {[char]$_})
```

Copy the output and paste it as your `LIFEOPS_API_KEY`. Keep it secret — it protects all backend endpoints.

**Get a free Cloudflare Tunnel URL** for `N8N_PUBLIC_URL`:

```powershell
# Install cloudflared if you don't have it:
# https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/downloads/

cloudflared tunnel --url http://localhost:5678
```

Copy the `https://....trycloudflare.com` URL it prints and use that as `N8N_PUBLIC_URL`. Note: free tunnel URLs change every time you restart cloudflared.

---

## Step 2 — Pull Ollama Models

Make sure Ollama is running on your machine, then pull the required models:

```powershell
ollama pull mistral:latest
ollama pull qwen2.5:7b
```

---

## Step 3 — Start Everything

From inside your project folder:

```powershell
docker compose up --build -d
```

This starts three containers:

| Container | What it does | Port |
|---|---|---|
| `lifeops_db` | PostgreSQL database | internal only |
| `lifeops_backend` | FastAPI + dashboard | 8000 |
| `lifeops_n8n` | n8n automation | 5678 |

Check they are all running:

```powershell
docker compose ps
```

All three should show `Up` / `healthy` status. If n8n shows `Up X seconds` it is still starting — wait 20 seconds and check again.

---

## Step 4 — Create the n8n Database

n8n needs its own database inside Postgres. Run this once:

```powershell
docker exec -it lifeops_db psql -U postgres -c "CREATE DATABASE n8n_db;"
docker compose restart n8n
```

---

## Step 5 — Verify the Backend

```
http://localhost:8000/health
```

Should return: `{"status":"ok","timestamp":"..."}`

Explore all endpoints at:

```
http://localhost:8000/api/docs
```

---

## Step 6 — Open the Dashboard

```
http://localhost:8000/dashboard?key=YOUR_LIFEOPS_API_KEY
```

Replace `YOUR_LIFEOPS_API_KEY` with the value from your `.env`. The key is saved in your browser session automatically — you only need `?key=...` on the first visit per session.

---

## Step 7 — Import the Workflow into n8n

1. Open `http://localhost:5678`
2. Log in with `N8N_USER` and `N8N_PASSWORD` from your `.env`
3. Click **Workflows** → **Import from File**
4. Select `workflows/lifeops_workflow.json`
5. The workflow will open — do **not** activate it yet

---

## Step 8 — Post-Import Configuration

This is the most important step. You must update four things before activating.

---

### 8a — Update Your Google Calendar ID

Every Google Calendar node in the workflow has a hardcoded calendar ID that belongs to the original author. You must replace it with your own.

**Find your Calendar ID:**
1. Open [Google Calendar](https://calendar.google.com)
2. Next to your calendar name, click **⋮ → Settings and sharing**
3. Scroll down to **Integrate calendar**
4. Copy the **Calendar ID** (looks like `abc123@group.calendar.google.com` or your Gmail address for the primary calendar)

**Update in n8n:**
- In the workflow, click any Google Calendar node
- Change the calendar field to your Calendar ID
- Repeat for all calendar nodes (there are approximately 10)

> 💡 Tip: Use **Ctrl+F** in n8n to search for nodes by name — search "calendar" to find them all quickly.

---

### 8b — Update HTTP Request Nodes

All HTTP nodes that call the backend need two changes: a new URL and an API key header.

**Nodes to update:**

| Node name | Old URL | New URL |
|---|---|---|
| HTTP Sync API | `http://host.docker.internal:8000/sync-events` | `http://backend:8000/sync-events` |
| Upsert Events | `http://host.docker.internal:8000/sync-events` | `http://backend:8000/sync-events` |
| Delete Sync Check | `http://host.docker.internal:8000/sync-delete-check` | `http://backend:8000/sync-delete-check` |
| Fetch Weekly Data | `http://host.docker.internal:8000/weekly-summary` | `http://backend:8000/weekly-summary` |
| HTTP Request | `http://host.docker.internal:8000/save-ai-insight` | `http://backend:8000/save-ai-insight` |

**For each node above, also add this header:**

1. Open the node
2. Go to **Headers** (or **Options → Add Header**)
3. Add:

| Name | Value |
|---|---|
| `X-API-Key` | `{{ $env.LIFEOPS_API_KEY }}` |

Using `$env.LIFEOPS_API_KEY` means n8n reads it from the Docker environment — the key never appears hardcoded in your workflow.

---

### 8c — Update the Gmail Reminder Recipient

In the workflow, find the node named **"Send a message"** inside the reminders flow (connected after the `If` node on the Schedule Trigger branch).

- Open the node
- Change the `sendTo` field from the original email to **your own Gmail address**

---

### 8d — Set Up Credentials

For each service, go to **Credentials** in n8n and create a new credential:

| Service | Credential type | What you need |
|---|---|---|
| Google Calendar | Google Calendar OAuth2 | Google Cloud OAuth client |
| Gmail | Gmail OAuth2 | Same Google Cloud project |
| Telegram | Telegram API | Bot token from @BotFather |
| PostgreSQL | Postgres | Host: `db`, DB: `events_db`, User: `postgres`, Password: from `.env` |
| Ollama | Ollama API | URL: `http://host.docker.internal:11434` |
| OpenRouter | OpenRouter API | API key from openrouter.ai |
| Google Gemini | Google PaLM API | API key from Google AI Studio |

Once credentials are created, assign them to each node that requires them.

---

## Step 9 — Activate the Workflow

Once all nodes are configured:

1. Click **Save** (top right)
2. Toggle the workflow to **Active**
3. Send a message to your Telegram bot to test

**Test message:**
> "Schedule a 1 hour study session tomorrow at 3pm"

You should receive a reply from the bot and see the event appear in your Google Calendar.

---

## Step 10 — Set Up Cloudflare Tunnel (for webhooks)

Telegram and Gmail triggers require a public URL to send events to n8n. Run cloudflared in a separate PowerShell window:

```powershell
cloudflared tunnel --url http://localhost:5678
```

Copy the printed URL (e.g. `https://abc-xyz.trycloudflare.com`) and update `N8N_PUBLIC_URL` in your `.env`, then restart n8n:

```powershell
docker compose restart n8n
```

> Note: Free Cloudflare tunnel URLs are temporary and change every restart. For a permanent URL, set up a [named tunnel](https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/get-started/) with a free Cloudflare account.

---

## Useful Commands

```powershell
# View logs
docker compose logs -f           # all services
docker compose logs -f backend   # just the backend
docker compose logs -f n8n       # just n8n

# Restart a service
docker compose restart n8n
docker compose restart backend

# Stop everything (data preserved)
docker compose down

# Start again
docker compose up -d

# Rebuild after code changes
docker compose up --build -d

# Full reset (WARNING: deletes all data)
docker compose down -v
docker compose up --build -d
```

---

## Security Notes

| What was hardened | How |
|---|---|
| DB password | Loaded from `DB_PASSWORD` env var — never in code |
| All API endpoints | Protected by `X-API-Key` header |
| CORS | Restricted to n8n origin only (not `*`) |
| Missing secrets | App refuses to start if `DB_PASSWORD` or `LIFEOPS_API_KEY` are not set |
| `limit` parameter abuse | Capped at 100 |
| Docker networking | Backend uses `db` service name, not `localhost` |

---

## Troubleshooting

**n8n shows `ERR_EMPTY_RESPONSE`:**
It is still starting. Wait 20–30 seconds and refresh. If it persists, run `docker compose logs n8n` — most likely the `n8n_db` database doesn't exist yet (see Step 4).

**Backend fails to start:**
Run `docker compose logs backend`. Almost always means `DB_PASSWORD` or `LIFEOPS_API_KEY` is missing or empty in `.env`.

**n8n workflow can't reach backend:**
Use `http://backend:8000` (Docker service name) inside n8n nodes — not `http://localhost:8000`. `localhost` inside a container refers to that container itself, not your host.

**Dashboard shows 403 Forbidden:**
The `X-API-Key` in your URL doesn't match `LIFEOPS_API_KEY` in `.env`. Check for extra spaces or line breaks when copying.

**Ollama not reachable from n8n:**
Make sure Ollama is running on your Windows host (`ollama serve`). The `host.docker.internal` hostname is automatically mapped by the `extra_hosts` entry in docker-compose.

**Telegram bot not responding:**
Check that cloudflared is running and `N8N_PUBLIC_URL` in `.env` matches the current tunnel URL. Restart n8n after any URL change.

**Google Calendar events not appearing:**
Confirm you updated the Calendar ID in all calendar nodes to your own (Step 8a). The original calendar ID in the workflow belongs to the author and you have no access to it.

**DB schema not created:**
`init.sql` only runs on a completely fresh volume. If you started the DB before with a different setup, run:
```powershell
docker compose down -v   # WARNING: deletes all data
docker compose up -d
```
