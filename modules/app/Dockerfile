# syntax=docker/dockerfile:1.6
FROM python:3.12-slim AS base
WORKDIR /app

# OS deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl git build-essential ca-certificates \
 && rm -rf /var/lib/apt/lists/*

# uv
RUN curl -LsSf https://astral.sh/uv/install.sh | sh && ln -s /root/.local/bin/uv /usr/local/bin/uv

# App files
COPY pyproject.toml README.md ./
COPY src ./src

# Dev image
FROM base AS dev
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_SYSTEM_PYTHON=1 \
    PYO3_USE_ABI3_FORWARD_COMPATIBILITY=1

# Python deps (your pyproject must include fastapi/uvicorn/websockets)
RUN uv pip install -e . --no-cache-dir

# Copy start.sh to the Docker container
COPY start.sh /usr/src/app/start.sh

# Give execution permissions to the start.sh script
RUN chmod +x /usr/src/app/start.sh

EXPOSE 2024 8000
CMD ["/usr/src/app/start.sh"]
