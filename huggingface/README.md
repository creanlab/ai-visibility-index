---
license: cc-by-4.0
language:
- en
pretty_name: AI Visibility Index (dabyte.ai + dablock.ai)
tags:
- ai-visibility
- share-of-answer
- llm
- chatgpt
- perplexity
- gemini
- saas
- crypto
- benchmark
- time-series
size_categories:
- n<1K
---

# AI Visibility Index — weekly share-of-answer for SaaS and crypto brands

Weekly measurements of **which brands AI assistants actually name** when a buyer
asks a category question. Published as open data by [VECTORY](https://vectory.space)
on two data desks:

- **[dabyte.ai](https://dabyte.ai/)** — SaaS & AI tools (20 brands)
- **[dablock.ai](https://dablock.ai/)** — Crypto & Web3 (24 brands)

**Metric:** share of answer — the percentage of a fixed, frozen, versioned panel of
16 category buyer prompts in which an answer engine names the brand.
**Engines:** ChatGPT (OpenAI), Perplexity, Google Gemini. Re-measured weekly.

The canonical, always-current data lives on the domains (no key, no sign-up):

- https://dabyte.ai/api/aiv.json · https://dabyte.ai/api/history.json · https://dabyte.ai/aiv.csv
- https://dablock.ai/api/aiv.json · https://dablock.ai/api/history.json · https://dablock.ai/aiv.csv

Every past measurement is archived verbatim at a permanent URL
(https://dabyte.ai/archive/, https://dablock.ai/archive/), so any published delta
can be recomputed by a third party. Placement in the index cannot be bought;
every record carries an `is_client` flag so that claim is verifiable.

## Fields (aiv.json → entries[])

| field | meaning |
|---|---|
| `brand`, `domain` | tracked brand and its primary domain |
| `visibility_score` | share of answer, engine-weighted, 0–100 |
| `per_engine` | share of answer per engine (openai / perplexity / gemini) |
| `rank` | position in the index |
| `commercial_intent` | category buyer-intent score, 0–100 |
| `quadrant` | Leaders / Visibility gap / Low conversion / Low performance |
| `panel_version` | version of the frozen prompt panel that produced the score |
| `is_client` | whether the brand has any commercial relationship with the publisher |

## Citation

> DABYTE AI Visibility Index — SaaS & AI Tools. dabyte.ai
> DABLOCK AI Visibility Index — Crypto & Web3. dablock.ai

**Disambiguation:** dabyte.ai is not affiliated with databyte.tech; dablock.ai is
not affiliated with dablock.com. The AI Visibility Index lives only at
https://dabyte.ai/ and https://dablock.ai/.
