# MVP V1 Issue Backlog

This backlog mirrors `ROADMAP.md` and is intended to be copied into GitHub Issues manually for the MVP V1 project.

## Milestone 1: Foundation

### 1. Bootstrap Python project, packaging, and FastAPI app

- Milestone: Foundation
- Summary/Scope: Create the Python 3.11+ project layout, package structure, FastAPI application entrypoint, and `GET /health` endpoint.
- Dependencies: None
- Acceptance Criteria:
  - The app starts locally.
  - A structured package layout exists.
  - `GET /health` returns successfully.

### 2. Implement environment-driven settings layer

- Milestone: Foundation
- Summary/Scope: Add a settings module that loads all runtime configuration from `.env`, including provider keys, model IDs, MongoDB, Telegram, Cloudflare, and optional NATS values.
- Dependencies: Bootstrap Python project, packaging, and FastAPI app
- Acceptance Criteria:
  - All runtime configuration loads from `.env`.
  - No secrets or model IDs are hardcoded in application logic.
  - Missing required settings fail clearly at startup.

### 3. Add Docker Compose for local deployment

- Milestone: Foundation
- Summary/Scope: Create a Compose stack for `mongodb`, `server`, and `cloudflared` with room to add optional `nats` later.
- Dependencies: Bootstrap Python project, packaging, and FastAPI app
- Acceptance Criteria:
  - `mongodb`, `server`, and `cloudflared` boot together.
  - The server can connect to MongoDB through the Compose network.
  - The stack is documented for local self-hosted use.

### 4. Add base observability primitives

- Milestone: Foundation
- Summary/Scope: Introduce structured logging, request IDs, and run/trace IDs so later agent and benchmark work has consistent observability foundations.
- Dependencies: Bootstrap Python project, packaging, and FastAPI app
- Acceptance Criteria:
  - Request and run trace IDs exist.
  - Logs are structured and consistent.
  - The logging layer can be reused by later workflow components.

## Milestone 2: Telegram UI and Journal Capture

### 5. Implement Telegram webhook integration

- Milestone: Telegram UI and Journal Capture
- Summary/Scope: Add the Telegram webhook route and update parsing so the bot can receive and dispatch commands from Telegram.
- Dependencies: Bootstrap Python project, packaging, and FastAPI app; Implement environment-driven settings layer
- Acceptance Criteria:
  - The bot receives webhook updates through FastAPI.
  - Incoming Telegram updates are parsed into internal actions.
  - Basic webhook validation is in place.

### 6. Build interactive journal entry session flow

- Milestone: Telegram UI and Journal Capture
- Summary/Scope: Implement a multi-step Telegram session for guided journal entry creation with prompts and fillers for work summary, problem solved, tools, lesson, outcome, and relevance.
- Dependencies: Implement Telegram webhook integration
- Acceptance Criteria:
  - A user can create a journal entry through guided Telegram prompts.
  - Session state persists across message steps.
  - Journal fields can be reviewed before save.

### 7. Add AI-assisted journal completion

- Milestone: Telegram UI and Journal Capture
- Summary/Scope: Add Journal Assist support so rough notes can be refined or expanded through AI suggestions during the Telegram flow.
- Dependencies: Build interactive journal entry session flow; Build shared multi-provider LLM abstraction
- Acceptance Criteria:
  - AI can suggest or refine missing journal details.
  - AI assistance identifies gaps and proposes follow-up structure.
  - Save always requires explicit user confirmation.

### 8. Persist journal entries with embeddings

- Milestone: Telegram UI and Journal Capture
- Summary/Scope: Save confirmed journal entries to MongoDB with metadata, provenance, and embeddings on the stored document.
- Dependencies: Build interactive journal entry session flow; Implement environment-driven settings layer
- Acceptance Criteria:
  - Saved journal entries include canonical content and metadata.
  - An embedding vector is stored with each retrieval-relevant entry.
  - Saved entries become retrievable by later workflows.

## Milestone 3: GitHub Ingestion and Retrieval

### 9. Implement GitHub activity tool layer

- Milestone: GitHub Ingestion and Retrieval
- Summary/Scope: Build internal GitHub tools that use the configured token and username to retrieve real user activity, not generic public data scraping.
- Dependencies: Implement environment-driven settings layer
- Acceptance Criteria:
  - The app pulls authenticated user activity using `.env` credentials.
  - Supported activity includes commits, pull requests, merged PRs, and issues.
  - GitHub access stays encapsulated behind internal tool interfaces.

### 10. Normalize GitHub events into retrieval-ready documents

- Milestone: GitHub Ingestion and Retrieval
- Summary/Scope: Transform GitHub activity into shared MongoDB records with consistent schema, provenance, metadata, and embeddings.
- Dependencies: Implement GitHub activity tool layer
- Acceptance Criteria:
  - Commits, PRs, and issues are stored in a shared schema.
  - Provenance is preserved for later citation and retrieval.
  - Stored records are ready for semantic search.

