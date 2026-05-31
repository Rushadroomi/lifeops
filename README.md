# 🤖 LifeOps — AI-Powered Life Management System

> A fully automated personal productivity system built with **n8n**, powered by AI agents, that manages your schedule, reminders, emails, and weekly analytics — all through Telegram.

---

## 🧠 What Is LifeOps?

LifeOps is an intelligent automation system that acts as your personal AI chief-of-staff. You talk to it on Telegram, and it handles everything: creating your schedule, rescheduling missed tasks, parsing emails for events, sending reminders, and delivering a weekly productivity report — automatically.

---

## ✨ Features

### 📅 AI Scheduling Agent
- Chat with the bot on Telegram to create study plans, fitness routines, or any custom plan
- AI classifies your intent (study / fitness / general / multi-day plans) and routes it to the right pipeline
- Generates 10–15 sessions with titles, descriptions, and smart durations
- Finds free slots in your Google Calendar and schedules events automatically
- Respects deep work limits (max 2-hour blocks), adds buffers, and avoids burnout

### 🔔 Smart Reminders
- Polls your calendar hourly via a scheduled trigger
- AI checks if any event starts within 15–20 minutes
- Sends a friendly email reminder only when needed (no spam)

### 📧 Email-to-Calendar Parser
- Monitors your Gmail inbox every minute
- AI reads emails and extracts event details (title, date, time, location, priority)
- Checks for calendar conflicts before creating events
- Sends a Telegram confirmation when an event is added

### 🔄 Calendar Sync
- Continuously syncs your Google Calendar to a local backend database
- Detects deleted events and cleans them from the database
- Normalizes all event data for downstream analytics

### 📊 Weekly Productivity Report
- Runs every week at midnight
- Fetches and cleans your weekly event data
- AI generates a premium markdown report with:
  - Productivity score (0–100)
  - Category breakdown (Study / Work / Health / Social)
  - Key patterns, bottlenecks, and recommendations
  - Personalized motivational message
- Saves the report to your backend

  <img width="1919" height="1024" alt="image" src="https://github.com/user-attachments/assets/0e15fd88-afeb-4785-bede-3574768b37fe" />


### 💬 Conversational AI (fallback)
- If your message isn't about scheduling, the agent responds as a general assistant
- Maintains conversation memory per user via Postgres

---

## 🛠️ Tech Stack

| Layer | Tools |
|---|---|
| Automation | n8n (self-hosted via Docker) |
| AI Models | Google Gemini, Mistral (Ollama), Qwen 2.5 (Ollama), OpenRouter |
| Messaging | Telegram Bot API |
| Calendar | Google Calendar API |
| Email | Gmail API |
| Memory | PostgreSQL (n8n Postgres Chat Memory) |
| Backend | FastAPI (Dockerised) |
| Dashboard | HTML/JS served by FastAPI |
| Language | JavaScript (n8n Code nodes) |

---

## 🔁 Workflow Architecture

```
Telegram Message
    └──> Intent Classifier (Qwen 2.5)
              ├── study       ──> Study Plan Generator ──> Calendar Scheduler ──> Telegram
              ├── fitness     ──> Fitness Plan Generator ──> Calendar Scheduler ──> Telegram
              ├── other plans ──> General Plan Generator ──> Calendar Scheduler ──> Telegram
              └── other       ──> AI Agent (Gemini + OpenRouter) ──> Telegram

Gmail Trigger
    └──> Email Parser (Mistral) ──> Conflict Check ──> Google Calendar ──> Telegram

Schedule Trigger (hourly)
    └──> Calendar Fetch ──> AI Reminder Agent ──> Gmail

Cron (every minute)
    └──> Google Calendar ──> Normalize ──> Backend DB Sync

Weekly Cron
    └──> Backend Fetch ──> Data Cleaner ──> AI Report (Qwen) ──> Backend Save
```

---

## 📦 Setup

> **Full step-by-step instructions are in [SETUP.md](SETUP.md).** The summary below is for reference.

### Prerequisites

