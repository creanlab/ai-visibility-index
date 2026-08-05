# Runs the MCP server standalone. No local dataset is required: with no site
# tree mounted, the server reads the same published JSON over HTTPS from
# dabyte.ai / dablock.ai, so the container works anywhere.
#
#   docker build -t aiv-mcp .
#   docker run -p 8090:8090 aiv-mcp
#   curl -X POST http://localhost:8090 -H 'Content-Type: application/json' \
#        -d '{"jsonrpc":"2.0","id":1,"method":"tools/list"}'
#
# AIV_SITE is what makes this work off a localhost Host header, and it is set
# here rather than defaulted in the code: a server that guesses which site it is
# would answer SaaS questions with crypto data. Swap it for dablock.ai to serve
# the crypto index. Mount a site tree at /srv/sites to read disk instead of HTTPS.
FROM python:3.12-slim

WORKDIR /srv/mcp-aiv
COPY mcp-server/server.py .

ENV AIV_BIND=0.0.0.0 \
    AIV_PORT=8090 \
    AIV_SITE=dabyte.ai \
    AIV_SITE_ROOT=/srv/sites \
    PYTHONUNBUFFERED=1

RUN useradd --system --no-create-home mcp-aiv
USER mcp-aiv

EXPOSE 8090
CMD ["python", "server.py"]
