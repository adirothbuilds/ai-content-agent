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

The service emits structured JSON logs and attaches `X-Request-ID`, `X-Trace-ID`, and `X-Run-ID` headers to HTTP responses. Incoming `X-Request-ID` values are preserved when provided by the caller.

## GitHub Token Setup

The GitHub activity tooling reads from the authenticated GitHub API using `GITHUB_TOKEN` and scopes activity to `GITHUB_USERNAME`.

Recommended token setup:

- Use a fine-grained personal access token.
- Grant access only to the repositories you want the app to inspect.
- Enable these repository permissions:
  - `Metadata: Read`
  - `Contents: Read`
  - `Pull requests: Read`
  - `Issues: Read`

Notes:

- If you want activity from private repositories, the token must be granted access to those private repositories explicitly.
- Public-only activity can be tested with access limited to public repositories.
- The current GitHub activity layer reads commits, pull requests, merged pull requests, and issues for the configured GitHub user.

## Docker Compose

For containerized deployment, the repo now includes two Compose modes:

- `dev`: `mongodb` + `server`
- `prod`: `mongodb` + `server` + `cloudflared`

```bash
cp .env.example .env
docker compose --profile dev up --build
```

For the production-style stack with Cloudflare Tunnel:

```bash
docker compose --profile prod up --build
```

Notes:

- `server` reads the same `.env` file as local development and expects `MONGODB_URI=mongodb://mongodb:27017`.
- `mongodb` is available on the internal Compose network as `mongodb` and is also published locally on port `27017`.
- Use the `dev` profile for local development when you do not need a public tunnel.
- Use the `prod` profile only with a real `CLOUDFLARED_TUNNEL_TOKEN` and `PUBLIC_BASE_URL`.
- The current bootstrap verifies startup configuration and serves `GET /health` on port `8000`.
