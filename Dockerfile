FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim

WORKDIR /app
COPY . /app

ENTRYPOINT ["uv", "run", ".gitea/scripts/code_review.py"]
