# AI Content Agent

## Title and Purpose

AI Content Agent is a Telegram-first, human-in-the-loop LinkedIn content assistant for turning real work into authentic post drafts. It combines interactive journal capture, GitHub activity retrieval, post-history memory, and task-specific AI agents so ideas and drafts stay grounded in actual engineering work instead of generic content.

## Goals

- Reduce the effort required to publish authentic LinkedIn content consistently.
- Keep the human in control of journal entry creation, topic selection, approval, remix, and publishing.
- Ground ideas and drafts in real journal entries and GitHub activity.
- Avoid repeated post angles by checking post history before generating new content.
- Keep runtime, provider, and deployment configuration controlled through `.env` without hardcoded values.

## Core Workflow

### Main flow

1. The user adds journal entries through Telegram, optionally asking for AI help to complete or refine rough notes.
2. The app syncs new GitHub activity for the configured user using an environment-provided token.
3. The system uses the delta since the last published post as the default ingestion and retrieval gate, unless the user explicitly requests a specific topic.
4. The Idea Agent retrieves relevant journal entries, GitHub activity, and post history, then returns exactly 3 grounded ideas.
5. The user selects one idea in Telegram.
6. The Writer Agent drafts the LinkedIn post.
7. The SEO Agent enriches the draft with tags and formatting improvements.
8. The user approves the draft, requests a remix, or continues iterating in Telegram.
9. The final post is saved as published history and becomes part of future retrieval and anti-duplication checks.

### Supporting flow

- GitHub activity is pulled through internal tools scoped to the configured user and token.
- New GitHub events are normalized, embedded, and made retrievable alongside journal entries and post history.

## Tech Stack

| Layer | Technology | Role in MVP V1 |
| --- | --- | --- |
| Language | Python 3.11+ | Main application runtime |
| Agent framework | Agno | Agent orchestration and typed workflows |
| API/server | FastAPI | Telegram webhook host and internal control API |
| Database | MongoDB | Canonical storage and vector-capable retrieval store |
| LLM provider | OpenAI GPT | Journal Assist and Idea Agent |
| LLM provider | Google Gemini | SEO Agent |
| LLM provider | Anthropic Claude | Writer Agent and default Remix Agent |
| Embeddings | Dedicated embedding model/API | Embeddings for retrieval-relevant records |
| Eventing | NATS (optional) | Lightweight async event delivery where needed |
| Ingress | Cloudflare Tunnel | Public HTTPS entrypoint for Telegram webhook |
| Packaging | Docker Compose | Local deployment on the Debian mini PC |

## Architecture

### FastAPI control plane

- Host the Telegram webhook and internal debug/manual endpoints.
- Keep route handlers thin and push workflow logic into services.
- Run on the Debian mini PC and expose the webhook through Cloudflare Tunnel.

### Telegram webhook and UI flow

- Treat Telegram as the primary user interface.
- Support journal entry creation, idea generation, idea selection, approval, remix, publish, and history lookup.
- Keep synchronous Telegram interactions responsive and move slow work to background processing where useful.

### MongoDB storage and retrieval

- Store canonical business documents and retrieval-ready documents in MongoDB from day 1.
- Keep embeddings on each retrieval-relevant document instead of in a separate system.
- Use MongoDB vector search plus metadata filters to keep agent context bounded.

### GitHub tools integration

- Pull user-specific activity using a GitHub token and configured username from `.env`.
- Normalize commits, pull requests, merged PRs, issues, and selected repository metadata into shared retrieval-ready records.

### Agent orchestration

- Use Agno to implement small, focused agents with explicit input and output schemas.
- Keep Journal Assist, Idea Agent, SEO Agent, Writer Agent, and Remix Agent scoped to one clear responsibility each.

### Shared LLM abstraction

- Wrap OpenAI, Gemini, and Anthropic behind one typed interface.
- Keep provider selection deterministic by task in V1.
- Support future provider switching through benchmark-driven decisions rather than hardcoded assumptions.

### Optional event delivery

