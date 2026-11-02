FROM ghcr.io/astral-sh/uv:0.9.10 AS uv
FROM python:3.12-slim
COPY --from=uv /uv /usr/local/bin/uv
ENV UV_LINK_MODE=copy
WORKDIR /app/apps/api
COPY apps/api/pyproject.toml apps/api/uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project
COPY apps/api ./
COPY agents /app/agents
RUN uv sync --frozen --no-dev
ENV PATH="/app/apps/api/.venv/bin:$PATH"
CMD ["python", "scripts/serve_pilot.py"]
