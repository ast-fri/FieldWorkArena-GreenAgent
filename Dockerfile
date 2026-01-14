FROM ghcr.io/astral-sh/uv:python3.12-trixie

RUN adduser fwa
USER fwa
WORKDIR /home/fwa

COPY pyproject.toml uv.lock README.md ./
COPY src src

RUN \
    --mount=type=cache,target=/home/fwa/.cache/uv,uid=1000 \
    uv sync --locked

COPY scenarios scenarios
COPY benchmark benchmark

ENTRYPOINT ["uv", "run", "fwa-server"]
CMD ["--host", "0.0.0.0"]
EXPOSE 9009
