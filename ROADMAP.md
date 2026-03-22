# Roadmap

## Milestone 1: Foundation

**Objective**

Establish the service skeleton, runtime configuration, and local deployment base for MVP V1.

**Deliverables**

- Python project bootstrap and package layout
- FastAPI app skeleton with health endpoint
- `.env`-driven settings layer
- Docker Compose for `mongodb`, `server`, and `cloudflared`
- Base logging and trace ID support

**Done Criteria**

- The app starts locally and serves `GET /health`.
- No runtime secrets or model IDs are hardcoded.
- The core containers boot together through Docker Compose.

## Milestone 2: Telegram UI and Journal Capture

**Objective**

Make Telegram the working primary UI for capturing journal data and guiding the user through assisted entry creation.

**Deliverables**

- Telegram webhook integration
- Interactive journal entry session flow
- Multi-step prompt and filler handling
- AI-assisted journal completion with confirmation gate
- Journal persistence with embeddings

**Done Criteria**

- A user can create and save a journal entry entirely from Telegram.
- AI-assisted journal content is never persisted without explicit confirmation.
- Saved journal entries are stored with metadata and embeddings.

## Milestone 3: GitHub Ingestion and Retrieval

**Objective**

Bring user-specific GitHub activity into the memory system and expose bounded retrieval for downstream agents.

**Deliverables**

- GitHub token-based activity tools
- Normalization of GitHub events into shared records
- Delta checkpointing from the last published post
- MongoDB vector retrieval across target collections
- Top-K retrieval service with metadata filters

**Done Criteria**

- GitHub activity sync works with environment-provided credentials.
- Retrieval returns relevant top-K context from journal, GitHub, and history records.
- Delta-based ingestion excludes already-covered activity by default.

## Milestone 4: Agents and Content Generation

**Objective**

Deliver the multi-provider agent layer and generate grounded content from retrieved source material.

**Deliverables**

- Shared task-routed LLM abstraction for OpenAI, OpenAI-compatible APIs, Gemini, and Anthropic
- Journal Assist wiring through the shared provider layer
- Idea Agent with OpenAI
- Writer Agent with Claude
- SEO Agent with Gemini
- Remix Agent with Claude
- Post-history anti-duplication checks

**Done Criteria**

- Each agent runs through the shared provider layer.
- Provider and model selection is configurable per task through `.env`.
- Idea generation returns 3 grounded ideas.
- Writer, SEO, and Remix flows preserve factual intent and provenance.

## Milestone 5: Publish Flow and Memory Growth

**Objective**

Complete the Telegram-driven content loop and turn published output into reusable memory.

**Deliverables**

- Telegram idea selection and draft approval flow
- Publish and finalize action
- Post-history persistence
- Checkpoint updates after publishing
- History browsing in Telegram

**Done Criteria**

- A user can go from idea request to published post entirely in Telegram.
- Published posts are stored and considered in future duplication checks.
- The delta checkpoint advances after publication.

## Milestone 6: Evaluation and Observability

**Objective**

Make the system measurable so agent and provider choices can be benchmarked and debugged over time.

**Deliverables**

- Per-agent benchmark datasets
- Benchmark runner and scorecards
- Provider comparison support per agent
- Token, latency, and cost instrumentation
- Traceable run metadata

**Done Criteria**

- Every agent has benchmark coverage.
- Provider comparisons can be run against the same fixtures.
- Model calls record usage and latency metadata.

## Milestone 7: Optional Eventing Hardening

**Objective**

Add lightweight async delivery where it improves responsiveness without turning V1 into a distributed system.

**Deliverables**

- Optional NATS integration for background events
- Decoupling of slow jobs from webhook-triggered flows
- Graceful fallback behavior when NATS is disabled

**Done Criteria**

- Slow paths can be dispatched asynchronously through NATS.
- The core product flow still works with NATS disabled.
- Eventing remains optional and lightweight in V1.
