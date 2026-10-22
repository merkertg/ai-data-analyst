# syntax=docker/dockerfile:1

# One image runs every service of the stand: migrations, bootstrap, API and the
# Streamlit interface; Compose chooses the command. Base images are pinned by
# the digest of their multi-architecture index: a tag can be moved, a digest
# cannot. The same digests are used by the first course project.
FROM python:3.12-slim@sha256:a6e34c598f2467ed0e9a8d349809fcd8b5c603269512df273a0bb1784edc11b1 AS python-base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# The builder installs the locked runtime dependencies into /app/.venv.
FROM python-base AS builder
COPY --from=ghcr.io/astral-sh/uv:0.12.23@sha256:61d393e44e249f2e4b526b6c7ddcecce245946826e608e11c93ad4f5bba55b21 /uv /bin/uv

WORKDIR /app
# Use the Python of the base image and copy files out of the uv cache.
ENV UV_PYTHON_DOWNLOADS=0 \
    UV_LINK_MODE=copy

# Dependencies first: a code change does not reinstall the libraries.
# --no-dev leaves out pytest, Ruff, mypy and pytest-cov.
COPY pyproject.toml uv.lock README.md ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-dev

# The final image has no uv, no build cache and no development tools.
FROM python-base AS runtime
WORKDIR /app
ENV PATH="/app/.venv/bin:$PATH" \
    STREAMLIT_SERVER_HEADLESS=true \
    STREAMLIT_SERVER_FILE_WATCHER_TYPE=none \
    STREAMLIT_BROWSER_GATHER_USAGE_STATS=false \
    STREAMLIT_CLIENT_TOOLBAR_MODE=minimal

# A fixed non-root UID; /run/ai-data-analyst holds the interface token and
# gets this owner, so a fresh Docker volume mounted there is writable.
RUN groupadd --gid 10001 app && \
    useradd --uid 10001 --gid app --create-home app && \
    mkdir -p /run/ai-data-analyst && \
    chown app:app /run/ai-data-analyst && \
    chmod 700 /run/ai-data-analyst
COPY --from=builder --chown=app:app /app/.venv /app/.venv
COPY --chown=app:app app ./app
COPY --chown=app:app ui ./ui
COPY --chown=app:app migrations ./migrations
COPY --chown=app:app alembic.ini ./alembic.ini
COPY --chown=app:app .streamlit ./.streamlit
# The eval questions let `python -m app.evals` run inside the container.
COPY --chown=app:app evals/cases.json ./evals/cases.json
USER app

EXPOSE 8000 8501

# The default command serves the API; /ready checks the database and the
# schema revision. The standard library is enough: no curl in the image.
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD ["python", "-c", "import json, urllib.request; response = urllib.request.urlopen('http://127.0.0.1:8000/ready', timeout=3); assert response.status == 200 and json.load(response)['status'] == 'ready'"]

# Exec form: stop signals reach Uvicorn directly.
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