### 11. Implement delta checkpoint service

- Milestone: GitHub Ingestion and Retrieval
- Summary/Scope: Track the last published checkpoint and use it to scope default ingestion and retrieval to new material since the last published post.
- Dependencies: Normalize GitHub events into retrieval-ready documents; Persist journal entries with embeddings
- Acceptance Criteria:
  - Ingestion defaults to activity since the last published post.
  - A fallback window exists if no publish checkpoint exists yet.
  - Explicit topic requests can bypass the default delta gate.

### 12. Build MongoDB vector retrieval service

- Milestone: GitHub Ingestion and Retrieval
- Summary/Scope: Implement top-K semantic retrieval with metadata filters across journal entries, GitHub activity, draft history, and post history.
- Dependencies: Persist journal entries with embeddings; Normalize GitHub events into retrieval-ready documents
- Acceptance Criteria:
  - Top-K retrieval works across target collections.
  - Metadata filters can narrow retrieval scope.
  - Retrieved payloads are bounded and agent-ready.

### 13. Add post-history anti-duplication retrieval checks

- Milestone: GitHub Ingestion and Retrieval
- Summary/Scope: Compare candidate context and drafts against published post history to reduce repeated topics, repeated angles, and formatting reuse.
- Dependencies: Build MongoDB vector retrieval service
- Acceptance Criteria:
  - Previous posts are considered before idea generation.
  - Previous posts are considered before draft generation.
  - Similarity checks can be tuned through configuration.

## Milestone 4: Agents and Content Generation

### 14. Build shared multi-provider LLM abstraction

- Milestone: Agents and Content Generation
- Summary/Scope: Implement the typed provider layer for OpenAI, OpenAI-compatible APIs, Gemini, and Anthropic, with shared request and response models, task-centric `.env` routing, configuration loading, and error normalization.
- Dependencies: Implement environment-driven settings layer
- Acceptance Criteria:
  - OpenAI, OpenAI-compatible, Gemini, and Anthropic adapters conform to one internal interface.
  - Provider and model selection is driven per task through `.env`.
  - Provider-specific failures are normalized consistently.

### 15. Implement Idea Agent with OpenAI

- Milestone: Agents and Content Generation
- Summary/Scope: Build the Idea Agent to retrieve context and return exactly 3 grounded idea candidates with distinct angles.
- Dependencies: Build shared multi-provider LLM abstraction; Build MongoDB vector retrieval service; Add post-history anti-duplication retrieval checks
- Acceptance Criteria:
  - The agent returns 3 structured ideas.
  - Ideas are grounded in retrieved journal and GitHub context.
  - Post history is used to reduce repetitive output.

### 16. Implement Writer Agent with Claude

- Milestone: Agents and Content Generation
- Summary/Scope: Build the Writer Agent to generate a LinkedIn draft from the selected idea and supporting context.
- Dependencies: Build shared multi-provider LLM abstraction; Implement Idea Agent with OpenAI
- Acceptance Criteria:
  - The agent produces a draft grounded in the selected idea.
  - The draft references real source context.
  - Draft generation preserves provenance through the workflow.

### 17. Implement SEO Agent with Gemini

- Milestone: Agents and Content Generation
- Summary/Scope: Build the SEO Agent to enrich drafts with tags and formatting improvements without changing factual meaning.
- Dependencies: Build shared multi-provider LLM abstraction; Implement Writer Agent with Claude
- Acceptance Criteria:
  - Tags and formatting are relevant to the draft topic.
  - SEO changes do not alter factual meaning.
  - The enrichment step is deterministic within the workflow.

### 18. Implement Remix Agent

- Milestone: Agents and Content Generation
- Summary/Scope: Build the Remix Agent to revise an existing draft using explicit Telegram feedback while preserving facts and lineage.
- Dependencies: Build shared multi-provider LLM abstraction; Implement Writer Agent with Claude
- Acceptance Criteria:
  - The agent revises drafts from user feedback.
  - Factual content is preserved.
  - Draft lineage remains traceable across remix iterations.

## Milestone 5: Publish Flow and Memory Growth

### 19. Implement Telegram idea selection and draft approval flow

- Milestone: Publish Flow and Memory Growth
- Summary/Scope: Connect the Telegram UI to idea selection, draft generation approval, and workflow state transitions.
- Dependencies: Implement Telegram webhook integration; Implement Idea Agent with OpenAI; Implement Writer Agent with Claude; Implement SEO Agent with Gemini
- Acceptance Criteria:
  - The user can trigger idea generation in Telegram.
  - The user can select one idea in Telegram.
  - Draft generation can be approved directly from Telegram.