- Keep NATS optional and lightweight in V1.
- Use it only where it improves responsiveness for slow ingestion or generation paths.
- Preserve a working synchronous control flow when NATS is disabled.

### Observability and benchmarking

- Capture request IDs, run IDs, model metadata, latency, token usage, and failure information.
- Add evaluation datasets and benchmark runners per agent so provider choices can be revisited later.

## Agent Design

### Journal Assist

- Helps the user complete or refine partial journal notes in Telegram.
- Suggests structure, missing details, and cleaner phrasing.
- Must never persist AI-generated content without explicit user confirmation.
- Default provider: OpenAI.

### Idea Agent

- Retrieves relevant context and returns exactly 3 grounded idea candidates.
- Must use post history to reduce repeated topics and angles.
- Default provider: OpenAI.

### SEO Agent

- Improves visibility through hashtags, formatting, and lightweight structure refinements.
- Must not change the factual meaning of the draft.
- Default provider: Gemini.

### Writer Agent

- Produces a LinkedIn draft based on the selected idea and retrieved source context.
- Must preserve provenance to journal and GitHub inputs.
- Default provider: Claude.

### Remix Agent

- Revises an existing draft based on explicit user feedback from Telegram.
- Must preserve facts while applying the requested changes.
- Default provider: Claude.

Provider assignment is configurable through `.env` and should remain benchmark-driven over time.

## Memory and Retrieval Design

- Store embeddings on every retrieval-relevant MongoDB document from day 1.
- Retrieval-relevant document classes:
  - journal entries
  - GitHub activity records
  - published post history
  - draft history
  - reusable memory records
- Use top-K semantic retrieval with collection and metadata filters to bound agent context.
- Use delta-from-last-published-post as the default ingestion and retrieval gate.
- Allow explicit user topic requests to override the default delta gate.
- Always check post history before idea generation and draft generation to reduce redundant posts, repeated angles, and repeated formatting patterns.

## Telegram Interaction Model

Telegram is the primary UI for the MVP.

### Interactive journal entry creation

- Start a guided journal session from Telegram.
- Walk the user through structured prompts such as:
  - what you worked on
  - what problem you solved
  - tools or tech involved
  - lesson learned
  - result or outcome
  - why it matters
- Let the user submit partial notes and request AI assistance.
- Require explicit user confirmation before saving an AI-assisted journal entry.

### Content workflow actions

- Trigger idea generation.
- View the 3 idea candidates.
- Select one idea.
- Approve draft generation.
- Request a remix with freeform feedback.
- Publish or finalize the selected draft.
- Inspect recent post history and summaries.

## API Surface

- `POST /webhooks/telegram`
- `POST /journal-entries`
- `POST /github/sync`
- `POST /ideas/generate`
- `POST /drafts/generate`
- `POST /drafts/{draft_id}/remix`
- `POST /posts/{draft_id}/publish`
- `GET /posts/history`
- `GET /health`

## Environment Variables

All runtime configuration must be controlled through `.env` in local and self-hosted deployments.

