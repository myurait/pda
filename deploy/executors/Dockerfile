FROM ghcr.io/astral-sh/uv:0.12.17 AS uv
FROM node:22.22.0-bookworm-slim AS node
FROM python:3.12.12-slim-bookworm AS base
COPY --from=uv /uv /usr/local/bin/uv
WORKDIR /app
COPY pyproject.toml uv.lock ./
COPY src ./src
COPY tools ./tools
RUN uv sync --frozen --no-dev --no-editable
ENV PATH="/app/.venv/bin:$PATH" PYTHONUNBUFFERED=1
COPY deploy/executors/entrypoint.sh /entrypoint.sh
RUN useradd --uid 1000 --create-home pda && mkdir -p /work && chown -R pda:pda /work /app
USER pda
WORKDIR /work
ENTRYPOINT ["/bin/sh", "/entrypoint.sh"]

FROM base AS real
USER root
COPY --from=node /usr/local/bin/node /usr/local/bin/node
COPY --from=node /usr/local/lib/node_modules /usr/local/lib/node_modules
RUN ln -s /usr/local/lib/node_modules/npm/bin/npm-cli.js /usr/local/bin/npm && \
    ln -s /usr/local/lib/node_modules/npm/bin/npx-cli.js /usr/local/bin/npx

USER pda
