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


# Every tool here reads a published file and returns it. Nothing writes, nothing
# reaches outside these two sites, and the same call returns the same bytes until
# the next weekly release — which is exactly what these four hints state. They are
# not decoration: without them a client must assume the worst and interrupt the
# user for confirmation before a read.
#
# The hints and the prose must never disagree. Saying the server "queries the
# engines live" while declaring openWorldHint false would be a contradiction, and
# it would be a lie besides: measurement happens weekly in a separate pipeline,
# and these tools only serve what that pipeline published.
READ_ONLY = {
    "readOnlyHint": True,
    "destructiveHint": False,
    "idempotentHint": True,
    "openWorldHint": False,
}

_ENTRY = {
    "type": "object",
    "properties": {
        "brand": {"type": "string", "description": "Brand name as published."},
        "slug": {"type": "string", "description": "Identifier used by get_brand_visibility."},
        "rank": {"type": "integer", "description": "Position in this release, 1 = most named."},
        "visibility_score": {"type": "number",
                             "description": "Share of answer, percent of panel prompts naming the brand."},
        "per_engine": {"type": "object", "additionalProperties": {"type": "number"},
                       "description": "Share of answer per engine, same scale."},
        "commercial_intent": {"type": "number",
                              "description": "How commercially loaded the brand's category demand is."},
        "quadrant": {"type": "string",
                     "description": "Position on visibility against commercial intent."},
        "is_client": {"type": "boolean",
                      "description": "Whether the brand is a client of the publisher. Placement "
                                     "cannot be bought; this flag makes that checkable."},
    },
    "required": ["brand", "slug", "rank", "visibility_score"],
}

_RELEASE_META = {
    "measured_at": {"type": "string", "description": "Date of this release, ISO 8601."},
    "panel_version": {"type": "integer",
                      "description": "Prompt panel version. Figures from different versions are "
                                     "not comparable."},
    "engines": {"type": "array", "items": {"type": "string"},
                "description": "Engines measured in this release."},
    "niche_title": {"type": "string"},
}


