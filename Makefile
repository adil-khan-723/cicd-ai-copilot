.PHONY: install test run-webhook run-bot lint clean

install:
	python3 -m venv .venv
	.venv/bin/pip install --upgrade pip
	.venv/bin/pip install -r requirements.txt

test:
	.venv/bin/pytest tests/ -v

test-cov:
	.venv/bin/pytest tests/ --cov=. --cov-report=term-missing

run-webhook:
	.venv/bin/uvicorn webhook.server:app --reload --port 8000

run-bot:
	.venv/bin/python -m slack.bot

lint:
	.venv/bin/python -m py_compile providers/*.py parser/*.py || true

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -name "*.pyc" -delete
