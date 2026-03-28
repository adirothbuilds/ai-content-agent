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

The repo is implemented through milestone 5 / issue `#21`.

Current state:

- Telegram webhook, guided journal flow, and AI-assisted journal completion are implemented
- Journal Assist, Idea, Writer, SEO, and Remix are Agno-backed
- journal entries, GitHub activity, draft history, and published post history are persisted as retrieval-ready MongoDB documents
- Telegram now supports idea generation, idea selection, draft generation, remix, publish, and history browsing
- the planned manual control endpoints for journal save, GitHub sync, idea generation, draft generation, remix, publish, and post history are available

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
- Telegram idea selection, draft generation, remix, publish, and history flow
- manual control endpoints under `/journal-entries`, `/github/sync`, `/ideas/generate`, `/drafts/...`, and `/posts/history`
- Mongo-backed journal, draft, and post persistence

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

### Telegram Content Flow

Milestone 5 adds these Telegram commands:

- `/ideas [optional topic]`
- `/select <number>`
- `/draft`
- `/remix <feedback>`
- `/publish`
- `/history`

Example local flow:

```bash
curl -s http://127.0.0.1:8000/webhooks/telegram \
  -H 'Content-Type: application/json' \
  -d '{
    "update_id": 100,
    "message": {
      "message_id": 200,
      "text": "/ideas webhook reliability",
      "from": { "id": 100, "is_bot": false, "username": "adi" },
      "chat": { "id": 456, "type": "private" }
    }
  }'
```

Then continue with the same `chat.id`:

```bash
curl -s http://127.0.0.1:8000/webhooks/telegram \
  -H 'Content-Type: application/json' \
  -d '{
    "update_id": 101,
    "message": {
      "message_id": 201,
      "text": "/select 1",
      "from": { "id": 100, "is_bot": false, "username": "adi" },
      "chat": { "id": 456, "type": "private" }
    }
  }'
```

```bash
curl -s http://127.0.0.1:8000/webhooks/telegram \
  -H 'Content-Type: application/json' \
  -d '{
    "update_id": 102,
    "message": {
      "message_id": 202,
      "text": "/draft",
      "from": { "id": 100, "is_bot": false, "username": "adi" },
      "chat": { "id": 456, "type": "private" }
    }
  }'
```

After that you can use `/remix make it shorter`, `/publish`, and `/history`.

If you want this flow to run end to end against real providers, your `.env` also needs:

- real LLM credentials for the providers configured in `IDEA_PROVIDER`, `WRITER_PROVIDER`, `SEO_PROVIDER`, and `REMIX_PROVIDER`
- a real embedding-capable provider for `EMBEDDING_PROVIDER`
- a reachable MongoDB instance
- a GitHub token with the permissions listed below if you want live GitHub sync in the idea flow

### Manual Control Endpoints

The FastAPI control surface now matches the plan:

- `POST /journal-entries`
- `POST /github/sync`
- `POST /ideas/generate`
- `POST /drafts/generate`
- `POST /drafts/{draft_id}/remix`
- `POST /posts/{draft_id}/publish`
- `GET /posts/history`

Example manual idea generation:

```bash
curl -s http://127.0.0.1:8000/ideas/generate \
  -H 'Content-Type: application/json' \
  -d '{"prompt":"workflow state and publish loops"}'
```

Example manual history lookup:

```bash
curl -s http://127.0.0.1:8000/posts/history
```

## Dev Integration Tests

The repo now has a dedicated dev integration suite that expects a real local MongoDB from the `dev` Compose profile.

Start the dev stack:

```bash
docker compose --profile dev up -d
```

Run the regular fast suite:

```bash
make test
```

Run the real-Mongo integration suite:

```bash
make test-integration-dev
```

Notes:

- `make test` excludes integration tests and stays fast.
- `make test-integration-dev` uses `mongodb://127.0.0.1:27017` and a dedicated database named `ai_content_agent_integration`.
- If local MongoDB is not running, the integration tests skip instead of failing.
- The integration suite clears its own test database before each run and leaves the generated documents in place afterward so you can inspect them in Mongo UI.

## Mongo UI

The `dev` Compose profile now includes `mongo-express` so you can inspect Mongo data in the browser after running integration tests.

- URL: `http://127.0.0.1:8081`
- MongoDB target: the local `mongodb` service from Compose
- Basic auth: disabled for local dev

What you should see after a successful integration run:

- `journal_entries`
- `draft_history`
- `post_history`
- `post_checkpoints`

## Live AI Smoke Test

The repo also includes one opt-in live smoke test that calls your real configured providers for:

- embeddings
- Journal Assist
- Idea Agent
- Writer Agent
- SEO Agent
- Remix Agent

Run it explicitly:

```bash
make test-live-ai
```

Notes:

- it uses your real `.env` provider configuration
- it will spend tokens
- it writes a JSON report to `reports/live_ai/latest.json`
- it uses fixed local context for retrieval/history so the live spend stays focused on the LLM and embedding calls

The report includes:

- provider/model settings per task
- prompt versions
- execution records per stage
- structured-output expectation vs observed behavior
- fallback usage
- duration per stage
- estimated cost per stage and total estimated run cost
- each stage result payload
- failure details if any stage breaks

The live smoke is a provider sanity check, not a benchmark. It should stay small and opt-in.

## Benchmarks

Milestone 6 benchmark fixtures now live under [`evals/datasets`](evals/datasets). They cover:

- Journal Assist
- Idea Agent
- Writer Agent
- SEO Agent
- Remix Agent

Run the current-model benchmark suite:

```bash
make benchmark
```

Run one agent only:

```bash
make benchmark-journal
make benchmark-idea
make benchmark-writer
make benchmark-seo
make benchmark-remix
```

Regenerate the Markdown summary from the latest scored artifact:

```bash
make benchmark-report
```

Benchmark notes:

- the runner executes the real Agno-backed agents, not isolated prompt snippets
- raw outputs and scored outputs are written separately
- reports are stored under `reports/benchmarks/<timestamp>/`
- the latest run is mirrored under `reports/benchmarks/latest/`
- scorecards include quality, latency, token usage, estimated cost, fallback rate, and structured-output adherence
- prompt tuning should happen after capturing a baseline benchmark run, not before

Relevant env vars:

- `BENCHMARK_DATASET_PATH`
- `BENCHMARK_OUTPUT_PATH`
- `BENCHMARK_MAX_CASES`
- `BENCHMARK_SOFT_BUDGET_USD`

## Prompt Management

Agent instructions and prompt builders are centralized in [`src/ai_content_agent/prompts.py`](src/ai_content_agent/prompts.py).

That is intentional for the upcoming evaluation milestone:

- prompt edits are versioned in one place
- agent modules only own execution and validation logic
- benchmark fixtures can later record prompt versions alongside model/provider results

The current prompt registry already exposes a `version` per agent prompt, so later evaluation work can compare model changes without losing prompt provenance.

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

- `dev`: `mongodb` + `server` + `mongo-express`
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
- `mongo-express` is available in `dev` on `http://127.0.0.1:8081`.
- Use the `dev` profile for local development when you do not need a public tunnel.
- Use the `prod` profile only with a real `CLOUDFLARED_TUNNEL_TOKEN` and `PUBLIC_BASE_URL`.
- The current bootstrap verifies startup configuration and serves `GET /health` on port `8000`.
