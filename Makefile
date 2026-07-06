.PHONY: install playground run test lint clean

install:
	uv sync

playground:
	uv run adk web app --host 127.0.0.1 --port 18081 --reload_agents

run:
	uv run adk web app --host 127.0.0.1 --port 18081

test:
	uv run pytest tests/ -v

lint:
	uv run ruff check app/
	uv run ruff format --check app/

clean:
	rm -rf .venv/
	rm -rf __pycache__/
	rm -rf app/__pycache__/
	rm -rf .pytest_cache/
	rm -rf .ruff_cache/
	rm -rf artifacts/
