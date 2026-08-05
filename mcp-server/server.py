# -*- coding: utf-8 -*-
"""server.py — настоящий MCP-сервер сети (streamable HTTP, JSON-RPC 2.0).

ЗАЧЕМ. /.well-known/mcp.json был только ДЕСКРИПТОРОМ: перечислял tools как
статические GET-эндпоинты. Official MCP Registry валидирует сабмит живым
JSON-RPC initialize-хендшейком — дескриптор его не проходит, и значит ни
реестр, ни каталоги (PulseMCP, Glama), ни честный PR в awesome-mcp-servers нам
недоступны. Этот процесс закрывает разрыв: протокольный сервер поверх ТЕХ ЖЕ
опубликованных JSON-файлов сайта.

АРХИТЕКТУРА. Один процесс на 127.0.0.1:8090 обслуживает оба домена — сайт
выбирается по заголовку Host (nginx проксирует /mcp обоих vhost-ов сюда).
Данные читаются с диска из живого каталога сайта при каждом вызове: сервер
никогда не расходится с тем, что видит обычный читатель, и не требует
пересборки при новом замере. Стейта нет: streamable HTTP разрешает stateless-
сервер без session id, инициализация не обязательна перед tools/list.

Запуск (systemd-юнит mcp-aiv.service):
  /usr/bin/python3 /opt/media_hub/backend/mcp_server/server.py
Зависимости: стандартная библиотека. Никаких fastapi/uvicorn — меньше
поверхностей отказа, http.server для строго одного POST-эндпоинта достаточно.
"""
import json
import pathlib
import re
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

SITE_ROOT = pathlib.Path("/opt/vectory-site")
PROTOCOL_VERSIONS = {"2024-11-05", "2025-03-26", "2025-06-18"}
LATEST = "2025-06-18"

SITES = {
    "dabyte.ai": {"key": "dabyte", "brand": "DABYTE", "niche": "SaaS & AI tools"},
    "dablock.ai": {"key": "dablock", "brand": "DABLOCK", "niche": "crypto/Web3"},
}

_SLUG = re.compile(r"^[a-z0-9-]{1,80}$")


def site_for(host):
    h = (host or "").split(":")[0].lower()
    if h.startswith("www."):
        h = h[4:]
    return SITES.get(h)


def read_json(site_key, rel):
    p = SITE_ROOT / site_key / rel
    return json.loads(p.read_text(encoding="utf-8"))


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
    k = cfg["key"]
    if name == "get_visibility_index":
        return read_json(k, "api/aiv.json")
    if name == "list_tracked_brands":
        return read_json(k, "api/brands.json")
    if name == "get_history":
        return read_json(k, "api/history.json")
    if name == "get_methodology":
        return read_json(k, "api/methodology.json")
    if name == "get_brand_visibility":
        slug = str((args or {}).get("slug", "")).strip().lower()
        if not _SLUG.match(slug):
            raise ValueError(f"invalid slug {slug!r}: expected [a-z0-9-]")
        try:
            return read_json(k, f"api/brands/{slug}.json")
        except FileNotFoundError:
            known = [e.get("slug") for e in read_json(k, "api/brands.json").get("brands", [])]
            raise ValueError(f"unknown brand slug {slug!r}; valid slugs: {known}")
    raise LookupError(name)


def handle_rpc(cfg, msg):
    """Один JSON-RPC запрос -> ответ (None для нотификаций)."""
    if not isinstance(msg, dict) or msg.get("jsonrpc") != "2.0":
        return {"jsonrpc": "2.0", "id": None,
                "error": {"code": -32600, "message": "invalid JSON-RPC 2.0 message"}}
    method, mid, params = msg.get("method"), msg.get("id"), msg.get("params") or {}

    if method and method.startswith("notifications/"):
        return None
    if mid is None:
        return None                                  # прочие нотификации молча принимаем

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
                # Ошибка ИНСТРУМЕНТА (не протокола) — по спеке отдаётся как result
                # с isError, чтобы LLM могла её прочитать и поправить вызов.
                return {"jsonrpc": "2.0", "id": mid, "result": {
                    "content": [{"type": "text", "text": str(e)}], "isError": True}}
        return {"jsonrpc": "2.0", "id": mid,
                "error": {"code": -32601, "message": f"method not found: {method}"}}
    except Exception as e:                            # noqa: BLE001 — наружу только JSON-RPC
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
        # Streamable HTTP разрешает 405 на GET: SSE-стрим не поддерживаем, и это честно.
        self._send(405, {"error": "SSE not supported; POST JSON-RPC messages to this endpoint"})

    def do_POST(self):                                # noqa: N802
        cfg = site_for(self.headers.get("Host"))
        if not cfg:
            self._send(404, {"error": "unknown host"})
            return
        try:
            n = int(self.headers.get("Content-Length") or 0)
            msg = json.loads(self.rfile.read(n))
        except (ValueError, TypeError):
            self._send(400, {"jsonrpc": "2.0", "id": None,
                             "error": {"code": -32700, "message": "parse error"}})
            return
        if isinstance(msg, list):                     # батч: отвечаем на все запросы разом
            replies = [r for r in (handle_rpc(cfg, m) for m in msg) if r is not None]
            self._send(200, replies) if replies else self._send(202)
            return
        reply = handle_rpc(cfg, msg)
        self._send(200, reply) if reply is not None else self._send(202)

    def log_message(self, fmt, *args):                # журнал — в systemd
        print(f"{self.headers.get('Host', '?')} {fmt % args}")


if __name__ == "__main__":
    ThreadingHTTPServer(("127.0.0.1", 8090), Handler).serve_forever()
