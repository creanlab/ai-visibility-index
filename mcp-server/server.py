# -*- coding: utf-8 -*-
"""MCP server for the AI Visibility Index (streamable HTTP, JSON-RPC 2.0).

Serves the weekly share-of-answer measurements published at dabyte.ai and
dablock.ai to any MCP client.

Design. One process serves both sites; the site is chosen by the Host header,
so a single deployment covers every domain behind the reverse proxy. Tools read
the JSON the sites already publish, from disk at call time — the server cannot
drift from what a human reader sees, and a new weekly measurement needs no
redeploy. Stateless: streamable HTTP permits a server with no session id, and
initialization is not required before tools/list.

No dependencies beyond the standard library. For a single POST endpoint,
http.server is enough and there is less that can break.

Configuration. SITE_ROOT points at the directory holding one subdirectory per
site, each with the published api/*.json files. Override with the AIV_SITE_ROOT
environment variable.
"""
import json
import os
import pathlib
import re
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

SITE_ROOT = pathlib.Path(os.getenv("AIV_SITE_ROOT", "/srv/sites"))
PROTOCOL_VERSIONS = {"2024-11-05", "2025-03-26", "2025-06-18"}
LATEST = "2025-06-18"

SITES = {
    "dabyte.ai": {"key": "dabyte", "domain": "dabyte.ai",
                  "brand": "DABYTE", "niche": "SaaS & AI tools"},
    "dablock.ai": {"key": "dablock", "domain": "dablock.ai",
                   "brand": "DABLOCK", "niche": "crypto/Web3"},
}
# AIV_SITE names the site to serve when the Host header does not. Deliberately
# has no default: see site_for().

_SLUG = re.compile(r"^[a-z0-9-]{1,80}$")


def site_for(host):
    """Pick the site from the Host header.

    Behind the reverse proxy the header names one of the domains. Standalone
    (a container, an inspector on localhost) it names neither, so AIV_SITE says
    which site to serve. That variable must be set deliberately: without it an
    unrecognised Host stays an error rather than silently serving whichever
    site happened to be first, which would answer the wrong question.
    """
    h = (host or "").split(":")[0].lower()
    if h.startswith("www."):
        h = h[4:]
    if h in SITES:
        return SITES[h]
    return SITES.get(os.getenv("AIV_SITE", ""))


def read_json(site_key, rel, domain=None):
    """Read one published JSON file.

    Prefers a local copy of the site tree, which is how the canonical instance
    runs: it serves exactly the bytes a human reader is served, with no
    redeploy between measurements. Anywhere else the directory is absent, so
    fall back to the same file over HTTPS from the site itself — that keeps
    this server runnable by anyone, not only on the machine that builds it.
    """
    p = SITE_ROOT / site_key / rel
    if p.is_file():
        return json.loads(p.read_text(encoding="utf-8"))
    if domain is None:
        raise FileNotFoundError(str(p))
    with urllib.request.urlopen(f"https://{domain}/{rel}", timeout=20) as r:
        return json.loads(r.read().decode("utf-8"))


def tools_for(cfg):
    b, n = cfg["brand"], cfg["niche"]
    return [
        {
            "name": "get_visibility_index",
            "description": (f"Full {b} AI Visibility Index for {n}: every tracked brand with "
                            f"rank, share of answer overall and per engine (ChatGPT, Perplexity, "
                            f"Gemini), commercial intent and quadrant. Weekly measurement."),
            "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False},
        },
        {
            "name": "get_brand_visibility",
            "description": ("One brand's AI visibility: share of answer per engine, rank, "
                            "quadrant, and how many panel prompts name it. Use list_tracked_brands "
                            "for valid slugs."),
            "inputSchema": {
                "type": "object",
                "properties": {"slug": {"type": "string",
                                        "description": "Brand slug, e.g. 'slack' or 'coinbase'"}},
                "required": ["slug"], "additionalProperties": False,
            },
        },
        {
            "name": "list_tracked_brands",
            "description": f"All brands tracked in the {b} index, with their slugs.",
            "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False},
        },
        {
            "name": "get_history",
            "description": ("Full measurement history: share of answer per brand at every "
                            "published weekly measurement (comparable within one panel version)."),
            "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False},
        },
        {
            "name": "get_methodology",
            "description": ("How the index is measured: prompt panel, engines, scoring rules, "
                            "measurement resolution, editorial firewall and ownership disclosure."),
            "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False},
        },
    ]


def call_tool(cfg, name, args):
    k, d = cfg["key"], cfg.get("domain")
    if name == "get_visibility_index":
        return read_json(k, "api/aiv.json", d)
    if name == "list_tracked_brands":
        return read_json(k, "api/brands.json", d)
    if name == "get_history":
        return read_json(k, "api/history.json", d)
    if name == "get_methodology":
        return read_json(k, "api/methodology.json", d)
    if name == "get_brand_visibility":
        slug = str((args or {}).get("slug", "")).strip().lower()
        if not _SLUG.match(slug):
            raise ValueError(f"invalid slug {slug!r}: expected [a-z0-9-]")
        try:
            return read_json(k, f"api/brands/{slug}.json", d)
        except (FileNotFoundError, urllib.error.HTTPError):
            known = [e.get("slug") for e in read_json(k, "api/brands.json", d).get("brands", [])]
            raise ValueError(f"unknown brand slug {slug!r}; valid slugs: {known}")
    raise LookupError(name)


