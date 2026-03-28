PYTHON := .venv/bin/python
PIP := .venv/bin/pip
PYTEST := .venv/bin/pytest

.PHONY: install test test-integration-dev test-live-ai benchmark benchmark-journal benchmark-idea benchmark-writer benchmark-seo benchmark-remix benchmark-report run compose-dev compose-prod compose-down compose-down-dev compose-down-prod

install:
	$(PIP) install ".[dev]"

test:
	PYTHONPATH=src PYTHONPYCACHEPREFIX=/tmp/ai-content-agent-pycache $(PYTEST) -q -m "not integration and not live_ai"

test-integration-dev:
	PYTHONPATH=src PYTHONPYCACHEPREFIX=/tmp/ai-content-agent-pycache $(PYTEST) -q -m integration

test-live-ai:
	RUN_LIVE_AI_TESTS=true PYTHONPATH=src PYTHONPYCACHEPREFIX=/tmp/ai-content-agent-pycache $(PYTEST) -q -m live_ai --maxfail=1

benchmark:
	PYTHONPATH=src PYTHONPYCACHEPREFIX=/tmp/ai-content-agent-pycache $(PYTHON) -m ai_content_agent.benchmarks

benchmark-journal:
	PYTHONPATH=src PYTHONPYCACHEPREFIX=/tmp/ai-content-agent-pycache $(PYTHON) -m ai_content_agent.benchmarks --agent journal_assist

benchmark-idea:
	PYTHONPATH=src PYTHONPYCACHEPREFIX=/tmp/ai-content-agent-pycache $(PYTHON) -m ai_content_agent.benchmarks --agent idea_agent

benchmark-writer:
	PYTHONPATH=src PYTHONPYCACHEPREFIX=/tmp/ai-content-agent-pycache $(PYTHON) -m ai_content_agent.benchmarks --agent writer_agent

benchmark-seo:
	PYTHONPATH=src PYTHONPYCACHEPREFIX=/tmp/ai-content-agent-pycache $(PYTHON) -m ai_content_agent.benchmarks --agent seo_agent

benchmark-remix:
	PYTHONPATH=src PYTHONPYCACHEPREFIX=/tmp/ai-content-agent-pycache $(PYTHON) -m ai_content_agent.benchmarks --agent remix_agent

benchmark-report:
	PYTHONPATH=src PYTHONPYCACHEPREFIX=/tmp/ai-content-agent-pycache $(PYTHON) -m ai_content_agent.benchmarks --report-only

run:
	$(PYTHON) -m ai_content_agent.main

compose-dev:
	docker compose --profile dev up -d

compose-prod:
	docker compose --profile prod up -d

compose-down:
	docker compose down

compose-down-dev:
	docker compose --profile dev down

compose-down-prod:
	docker compose --profile prod down
