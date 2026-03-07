FROM python:3.12-slim

WORKDIR /app

# Install system dependencies for linters
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install ruff (Python linter)
RUN pip install --no-cache-dir ruff

# Install the agent
COPY pyproject.toml README.md ./
COPY src/ src/
COPY prompts/ prompts/
RUN pip install --no-cache-dir .

ENTRYPOINT ["code-review-agent"]
CMD ["--help"]
