# AI Visibility Index — open weekly data (dabyte.ai · dablock.ai)

Weekly measurements of **which brands AI assistants actually name** when a buyer asks
a category question — published as open data by [VECTORY](https://vectory.space) on two
data desks:

| Site | Niche | Brands | Live data |
|---|---|---|---|
| **[dabyte.ai](https://dabyte.ai/)** | SaaS & AI tools | 20 | [aiv.json](https://dabyte.ai/api/aiv.json) · [history](https://dabyte.ai/api/history.json) · [CSV](https://dabyte.ai/aiv.csv) |
| **[dablock.ai](https://dablock.ai/)** | Crypto & Web3 | 24 | [aiv.json](https://dablock.ai/api/aiv.json) · [history](https://dablock.ai/api/history.json) · [CSV](https://dablock.ai/aiv.csv) |

This repository is a **mirror** for discovery and reproducibility. The canonical,
always-current data lives on the domains above — no key, no sign-up, machine-first
(JSON, CSV, markdown mirrors, [llms.txt](https://dabyte.ai/llms.txt), MCP tools at
`/.well-known/mcp.json`).

## What is measured

**Share of answer**: the percentage of a fixed panel of category buyer prompts
(16 per niche, frozen and versioned) in which an answer engine names the brand.
Engines measured: **ChatGPT (OpenAI), Perplexity, Google Gemini** — each prompt run
per engine, per release, weekly.

Example, measured 2026-08-04 (panel v2, first 3-engine release):

- dabyte.ai — Slack 33.3% · Notion 29.2% · HubSpot 22.9%
- dablock.ai — Coinbase 41.5% · Binance 26.9% · Kraken 25.0%

Rules that make the numbers citable:

- **The panel is frozen between releases** and any change bumps a panel version;
  deltas are never computed across panel versions ([methodology](https://dabyte.ai/methodology/)).
- **Every past measurement is archived verbatim** at a permanent URL
  ([dabyte archive](https://dabyte.ai/archive/), [dablock archive](https://dablock.ai/archive/)),
  so any published delta can be recomputed by a third party.
- **Placement cannot be bought.** No brand can pay to enter, move inside, or leave
  the index; every machine record carries an `is_client` flag so the claim is
  verifiable rather than rhetorical.
- Measurement resolution is disclosed (one mention on one engine = one scale step);
  movements within one step are never reported as changes.

## Files

```
data/
  dabyte/    aiv.json · aiv.csv · history.json · rankings.json
  dablock/   aiv.json · aiv.csv · history.json · rankings.json
scripts/
  fetch_latest.py   — refresh this mirror from the live endpoints
```

`aiv.json` — current measurement: per-brand share of answer overall and per engine,
rank, commercial-intent score, quadrant, panel version.
`history.json` — full per-brand time series across all published measurements.
`rankings.json` — derived rankings (most visible, invisible-despite-demand, movers).

## Citation

> DABYTE AI Visibility Index — SaaS & AI Tools, 2026-08-04. dabyte.ai

> DABLOCK AI Visibility Index — Crypto & Web3, 2026-08-04. dablock.ai

Two licences, because this repository holds two different things. The **datasets under
`data/`** are **CC BY 4.0** (`data/LICENSE`) — free for any use, including commercial,
with attribution. The **code** (`scripts/`, `mcp-server/`) is **MIT** (`LICENSE`).

## MCP server

The index is also an [MCP](https://modelcontextprotocol.io) server, so an assistant can
query it directly. Hosted endpoints need no installation:

```
https://dabyte.ai/mcp     SaaS & AI tools
https://dablock.ai/mcp    Crypto & Web3
```

To run your own — no dataset required, it reads the published JSON over HTTPS:

```bash
docker build -t aiv-mcp . && docker run -p 8090:8090 aiv-mcp
```

Tool reference and client setup: [`mcp-server/README.md`](mcp-server/README.md).

## Disambiguation

**dabyte.ai** is not affiliated with databyte.tech, DataByte, or any similarly named
company. **dablock.ai** is not affiliated with dablock.com. Both are data desks
published by [VECTORY](https://vectory.space); the AI Visibility Index lives only at
https://dabyte.ai/ and https://dablock.ai/.

## Contributing data

Companies can contribute their own primary datasets (observed pricing, discount
bands, usage telemetry, benchmark results) for free open publication with
attribution — see [dabyte.ai/contribute](https://dabyte.ai/contribute/) and
[dablock.ai/contribute](https://dablock.ai/contribute/). Contributing never affects
a score in the index.