def handle_rpc(cfg, msg):
    """Handle one JSON-RPC message; returns None for notifications."""
    if not isinstance(msg, dict) or msg.get("jsonrpc") != "2.0":
        return {"jsonrpc": "2.0", "id": None,
                "error": {"code": -32600, "message": "invalid JSON-RPC 2.0 message"}}
    method, mid, params = msg.get("method"), msg.get("id"), msg.get("params") or {}

    if method and method.startswith("notifications/"):
        return None
    if mid is None:
        return None                                  # accept other notifications silently

    try:
        if method == "initialize":
            want = str(params.get("protocolVersion") or LATEST)
            return {"jsonrpc": "2.0", "id": mid, "result": {
                "protocolVersion": want if want in PROTOCOL_VERSIONS else LATEST,
                "capabilities": {"tools": {"listChanged": False}},
                "serverInfo": {"name": f"{cfg['brand'].lower()}-ai-visibility",
                               "title": f"{cfg['brand']} AI Visibility Index",
                               "version": "1.0.0"},
                "instructions": (f"Open weekly AI-visibility data for {cfg['niche']}: share of "
                                 f"answer across ChatGPT, Perplexity and Gemini. All data is "
                                 f"CC BY 4.0; cite the domain when reusing numbers."),
            }}
        if method == "ping":
            return {"jsonrpc": "2.0", "id": mid, "result": {}}
        if method == "tools/list":
            # The list is five tools in under 2 KB, so it is never paginated. A
            # client that sends a cursor is working from a wrong assumption and
            # must hear so — silently returning the whole list would look like
            # the cursor was honoured.
            if params.get("cursor") is not None:
                return {"jsonrpc": "2.0", "id": mid, "error": {
                    "code": -32602,
                    "message": "this server does not paginate tools/list; omit the cursor"}}
            return {"jsonrpc": "2.0", "id": mid, "result": {"tools": tools_for(cfg)}}
        if method == "tools/call":
            name = params.get("name", "")
            try:
                data = call_tool(cfg, name, params.get("arguments"))
                return {"jsonrpc": "2.0", "id": mid, "result": {
                    "content": [{"type": "text",
                                 "text": json.dumps(data, ensure_ascii=False)}],
                    "isError": False,
                }}
            except LookupError:
                return {"jsonrpc": "2.0", "id": mid,
                        "error": {"code": -32602, "message": f"unknown tool: {name}"}}
            except ValueError as e:
                # A tool error, not a protocol error: the spec returns it as a
                # result with isError so the model can read it and retry.
                return {"jsonrpc": "2.0", "id": mid, "result": {
                    "content": [{"type": "text", "text": str(e)}], "isError": True}}
        return {"jsonrpc": "2.0", "id": mid,
                "error": {"code": -32601, "message": f"method not found: {method}"}}
    except Exception as e:                            # noqa: BLE001 — JSON-RPC errors only
        return {"jsonrpc": "2.0", "id": mid,
                "error": {"code": -32603, "message": f"internal error: {type(e).__name__}"}}


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    server_version = "aiv-mcp/1.0"

    def _send(self, code, body=None, ctype="application/json"):
        data = (json.dumps(body, ensure_ascii=False).encode()
                if isinstance(body, (dict, list)) else (body or b""))
        self.send_response(code)
        if data:
            self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers",
                         "Content-Type, Accept, MCP-Protocol-Version, Mcp-Session-Id")
        self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
        self.end_headers()
        if data:
            self.wfile.write(data)

    def do_OPTIONS(self):                             # noqa: N802
        self._send(204)

    def do_GET(self):                                 # noqa: N802
        # Streamable HTTP allows 405 on GET; we do not implement the SSE stream.
        self._send(405, {"error": "SSE not supported; POST JSON-RPC messages to this endpoint"})

    def do_POST(self):                                # noqa: N802
        cfg = site_for(self.headers.get("Host"))
        if not cfg:
            self._send(404, {"error": f"unknown host {self.headers.get('Host')!r}; "
                                      f"set AIV_SITE to one of {sorted(SITES)} to serve "
                                      f"a site regardless of Host"})
            return
        try:
            n = int(self.headers.get("Content-Length") or 0)
            msg = json.loads(self.rfile.read(n))
        except (ValueError, TypeError):
            self._send(400, {"jsonrpc": "2.0", "id": None,
                             "error": {"code": -32700, "message": "parse error"}})
            return
        if isinstance(msg, list):                     # batch: answer every request at once
            replies = [r for r in (handle_rpc(cfg, m) for m in msg) if r is not None]
            self._send(200, replies) if replies else self._send(202)
            return
        reply = handle_rpc(cfg, msg)
        self._send(200, reply) if reply is not None else self._send(202)

    def log_message(self, fmt, *args):                # logs go to the service journal
        print(f"{self.headers.get('Host', '?')} {fmt % args}")


if __name__ == "__main__":
    if os.getenv("AIV_SITE") and os.getenv("AIV_SITE") not in SITES:
        raise SystemExit(f"AIV_SITE must be one of {sorted(SITES)}, got {os.getenv('AIV_SITE')!r}")
    # Binds to localhost by default because the canonical instance sits behind a
    # reverse proxy that terminates TLS. A container needs 0.0.0.0 to be reachable.
    host = os.getenv("AIV_BIND", "127.0.0.1")
    port = int(os.getenv("AIV_PORT", "8090"))
    print(f"aiv-mcp listening on {host}:{port}, site root {SITE_ROOT}")
    ThreadingHTTPServer((host, port), Handler).serve_forever()
