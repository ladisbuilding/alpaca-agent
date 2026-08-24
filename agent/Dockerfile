# The committee's runtime. Runs on Cloudflare Containers (linux/amd64).
#
# Everything the agent needs is baked in — there is no reliable runtime egress to install
# packages, and a container that fails to start at 9:31 on a trading morning is worse than
# a slightly larger image.
FROM --platform=linux/amd64 python:3.12-slim

WORKDIR /app

# Dependencies first so the layer caches across code changes.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ ./src/
COPY scripts/ ./scripts/

ENV PYTHONPATH=/app/src \
    PYTHONUNBUFFERED=1 \
    ALPACA_MCP_BIN=alpaca-mcp-server

# The container serves one endpoint: POST /cycle runs a committee sitting. The Worker's
# cron trigger calls it. Keeping the schedule in the Worker rather than a cron inside the
# container means the schedule is visible in wrangler.jsonc and changeable without a rebuild.
EXPOSE 8080
CMD ["python", "-m", "committee.server"]