| Requirement | Notes |
|---|---|
| Docker Desktop | Must be running |
| Git | For cloning the repo |
| Ollama | Running locally with `mistral:latest` and `qwen2.5:7b` |
| Telegram Bot Token | Create via [@BotFather](https://t.me/BotFather) |
| Google Calendar OAuth2 | [Google Cloud Console](https://console.cloud.google.com) |
| Gmail OAuth2 | Same Google Cloud project |
| Google Gemini API key | [Google AI Studio](https://aistudio.google.com) |
| OpenRouter API key | [openrouter.ai](https://openrouter.ai) |
| Cloudflare Tunnel | Free — needed for n8n webhooks (Telegram, Gmail trigger) |

### Quick Start

```bash
# 1. Clone the repo
git clone https://github.com/YOUR_USERNAME/lifeops.git
cd lifeops

# 2. Create your environment file
cp .env.example .env
# Edit .env with your values (see SETUP.md Step 1)

# 3. Pull Ollama models
ollama pull mistral:latest
ollama pull qwen2.5:7b

# 4. Start everything
docker compose up --build -d

# 5. Open the dashboard
# http://localhost:8000/dashboard?key=YOUR_LIFEOPS_API_KEY
```

### After starting, import the workflow

1. Open n8n at `http://localhost:5678`
2. Log in with your `N8N_USER` / `N8N_PASSWORD` from `.env`
3. Go to **Workflows → Import from File**
4. Select `workflows/lifeops_workflow.json`
5. Follow the **Post-Import Configuration** steps in [SETUP.md](SETUP.md)

---

## ⚙️ Post-Import Configuration

After importing the workflow you must update four things. Full details in SETUP.md — quick reference:

### 1. Google Calendar ID
Every Google Calendar node has a hardcoded calendar ID. Replace it with your own **LifeOps calendar ID**:
- Open Google Calendar → Settings → your calendar → copy the Calendar ID
- Update all calendar nodes in n8n (there are ~10 of them)

### 2. HTTP Request nodes — URL + API Key
All HTTP calls to the backend must be updated:

| Node name | New URL |
|---|---|
| HTTP Sync API | `http://backend:8000/sync-events` |
| Upsert Events | `http://backend:8000/sync-events` |
| Delete Sync Check | `http://backend:8000/sync-delete-check` |
| Fetch Weekly Data | `http://backend:8000/weekly-summary` |
| HTTP Request (insight) | `http://backend:8000/save-ai-insight` |

Add this header to **each** of those nodes:

| Header name | Value |
|---|---|
| `X-API-Key` | `{{ $env.LIFEOPS_API_KEY }}` |

### 3. Gmail reminder recipient
In the **"Send a message"** Gmail node (inside the reminders flow), change the `sendTo` email address to your own.

### 4. Credentials
Set up credentials in n8n for: Google Calendar, Gmail, Telegram, PostgreSQL, Ollama, OpenRouter, Google Gemini.

---

## 🖥️ Dashboard

Once running, open:

```
http://localhost:8000/dashboard?key=YOUR_LIFEOPS_API_KEY
```

The API key is saved in your browser session after the first visit — you won't need to add `?key=...` again in the same session.

The dashboard shows:
- Live event stats and weekly activity chart
- Productivity score (extracted from the weekly AI report)
- Recent activities feed
- AI insight panel
- Add-event form (syncs directly to Google Calendar via n8n)
- Mini calendar with event highlights

---

## 📸 Usage Examples

**Create a study plan:**
> "Make me a study plan for my AI exam next week"

**Add an event:**
> "Schedule a team meeting tomorrow at 3pm for 1 hour"

**Reschedule a missed task:**
> "I skipped my 4pm revision session"

**General question:**
> "What's the best way to study algorithms?"

---

## 🗂️ Project Structure

```
lifeops/
├── backend/
│   ├── main.py           ← FastAPI backend (API key auth, env-based config)
│   ├── dashboard.html    ← Production dashboard UI
│   ├── requirements.txt
│   ├── Dockerfile
│   └── init.sql          ← DB schema (runs automatically on first start)
├── workflows/
│   └── lifeops_workflow.json   ← n8n workflow (import this)
├── docker-compose.yml    ← Spins up postgres + backend + n8n
├── .env.example          ← Copy to .env and fill in your values
├── .env                  ← Your secrets (never committed to git)
├── .gitignore
├── SETUP.md              ← Full setup guide
└── README.md
```

---

## 🗺️ Roadmap

- [ ] Voice message support via Whisper
- [ ] WhatsApp integration
- [ ] Notion/Obsidian sync
- [ ] Sleep tracking integration
- [ ] Multi-user support

---

## 📄 License

MIT License — feel free to fork, extend, and build on top of LifeOps.

---

## 🙋 Author

Built by **Rushad Roomi** — connecting AI, automation, and real-life productivity.

> *"Your life, on autopilot."*