def tools_for(cfg):
    b, n, d = cfg["brand"], cfg["niche"], cfg["domain"]
    n_note = (f"Covers {n} only; the sibling index at "
              f"{'dablock.ai' if d == 'dabyte.ai' else 'dabyte.ai'} covers the other niche.")
    freshness = ("Re-measured weekly, so the same call returns the same figures until the next "
                 "release. Data is CC BY 4.0 and free: no key, no account, no rate limit — cite "
                 f"the release date and {d} when quoting a number.")
    return [
        {
            "name": "get_visibility_index",
            "title": f"{b} AI Visibility Index — full table",
            "description": (
                f"The whole current release in one call: every tracked brand in {n} with its rank, "
                f"share of answer overall and per engine, commercial intent and quadrant. Share of "
                f"answer is the percentage of a fixed panel of category buyer prompts in which an "
                f"engine names the brand.\n\n"
                f"Use this when the question is about the field — who leads, who is absent, how the "
                f"category looks. It is one response of roughly 8 KB for {'20' if d == 'dabyte.ai' else '24'} "
                f"brands, so prefer it over calling get_brand_visibility repeatedly.\n\n"
                f"Do NOT use it for one named brand (get_brand_visibility is the direct answer), for "
                f"movement over time (get_history holds the series; a single release cannot show a "
                f"trend), or to audit a website's own AI visibility — this is a measured dataset "
                f"about third-party brands, not a site audit. {n_note}\n\n{freshness}"),
            "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False},
            "outputSchema": {
                "type": "object",
                "properties": dict(_RELEASE_META, entries={"type": "array", "items": _ENTRY}),
                "required": ["measured_at", "entries"],
            },
            "annotations": dict(READ_ONLY, title=f"{b} AI Visibility Index — full table"),
        },
        {
            "name": "get_brand_visibility",
            "title": "Look up one brand",
            "description": (
                f"One brand's standing in the current {b} release: share of answer per engine, rank, "
                f"quadrant, how many panel prompts name it, and which ones.\n\n"
                f"Use this when a specific brand is named. Takes a slug, not a display name — call "
                f"list_tracked_brands first if you are unsure, or read the slug from "
                f"get_visibility_index.\n\n"
                f"An unknown slug is not a failure to hide: the error names every valid slug, so a "
                f"second attempt can succeed. A brand absent from the index has not been measured at "
                f"all, which is different from a measured zero. Only {n} brands are tracked. "
                f"For the field as a whole use get_visibility_index; for this brand over time, "
                f"get_history.\n\n{freshness}"),
            "inputSchema": {
                "type": "object",
                "properties": {"slug": {
                    "type": "string", "pattern": "^[a-z0-9-]{1,80}$",
                    "description": ("Brand slug, lowercase with hyphens — 'slack', 'coinbase', "
                                    "'monday-com'. Not the display name."),
                }},
                "required": ["slug"], "additionalProperties": False,
            },
            "outputSchema": {
                "type": "object",
                "properties": dict(_RELEASE_META, **_ENTRY["properties"],
                                   prompts={"type": "array", "items": {"type": "string"},
                                            "description": "Panel prompts in which the brand is named."}),
                "required": ["brand", "slug", "rank", "visibility_score", "measured_at"],
            },
            "annotations": dict(READ_ONLY, title="Look up one brand"),
        },
        {
            "name": "list_tracked_brands",
            "title": "List tracked brands and slugs",
            "description": (
                f"The names and slugs of every brand in the {b} index — a lookup table, nothing else. "
                f"No scores, no ranks.\n\n"
                f"Use it for two things: to turn a brand name into the slug get_brand_visibility "
                f"needs, and to answer whether a brand is tracked at all.\n\n"
                f"Do NOT use it when you want figures — get_visibility_index returns the same brands "
                f"with their full measurements in a single call, so calling this one first is a "
                f"wasted round trip. Absence here means the brand is not measured, not that it scores "
                f"zero. {n_note}\n\n{freshness}"),
            "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False},
            "outputSchema": {
                "type": "object",
                "properties": {"brands": {"type": "array", "items": {
                    "type": "object",
                    "properties": {"brand": {"type": "string"}, "slug": {"type": "string"}},
                    "required": ["brand", "slug"]}}},
                "required": ["brands"],
            },
            "annotations": dict(READ_ONLY, title="List tracked brands and slugs"),
        },
        {
            "name": "get_history",
            "title": "Full measurement time series",
            "description": (
                f"Every {b} release ever published, as a series per brand: share of answer at each "
                f"weekly measurement with the date and panel version it was taken under.\n\n"
                f"Use this for any question about change — is a brand rising, when did it enter the "
                f"index, how volatile is the category.\n\n"
                f"Two limits decide whether an answer is honest. Figures are comparable only WITHIN a "
                f"panel version: the panel is frozen between releases and a version change alters the "
                f"denominator, so a difference across that boundary is not a trend. And one mention on "
                f"one engine is a whole scale step, since each prompt runs once per engine per "
                f"release — a movement of one step is inside the noise of a language model and should "
                f"not be reported as a gain or a loss. Call get_methodology for the exact step size. "
                f"For the current release alone use get_visibility_index.\n\n{freshness}"),
            "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False},
            "outputSchema": {
                "type": "object",
                "properties": {
                    "measurements": {"type": "array", "items": {"type": "object", "properties": {
                        "measured_at": {"type": "string"},
                        "panel_version": {"type": "integer"}}}},
                    "series": {"type": "object", "additionalProperties": {"type": "array"},
                               "description": "Per brand slug, the share of answer at each release."},
                },
            },
            "annotations": dict(READ_ONLY, title="Full measurement time series"),
        },
        {
            "name": "get_methodology",
            "title": "How the index is measured",
            "description": (
                f"The rules behind every figure this server returns: the exact prompt panel and its "
                f"version, which engines were measured, how share of answer is scored and rounded, the "
                f"resolution of the scale in percentage points, and the editorial firewall and "
                f"ownership disclosure.\n\n"
                f"Call this before quoting a number as evidence, before comparing two releases, or "
                f"whenever a user asks how the measurement was made or who publishes it. It is the "
                f"only tool that tells you how much of a difference is meaningful, which is what "
                f"stops a one-step wobble being reported as a movement.\n\n"
                f"It returns rules, not figures — no brand appears in the response. For figures use "
                f"get_visibility_index or get_brand_visibility; for the series, get_history. "
                f"The panel is public and frozen between releases, so every published number can be "
                f"recomputed by a third party from the archive at https://{d}/archive/.\n\n{freshness}"),
            "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False},
            "outputSchema": {
                "type": "object",
                "properties": dict(
                    _RELEASE_META,
                    prompt_panel={"type": "array", "items": {"type": "string"},
                                  "description": "The exact prompts, verbatim."},
                    scoring={"type": "string", "description": "How share of answer is computed."},
                    resolution={"type": "string",
                                "description": "Percentage points one mention on one engine is worth."},
                    license={"type": "string"},
                    publisher={"type": "string"},
                ),
            },
            "annotations": dict(READ_ONLY, title="How the index is measured"),
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
                # Every tool declares an outputSchema, so the payload goes back as
                # structuredContent — a model reading measurements should not have to
                # re-parse them out of a string it was handed. The text block stays
                # beside it: the spec requires it for clients that predate structured
                # results, and dropping it would break them for no gain.
                return {"jsonrpc": "2.0", "id": mid, "result": {
                    "content": [{"type": "text",
                                 "text": json.dumps(data, ensure_ascii=False)}],
                    "structuredContent": data,
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
