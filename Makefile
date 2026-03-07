.PHONY: install dev lint test test-cov docker-build docker-run clean

install:
	pip install .

dev:
	pip install -e ".[dev]"

lint:
	ruff check src/ tests/
	ruff format --check src/ tests/

format:
	ruff check --fix src/ tests/
	ruff format src/ tests/

test:
	pytest -v

test-cov:
	pytest --cov=code_review_agent --cov-report=term-missing

docker-build:
	docker build -t code-review-agent .

docker-run:
	docker run --rm \
		-e CRA_GITHUB_TOKEN \
		-e CRA_OPENAI_API_KEY \
		code-review-agent review $(PR_URL)

# Run a local dry-run review
review-dry:
	code-review-agent review $(PR_URL) --dry-run --debug

# Create a test PR against your repo
test-pr:
	code-review-agent test-pr $(REPO)

clean:
	rm -rf build/ dist/ *.egg-info .pytest_cache .ruff_cache
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
