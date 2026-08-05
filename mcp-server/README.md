# MCP server — AI Visibility Index

The Model Context Protocol server behind [dabyte.ai](https://dabyte.ai/) and
[dablock.ai](https://dablock.ai/). It exposes the weekly AI-visibility
measurements to any MCP client — Claude, ChatGPT, Cursor and others.

**Live endpoints** (streamable HTTP, JSON-RPC 2.0, no auth, no API key):

```
https://dabyte.ai/mcp     SaaS & AI tools — 20 brands
https://dablock.ai/mcp    Crypto & Web3 — 24 brands
```

Listed in the [official MCP registry](https://registry.modelcontextprotocol.io)
as `ai.dabyte/visibility-index` and `ai.dablock/visibility-index`.

## Tools

| Tool | Returns |
|---|---|
| `get_visibility_index` | Every tracked brand: rank, share of answer overall and per engine, commercial intent, quadrant |
| `get_brand_visibility` | One brand by slug: per-engine share, rank, quadrant, prompts named in |
| `list_tracked_brands` | All tracked brands with their slugs |
| `get_history` | Share of answer per brand at every published weekly measurement |
| `get_methodology` | Prompt panel, engines, scoring rules, measurement resolution, editorial firewall |

## Try it

```bash
curl -X POST https://dabyte.ai/mcp \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/list"}'
```

```bash
curl -X POST https://dablock.ai/mcp \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/call",
       "params":{"name":"get_brand_visibility","arguments":{"slug":"coinbase"}}}'
```

## How it works

One process serves both sites; the site is selected by the `Host` header. Every
tool reads the same JSON files the websites publish, straight from disk at call
time — so the server can never drift from what a human reader sees, and a new
weekly measurement needs no redeploy.

Stateless by design: streamable HTTP permits a server with no session id, and
initialization is not required before `tools/list`.

- `server.py` — the whole server, Python standard library only, no dependencies
- `mcp-aiv.service` — systemd unit (runs as `www-data`, read-only filesystem)

Reverse proxy: point `/mcp` at `127.0.0.1:8090`, pass the `Host` header through.

## Data licence

All measurements are CC BY 4.0. Reuse them anywhere, commercially included —
attribution is the only condition. Every past measurement stays at a permanent
URL ([dabyte archive](https://dabyte.ai/archive/),
[dablock archive](https://dablock.ai/archive/)), so any figure this server
returns can be verified against the record it came from.

Placement in the index cannot be bought. Every record carries an `is_client`
flag so that claim is checkable rather than rhetorical.