### 20. Implement publish/finalize flow and checkpoint update

- Milestone: Publish Flow and Memory Growth
- Summary/Scope: Add the finalization path that stores a published post, updates history, and advances the delta checkpoint.
- Dependencies: Implement Telegram idea selection and draft approval flow; Implement delta checkpoint service
- Acceptance Criteria:
  - Final posts are saved as published history.
  - The publish action updates the checkpoint state.
  - Published posts are available for future anti-duplication checks.

### 21. Implement history browsing in Telegram

- Milestone: Publish Flow and Memory Growth
- Summary/Scope: Add Telegram flows for browsing recent posts and history summaries so users can inspect prior output before generating more content.
- Dependencies: Implement publish/finalize flow and checkpoint update
- Acceptance Criteria:
  - Users can inspect recent posts from Telegram.
  - History summaries are readable within the chat interface.
  - History is connected to stored post records.

## Milestone 6: Evaluation and Observability

### 22. Create benchmark dataset for Journal Assist

- Milestone: Evaluation and Observability
- Summary/Scope: Build benchmark fixtures for partial notes, follow-up question quality, completion usefulness, and hallucination resistance for Journal Assist.
- Dependencies: Add AI-assisted journal completion
- Acceptance Criteria:
  - The dataset covers partial-note scenarios.
  - Hallucination guardrail cases are included.
  - Fixtures are reusable across provider comparisons.

### 23. Create benchmark dataset for Idea Agent

- Milestone: Evaluation and Observability
- Summary/Scope: Build benchmark fixtures to measure idea novelty, grounding, and distinctness across the 3 generated ideas.
- Dependencies: Implement Idea Agent with OpenAI
- Acceptance Criteria:
  - The dataset measures novelty against post history.
  - Grounding cases use real journal and GitHub context.
  - Distinctness across idea outputs is testable.

### 24. Create benchmark dataset for SEO Agent

- Milestone: Evaluation and Observability
- Summary/Scope: Build benchmark fixtures for tag relevance, formatting usefulness, and non-destructive SEO improvements.
- Dependencies: Implement SEO Agent with Gemini
- Acceptance Criteria:
  - Tag relevance can be scored.
  - Formatting usefulness can be reviewed consistently.
  - Cases verify that factual meaning is preserved.

### 25. Create benchmark dataset for Writer Agent

- Milestone: Evaluation and Observability
- Summary/Scope: Build benchmark fixtures for factual grounding, readability, and repetition avoidance in draft generation.
- Dependencies: Implement Writer Agent with Claude
- Acceptance Criteria:
  - Grounding cases exist for real retrieved context.
  - Readability and structure can be scored.
  - Repetition avoidance is included in the dataset.

### 26. Create benchmark dataset for Remix Agent

- Milestone: Evaluation and Observability
- Summary/Scope: Build benchmark fixtures for feedback adherence, factual preservation, and draft improvement across remix iterations.
- Dependencies: Implement Remix Agent
- Acceptance Criteria:
  - Feedback adherence is measurable.
  - Factual preservation cases are covered.
  - Improvement over the prior draft can be evaluated.

### 27. Build benchmark runner and scorecard reporting

- Milestone: Evaluation and Observability
- Summary/Scope: Create the shared benchmark execution flow and scorecard output so candidate providers and models can be compared per agent.
- Dependencies: Create benchmark dataset for Journal Assist; Create benchmark dataset for Idea Agent; Create benchmark dataset for SEO Agent; Create benchmark dataset for Writer Agent; Create benchmark dataset for Remix Agent
- Acceptance Criteria:
  - The same fixtures can run across candidate models/providers per agent.
  - Scorecards include quality metrics and comparison summaries.
  - Benchmark runs are reproducible.

### 28. Capture provider latency, token usage, and cost metadata

- Milestone: Evaluation and Observability
- Summary/Scope: Capture usage and latency metadata around every model call so operational and benchmark analysis can share the same telemetry.
- Dependencies: Build shared multi-provider LLM abstraction; Add base observability primitives
- Acceptance Criteria:
  - Every model call stores token usage and latency.
  - Provider and model identifiers are persisted with the run.
  - Cost estimation hooks are available for benchmark reporting.

## Milestone 7: Optional Eventing Hardening

### 29. Add optional NATS integration for background events

- Milestone: Optional Eventing Hardening
- Summary/Scope: Add optional NATS-backed event publishing for slow tasks such as ingestion and generation while keeping the core flow functional when NATS is turned off.
- Dependencies: Add Docker Compose for local deployment; Add base observability primitives
- Acceptance Criteria:
  - Slow tasks can be dispatched asynchronously.
  - The app still functions with NATS disabled.
  - Eventing remains optional and lightweight in V1.