| Variable | Required | Example | Purpose |
| --- | --- | --- | --- |
| `APP_ENV` | Yes | `development` | Runtime environment name |
| `APP_HOST` | Yes | `0.0.0.0` | FastAPI bind host |
| `APP_PORT` | Yes | `8000` | FastAPI bind port |
| `LOG_LEVEL` | No | `INFO` | Log verbosity |
| `MONGODB_URI` | Yes | `mongodb://mongodb:27017` | MongoDB connection URI |
| `MONGODB_DATABASE` | Yes | `ai_content_agent` | MongoDB database name |
| `MONGODB_VECTOR_INDEX_NAME` | No | `default_vector_index` | Vector index name |
| `NATS_ENABLED` | No | `true` | Enable optional NATS integration |
| `NATS_URL` | No | `nats://nats:4222` | NATS connection URL |
| `TELEGRAM_BOT_TOKEN` | Yes | `<secret>` | Telegram bot token |
| `TELEGRAM_WEBHOOK_SECRET` | No | `<secret>` | Optional webhook verification secret |
| `PUBLIC_BASE_URL` | Yes | `https://example.trycloudflare.com` | Public base URL used for webhook setup |
| `CLOUDFLARED_TUNNEL_TOKEN` | Yes | `<secret>` | Cloudflare Tunnel token |
| `GITHUB_TOKEN` | Yes | `<secret>` | GitHub API token |
| `GITHUB_USERNAME` | Yes | `adiroth` | GitHub username used for activity filtering |
| `OPENAI_API_KEY` | Yes | `<secret>` | OpenAI API key |
| `OPENAI_IDEA_MODEL` | Yes | `gpt-5` | Model used by Idea Agent |
| `OPENAI_JOURNAL_ASSIST_MODEL` | No | `gpt-5-mini` | Model used by Journal Assist |
| `GEMINI_API_KEY` | Yes | `<secret>` | Gemini API key |
| `GEMINI_SEO_MODEL` | Yes | `gemini-2.5-pro` | Model used by SEO Agent |
| `ANTHROPIC_API_KEY` | Yes | `<secret>` | Anthropic API key |
| `ANTHROPIC_WRITER_MODEL` | Yes | `claude-sonnet-4` | Model used by Writer Agent |
| `ANTHROPIC_REMIX_MODEL` | No | `claude-sonnet-4` | Model used by Remix Agent |
| `EMBEDDING_PROVIDER` | Yes | `openai` | Embedding provider selector |
| `EMBEDDING_MODEL` | Yes | `text-embedding-3-large` | Embedding model ID |
| `RETRIEVAL_TOP_K` | No | `8` | Default retrieval top-K |
| `DELTA_LOOKBACK_DAYS_FALLBACK` | No | `30` | Fallback window if no publish checkpoint exists |
| `POST_HISTORY_SIMILARITY_THRESHOLD` | No | `0.88` | Similarity threshold for duplicate checks |
| `ENABLE_PROVIDER_BENCHMARKS` | No | `true` | Enable benchmark flows |
| `BENCHMARK_DATASET_PATH` | No | `./evals/datasets` | Path to benchmark fixtures |
| `TRACE_PAYLOAD_SAMPLING` | No | `false` | Whether to sample prompt/output payloads in tracing |

## Testing and Evaluation

### Unit tests

- Settings loading from `.env`
- Journal entry session state handling
- GitHub activity normalization
- Delta checkpoint logic
- Post-history similarity checks
- Retrieval filtering and top-K bounds
- Provider adapter normalization

### Integration tests

- Telegram webhook receives updates and routes actions correctly.
- Interactive journal flow saves a confirmed journal entry.
- AI-assisted journal completion requires explicit user confirmation before persistence.
- GitHub sync pulls and stores user-scoped activity.
- Idea selection in Telegram leads to draft generation.
- Remix updates the current draft lineage without losing factual grounding.
- Publishing updates post history and advances the delta checkpoint.
- Core flow works with NATS disabled.

### Agent benchmark and evaluation tests

- Journal Assist benchmark:
  - partial note completion quality
  - follow-up prompt quality
  - hallucination resistance
- Idea Agent benchmark:
  - novelty against post history
  - grounding in journal and GitHub sources
  - distinctness across 3 ideas
- SEO Agent benchmark:
  - tag relevance
  - formatting usefulness
  - non-destructive behavior
- Writer Agent benchmark:
  - factual grounding
  - readability
  - repetition avoidance
- Remix Agent benchmark:
  - adherence to feedback
  - factual preservation
  - improvement over prior draft

Benchmark results must store raw outputs, scores, latency, token usage, and provider metadata so models and providers can be switched later based on evidence.

## Assumptions and Defaults

- Embeddings use a dedicated embedding model, not a chat completion model.
- Cloudflare Tunnel is the only ingress in V1.
- NATS is optional and lightweight in V1.
- Multi-provider support is required from day 1.
- `.env` controls all runtime configuration.
- AI-assisted journal filling always requires explicit user confirmation before persistence.
- Traefik is not part of V1 unless a future deployment constraint requires it.
