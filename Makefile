PYTHON := .venv/bin/python
PIP := .venv/bin/pip
PYTEST := .venv/bin/pytest

.PHONY: install test run compose-dev compose-prod compose-down compose-down-dev compose-down-prod

install:
	$(PIP) install ".[dev]"

test:
	PYTHONPATH=src PYTHONPYCACHEPREFIX=/tmp/ai-content-agent-pycache $(PYTEST) -q

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
