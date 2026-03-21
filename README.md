# AI Content Agent

AI Content Agent is a Telegram-first, human-in-the-loop system for turning journal entries and GitHub activity into authentic LinkedIn post drafts.

## What It Does

- captures journal entries interactively in Telegram
- syncs user-scoped GitHub activity
- generates 3 grounded post ideas
- drafts, remixes, and finalizes posts with human approval
- uses post history to reduce repeated angles over time

## MVP V1 Stack

- Python 3.11+
- Agno
- FastAPI
- MongoDB with document embeddings
- OpenAI for Journal Assist and Idea Agent
- Gemini for SEO Agent
- Claude for Writer Agent and default Remix Agent
- Cloudflare Tunnel
- Docker Compose
- optional NATS

## Docs

- [PLAN.md](PLAN.md) - product and architecture spec
- [ROADMAP.md](ROADMAP.md) - milestone-based delivery plan
- [.github/ISSUES_MVP_V1.md](.github/ISSUES_MVP_V1.md) - MVP issue backlog for manual GitHub issue creation

## Status

This repo currently contains the MVP V1 planning package and issue backlog. Implementation follows the plan in `PLAN.md`.

## Local Development

Create a Python 3.11+ virtual environment, install the package, and run the API server:

```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env
ai-content-agent
```

The bootstrap service exposes `GET /health`.

All runtime configuration is loaded from `.env`. Missing required values fail at startup with a configuration error.
