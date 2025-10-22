# syntax=docker/dockerfile:1.6
FROM python:3.11-slim AS base
WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl git build-essential && rm -rf /var/lib/apt/lists/*

# Install uv
RUN curl -LsSf https://astral.sh/uv/install.sh | sh && ln -s /root/.local/bin/uv /usr/local/bin/uv

# Copy deps first for caching
COPY pyproject.toml README.md ./
COPY src ./src

FROM base AS dev
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 UV_SYSTEM_PYTHON=1

# Install your app + Langfuse SDK
RUN uv pip install -e . --no-cache-dir

# LangGraph dev server
EXPOSE 2024
CMD ["uv","run","langgraph","dev","--host","0.0.0.0","--port","2024"]
