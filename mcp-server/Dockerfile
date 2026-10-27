# The M-Pesa Daraja MCP server in HTTP mode. MCP is at /mcp and Daraja callbacks at /cb/<token>/..., on one port.
# Build: docker build -t mpesa-daraja mcp-server   (or docker compose up from the repo root)
FROM python:3.13-slim

RUN useradd --create-home --uid 10001 mpesa
WORKDIR /app
COPY pyproject.toml README.md LICENSE ./
COPY src ./src
RUN pip install --no-cache-dir . && mkdir /data && chown mpesa /data

USER mpesa
ENV DARAJA_STATE_DB=/data/state.db \
    DARAJA_OUTPUT_DIR=/data/qr \
    DARAJA_CONFIG_DIR=/data/config \
    DARAJA_MCP_HOST=0.0.0.0 \
    DARAJA_MCP_PORT=8000 \
    PYTHONUNBUFFERED=1
VOLUME /data
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/healthz')"

CMD ["mpesa-daraja-mcp", "serve", "--http"]
