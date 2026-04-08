# 🎥 Technical Video Intelligence Bot

> Upload a long meeting recording or YouTube tutorial → get structured Markdown notes + Jira-ready JSON in minutes.

**Pipeline:** `Video/YouTube` → `Whisper STT` → `GPT-4o Vision Analysis` → `Distiller` → `Markdown + Jira JSON`

---

## 📋 Table of Contents
1. [Project Structure](#project-structure)
2. [Prerequisites](#prerequisites)
3. [Local Setup (Manual)](#local-setup)
4. [Run with GitHub Copilot — Step by Step](#github-copilot-workflow)
5. [API Reference](#api-reference)
6. [Running Tests](#running-tests)
7. [Deploy](#deploy)
8. [Environment Variables](#environment-variables)

---

## Project Structure

```
video-intel-bot/
├── backend/
│   ├── main.py                    # FastAPI app + pipeline orchestrator
│   └── agents/
│       ├── ingestor.py            # Agent 1: Video download + frame extraction
│       ├── transcriber.py         # Agent 2: OpenAI Whisper transcription
│       ├── analyzer.py            # Agent 3: GPT-4o vision + transcript analysis
│       ├── distiller.py           # Agent 4: Enrich + deduplicate
│       └── output_generator.py    # Agent 5: Markdown + Jira JSON
├── tests/
│   └── test_pipeline.py           # pytest test suite
├── .github/
│   ├── workflows/ci.yml           # GitHub Actions CI/CD
│   └── copilot-instructions.md    # Copilot context file
├── .vscode/settings.json          # VS Code + Copilot settings
├── .env.example                   # Copy → .env and fill in keys
├── docker-compose.yml
├── Dockerfile.backend
└── README.md
```

---

## Prerequisites

| Tool | Version | Install |
|------|---------|---------|
| Python | 3.10+ | [python.org](https://python.org) |
| ffmpeg | Any | `brew install ffmpeg` / `apt install ffmpeg` |
| Node.js (optional, for frontend) | 18+ | [nodejs.org](https://nodejs.org) |
| Docker (optional) | 24+ | [docker.com](https://docker.com) |
| OpenAI API Key | — | [platform.openai.com](https://platform.openai.com) |

---

## Local Setup

```bash
# 1. Clone the repo
git clone https://github.com/careerbytecode/video-intel-bot
cd video-intel-bot

# 2. Create virtual environment
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate

# 3. Install dependencies
pip install -r backend/requirements.txt

# 4. Copy env file and add your OpenAI key
cp .env.example .env
# Edit .env → set OPENAI_API_KEY=sk-proj-...

# 5. Run the backend
cd backend
uvicorn main:app --reload --port 8000

# 6. Open in browser
# API docs: http://localhost:8000/docs
# Health:   http://localhost:8000/health
```

---

## 🤖 GitHub Copilot Workflow — Step by Step

### Step 0 — Install GitHub Copilot

1. Open **VS Code**
2. Press `Ctrl+Shift+X` → search **"GitHub Copilot"** → Install
3. Sign in with your GitHub account
4. Confirm subscription at [github.com/features/copilot](https://github.com/features/copilot)

> The `.github/copilot-instructions.md` file in this repo automatically gives Copilot context about the project architecture.

---

### Step 1 — Open the Project in VS Code

```bash
# After cloning:
code video-intel-bot
```

VS Code will detect `.vscode/settings.json` and configure Python + Copilot automatically.

---

### Step 2 — Set Up Environment with Copilot Chat

1. Open **Copilot Chat** → `Ctrl+Alt+I` (Windows) or `Cmd+Shift+I` (Mac)
2. Type this prompt:

```
@workspace Set up this project for me. 
Create the virtual environment, install requirements, 
and verify ffmpeg is installed. Show me the commands.
```

Copilot will generate the exact setup commands for your OS.

---

### Step 3 — Configure API Keys

1. In Copilot Chat, type:
```
Help me create a .env file from .env.example 
and explain what each variable does.
```

2. Copilot will walk you through each required key.
3. Paste your `OPENAI_API_KEY` into `.env`

---

### Step 4 — Run Tests First (TDD)

Open the integrated terminal (`Ctrl+`` `) and run:

```bash
# Activate venv
source .venv/bin/activate

# Run all tests
pytest tests/ -v

# Expected output:
# tests/test_pipeline.py::test_health PASSED
# tests/test_pipeline.py::test_markdown_contains_title PASSED
# ... 15 tests should pass
```

**Using Copilot to understand a failing test:**
```
/explain  # Select a failing test and type /explain in Copilot Chat
```

---

### Step 5 — Start the Backend Server

```bash
cd backend
uvicorn main:app --reload --port 8000
```

You should see:
```
INFO:     Uvicorn running on http://0.0.0.0:8000
INFO:     Application startup complete.
```

---

### Step 6 — Test the API with Copilot

1. Open `http://localhost:8000/docs` (Swagger UI auto-generated)
2. In Copilot Chat:
```
Generate a curl command to test the /process/youtube endpoint 
with this URL: https://www.youtube.com/watch?v=dQw4w9WgXcQ
```

Copilot will generate:
```bash
curl -X POST http://localhost:8000/process/youtube \
  -H "Content-Type: application/json" \
  -d '{"url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ"}'
```

3. Poll the job status:
```bash
# Use the job_id from the response above
curl http://localhost:8000/jobs/{job_id}
```

---

### Step 7 — Use Copilot Inline to Extend the Code

**Example: Add a new agent using Copilot inline suggestions**

1. Create a new file `backend/agents/jira_pusher.py`
2. Type this comment and let Copilot complete it:

```python
# JiraPusher: Takes the jira_payload from OutputGenerator
# and actually POSTs it to the Jira REST API v3
# Uses JIRA_BASE_URL, JIRA_EMAIL, JIRA_API_TOKEN from env
# Method: async def push(self, jira_payload: dict) -> list[str]  # returns created issue keys

class JiraPusher:
    # Copilot will complete the rest...
```

Press `Tab` to accept each suggestion.

---

### Step 8 — Ask Copilot to Write Tests

In Copilot Chat:
```
@workspace Write pytest tests for the JiraPusher class I just created.
Mock the httpx calls. Test: successful creation, auth failure, and network error.
```

---

### Step 9 — Run with Docker (optional)

```bash
# Build and run everything
docker-compose up --build

# Check health
curl http://localhost:8000/health
```

---

### Step 10 — Push to GitHub and Watch CI Run

```bash
git add .
git commit -m "feat: add Technical Video Intelligence Bot"
git push origin main
```

Go to **GitHub → Actions tab** → Watch the CI pipeline:
- ✅ Backend Tests
- ✅ Lint (Ruff)
- ✅ Docker Build
- ✅ Deploy (on main branch)

---

## API Reference

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/health` | Health check |
| `POST` | `/process/youtube` | Process a YouTube URL |
| `POST` | `/process/upload` | Upload a video file |
| `GET` | `/jobs/{job_id}` | Poll job status |
| `GET` | `/jobs/{job_id}/stream` | SSE stream of stage updates |

### Process YouTube — Request
```json
POST /process/youtube
{
  "url": "https://www.youtube.com/watch?v=...",
  "title": "optional custom title"
}
```

### Job Status Response
```json
{
  "job_id": "uuid",
  "status": "queued | running | done | error",
  "stage": "ingest | transcribe | analyze | distill | output | complete",
  "progress": 0,
  "result": {
    "markdown": "# Meeting Notes...",
    "jira_json": { "issues": [...] },
    "decisions_found": 5,
    "action_items_found": 8
  }
}
```

---

## Running Tests

```bash
# All tests
pytest tests/ -v

# With coverage
pytest tests/ -v --cov=backend --cov-report=term-missing

# Single test file
pytest tests/test_pipeline.py -v

# Single test
pytest tests/test_pipeline.py::test_jira_json_structure -v

# Watch mode (install pytest-watch)
ptw tests/
```

---

## Deploy

### Railway (recommended)
```bash
npm install -g @railway/cli
railway login
railway init
railway up
railway variables set OPENAI_API_KEY=sk-proj-...
```

### Render
1. Connect GitHub repo at render.com
2. Build command: `pip install -r backend/requirements.txt`
3. Start command: `uvicorn main:app --host 0.0.0.0 --port $PORT`
4. Add env vars in Render dashboard

### Docker
```bash
docker build -f Dockerfile.backend -t video-intel-bot .
docker run -p 8000:8000 -e OPENAI_API_KEY=sk-proj-... video-intel-bot
```

---

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `OPENAI_API_KEY` | ✅ Yes | OpenAI API key (Whisper + GPT-4o) |
| `JIRA_BASE_URL` | Optional | e.g. `https://yourco.atlassian.net` |
| `JIRA_EMAIL` | Optional | Your Atlassian account email |
| `JIRA_API_TOKEN` | Optional | Generate at id.atlassian.com |
| `JIRA_PROJECT_KEY` | Optional | Default project key e.g. `TECH` |

---

## Troubleshooting

**`ffmpeg: command not found`**
```bash
# macOS
brew install ffmpeg
# Ubuntu/Debian
sudo apt install ffmpeg
# Windows — download from ffmpeg.org and add to PATH
```

**`yt-dlp: Unable to download`**
```bash
pip install --upgrade yt-dlp
```

**OpenAI 429 Rate Limit**
- The free tier has low limits. Upgrade to Tier 1 at platform.openai.com/account/limits

---

*Built for Live Session — Learning Made Simple 🚀*
