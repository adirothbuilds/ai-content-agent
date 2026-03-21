PYTHON := .venv/bin/python
PIP := .venv/bin/pip
PYTEST := .venv/bin/pytest

.PHONY: install test run

install:
	$(PIP) install ".[dev]"

test:
	PYTHONPYCACHEPREFIX=/tmp/ai-content-agent-pycache $(PYTEST) -q

run:
	$(PYTHON) -m ai_content_agent.main
