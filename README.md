# AI Content Agent

AI Content Agent is a Telegram-first, human-in-the-loop system for turning journal entries and GitHub activity into authentic LinkedIn post drafts.

## What It Does

- captures journal entries interactively in Telegram
- syncs user-scoped GitHub activity
- generates 3 grounded post ideas
- generates writer, SEO, and remix variants through task-specific agents
- uses post history to reduce repeated angles over time

## MVP V1 Stack

- Python 3.11+
- Agno
- FastAPI
- MongoDB with document embeddings
- Task-routed LLM providers via `.env`
- Direct support for OpenAI, OpenAI-compatible APIs, Gemini, and Anthropic
- Cloudflare Tunnel
- Docker Compose
- optional NATS

## Docs

- [PLAN.md](PLAN.md) - product and architecture spec
- [ROADMAP.md](ROADMAP.md) - milestone-based delivery plan
- [.github/ISSUES_MVP_V1.md](.github/ISSUES_MVP_V1.md) - MVP issue backlog for manual GitHub issue creation

## Status

The repo is implemented through milestone 4 / issue `#18`.

Current state:

- Telegram webhook and guided journal flow are implemented
- Journal Assist, Idea, Writer, SEO, and Remix are Agno-backed
- journal entries and GitHub activity are persisted as retrieval-ready MongoDB documents
- publish/finalize flow and Telegram idea-selection workflow are not implemented yet

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

LLM routing is task-centric. Each task picks its own provider and model through `.env`:

- `IDEA_PROVIDER` / `IDEA_MODEL`
- `JOURNAL_ASSIST_PROVIDER` / `JOURNAL_ASSIST_MODEL`
- `SEO_PROVIDER` / `SEO_MODEL`
- `WRITER_PROVIDER` / `WRITER_MODEL`
- `REMIX_PROVIDER` / `REMIX_MODEL`

Supported task providers are `openai`, `openai_compatible`, `gemini`, and `anthropic`.
All task execution goes through Agno; the provider choice is configuration, not a separate non-Agno runtime path.

Provider credentials stay grouped by family:

- `OPENAI_API_KEY`
- `OPENAI_COMPATIBLE_API_KEY`
- `OPENAI_COMPATIBLE_BASE_URL`
- `GEMINI_API_KEY`
- `ANTHROPIC_API_KEY`

Embeddings are also provider-backed. Right now `EMBEDDING_PROVIDER` supports:

- `openai`
- `openai_compatible`

That means journal saves, GitHub normalization, and retrieval all need a real embedding-capable API configuration, not placeholder values, if you want to exercise those paths locally.

The service emits structured JSON logs and attaches `X-Request-ID`, `X-Trace-ID`, and `X-Run-ID` headers to HTTP responses. Incoming `X-Request-ID` values are preserved when provided by the caller.

## Current Manual Testing

What you can test at the current milestone:

- `GET /health`
- Telegram webhook parsing and guided journal flow
- Journal Assist suggestion flow through `/assist`
- Mongo-backed journal persistence

Start the app from source:

```bash
source .venv/bin/activate
PYTHONPATH=src python -m ai_content_agent.main
```

In a second terminal:

```bash
curl -i http://127.0.0.1:8000/health
```

To test the Telegram webhook locally without Telegram, post Telegram-style payloads to `POST /webhooks/telegram`. Keep the same `chat.id` across requests so the in-memory session matches.

Example:

```bash
curl -s http://127.0.0.1:8000/webhooks/telegram \
  -H 'Content-Type: application/json' \
  -d '{
    "update_id": 1,
    "message": {
      "message_id": 10,
      "text": "/journal",
      "from": { "id": 100, "is_bot": false, "username": "adi" },
      "chat": { "id": 456, "type": "private" }
    }
  }'
```

If you want to exercise `/assist` or save journal entries, your `.env` needs:

- a real chat-model API key for the configured `JOURNAL_ASSIST_PROVIDER`
- a real embedding API key/config for `EMBEDDING_PROVIDER`
- a reachable MongoDB instance

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
