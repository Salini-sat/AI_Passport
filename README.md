# AI Product Passport Engine — Backend

A merchant-facing diagnostic tool that helps Shopify stores understand how AI shopping agents perceive and represent them — and what to fix.

---

## The Problem

When an AI agent (ChatGPT Shopping, Perplexity, Claude) recommends products, it pulls entirely from structured store data. If that data is incomplete, ambiguous, or contradictory, the AI either skips the product or misrepresents it.

Research backing this:
- **40%** of Shopify products are invisible to AI agents due to missing structured data
- **31%** of revenue is lost due to poor product data quality in AI recommendations
- **51%** of Gen Z now starts product search in ChatGPT/Gemini — bypassing Google

We identified 5 root causes of AI invisibility and built one agent for each.

---

## What We Built

A Python/FastAPI backend that:
1. Connects to a Shopify store via the Admin GraphQL API
2. Runs 5 specialized AI agents on each product in parallel
3. Returns a structured **AI Passport** — scores, gaps, auto-generated fixes, and a ranked action plan
4. Simulates live AI perception: "would Claude recommend your product for this query?"
5. Compares your store against competitors to show where you're losing

---

## Architecture

```
POST /analyze
     │
     ├── scraper.py          Shopify GraphQL API → raw product data
     │        │              (products + metafields + collections)
     │        ▼
     ├── normalizer.py       Raw data → clean, flat product dicts
     │        │              Strips HTML, computes signals, flattens metafields
     │        ▼
     ├── orchestrator.py     Fans out to all 5 agents per product (parallel)
     │        │              ThreadPoolExecutor — ~8s vs ~25s sequential
     │        ├── agents/visibility.py      Field presence audit
     │        ├── agents/hallucination.py   Claim verification
     │        ├── agents/context.py         Shopper query simulation
     │        ├── agents/trust.py           Trust signal evaluation
     │        └── agents/staleness.py       Data freshness check
     │        │
     │        ▼
     └── Weighted score aggregation → Passport JSON

POST /perceive
     │
     └── Groq (llama-3.3-70b) simulates AI shopping agent
         Given raw store data → recommends products for a query
         apply_fixes=true → uses passport-fixed data (before/after demo)

POST /compare
     │
     └── competitor.py
         Scrapes public Shopify stores (/products.json)
         Runs same passport pipeline on each
         Returns side-by-side gap analysis
```

---

## The 5 Agents

Each agent follows the same pattern: deterministic pre-check → LLM analysis → fix copy generation.

### 1. Visibility Agent (`agents/visibility.py`)
**Problem:** Products with missing structured fields are skipped entirely by AI agents.

- **What it checks:** 12 required fields (title, description, product_type, tags, collections, price, inventory, SKU, images, alt text, SEO title, SEO description)
- **How:** Deterministic field presence check (no LLM needed for scoring)
- **LLM role:** Explains *why* each missing field hurts AI discoverability
- **Fix output:** Generates ready-to-paste description, tags, SEO copy
- **Model:** `llama-3.1-8b-instant` (fast, field-checking doesn't need heavy reasoning)
- **Weight:** 30% of overall score

### 2. Hallucination Agent (`agents/hallucination.py`)
**Problem:** LLMs invent product features not in the data, damaging trust and causing wrong recommendations.

- **What it checks:** Claims in the description against verified structured data (ground truth)
- **How:** Builds a ground truth dict from structured fields, asks LLM to find unverifiable claims
- **LLM role:** Identifies claims like "Award-winning" or "Eco-certified" with no backing metafield
- **Fix output:** Rewrites description replacing unverifiable claims with grounded alternatives
- **Model:** `llama-3.3-70b-versatile` (needs strong reasoning to judge claim credibility)
- **Weight:** 30% of overall score

### 3. Context Collapse Agent (`agents/context.py`)
**Problem:** AI agents can't match products to shopper queries without use-case context.

- **What it checks:** Whether the product would surface for 5 realistic shopper queries
- **How:** Generates category-specific queries, scores each for surfaceability given current data
- **LLM role:** Simulates an AI shopping agent deciding whether to recommend the product
- **Fix output:** Use-case tags, target audience, context description
- **Model:** `llama-3.3-70b-versatile` (needs to simulate real shopper intent)
- **Weight:** 20% of overall score

### 4. Trust Gap Agent (`agents/trust.py`)
**Problem:** AI agents hedge or skip products they can't verify, outputting "this product seems to be..." instead of confident recommendations.

- **What it checks:** Reviews, certifications, warranty, price consistency, inventory accuracy
- **How:** Extracts trust signals from metafields + variants, evaluates confidence level
- **LLM role:** Judges whether an AI would trust and confidently recommend this product
- **Fix output:** Metafields to add, review prompt copy, trust-building description sentences
- **Model:** `llama-3.3-70b-versatile` (credibility judgment requires reasoning)
- **Weight:** 15% of overall score

### 5. Staleness Agent (`agents/staleness.py`)
**Problem:** LLM training cutoffs mean AI systems distrust old product data — recommending stale products damages brand credibility.

- **What it checks:** Days since `updatedAt` timestamp
- **How:** Deterministic — stale if >90 days, critical if >180 days
- **LLM role:** Only called if product IS stale — explains business impact
- **Fix output:** Checklist of what to update in Shopify admin
- **Model:** `llama-3.1-8b-instant` (mostly deterministic, LLM rarely needed)
- **Weight:** 5% of overall score

---

## Scoring System

### Weighted Overall Score
```
overall = (visibility × 0.30) + (hallucination × 0.30) +
          (context × 0.20) + (trust × 0.15) + (staleness × 0.05)
```

Weights reflect severity from research: Critical agents (visibility, hallucination) = 60% combined. This means a store with beautiful copy but missing fields still scores poorly — which is the correct behavior.

### Score Interpretation
| Score | Grade | Meaning |
|-------|-------|---------|
| 90–100 | A | Fully AI-ready |
| 70–89 | B | Minor gaps |
| 50–69 | C | Significant invisibility risk |
| <50 | D | Critical — majority invisible to AI |

### Revenue at Risk Formula
```
invisibility_pct = (100 - overall_score) / 100
at_risk = monthly_revenue × invisibility_pct × 0.31
```
The 0.31 multiplier comes from research: 31% of revenue is impacted by AI recommendation quality.

---

## Key Design Decisions

### Why parallel agents (ThreadPoolExecutor)?
Each agent makes 1–2 Groq API calls. Sequential execution = ~25s for 5 agents. Parallel = ~8s. For a demo this difference is the line between judges staying engaged and checking their phones.

### Why separate models for different agents?
`llama-3.1-8b-instant` for visibility and staleness (deterministic field-checking — no heavy reasoning needed, faster, uses less of the free rate limit). `llama-3.3-70b-versatile` for hallucination, context, trust (judgment calls requiring genuine reasoning). This splits the Groq rate limit across two model quotas.

### Why Groq instead of Anthropic/OpenAI?
Free tier, no credit card required, LPU inference is fast (~500ms per call). For a hackathon with potentially 100+ test runs, cost-free matters. The OpenAI-compatible SDK means switching to Claude/GPT-4 is a one-line model string change if needed for production.

### Why deterministic pre-checks before LLM calls?
The visibility agent's field check and staleness agent's timestamp check are pure Python — no API call needed. This means: (1) they never fail due to rate limits, (2) they're instant, (3) they produce consistent scores. LLM is only called when judgment is actually needed.

### Why auto-fix copy inside each agent?
The original design had a separate "fixer" module. We moved fix generation into each agent because: (1) the agent already has the context to write the fix, (2) it saves one round-trip to normalize results, (3) it keeps each agent self-contained and independently testable.

### Why limit to 3–5 products per analysis?
Groq's free tier allows 30 requests/minute on the 70B model. 5 agents × 5 products = 25 calls, approaching the limit. 3 products = 15 calls, safely under. For demo purposes 3 products tells the full story. Production would use batching and caching.

### Why public /products.json for competitor analysis?
The Shopify Admin API requires per-store OAuth. Public stores expose `/products.json` without authentication. This lets merchants analyze any competitor without needing their credentials — the core use case for competitive intelligence.

---

## API Reference

### `POST /analyze`
Runs full 5-agent passport analysis on a store.

**Request:**
```json
{
  "store_url": "your-store.myshopify.com",
  "shopify_token": "shpat_...",
  "monthly_revenue": 10000,
  "product_limit": 3
}
```

**Response:**
```json
{
  "success": true,
  "store": "your-store.myshopify.com",
  "store_score": 67,
  "revenue_at_risk": {
    "formatted_monthly": "$1,023",
    "formatted_annually": "$12,276",
    "at_risk_pct": 10.2
  },
  "store_summary": {
    "products_analyzed": 3,
    "invisible_products": 3,
    "invisible_pct": 100,
    "top_missing_fields": ["seo_title", "description", "sku"],
    "worst_product": "The Inventory Not Tracked Snowboard"
  },
  "products": [
    {
      "title": "The Inventory Not Tracked Snowboard",
      "overall_score": 64,
      "scores": {
        "visibility": 75,
        "hallucination": 100,
        "context": 20,
        "trust": 30,
        "staleness": 100
      },
      "action_plan": [
        {
          "priority": 1,
          "agent": "context",
          "label": "Add use-case context and tags",
          "severity": "critical",
          "score": 20,
          "score_gain": 12,
          "fixes": {
            "use_case_tags": ["Advanced", "All-Mountain", "High-Speed"],
            "context_description": "Designed for experienced riders..."
          }
        }
      ]
    }
  ]
}
```

### `POST /perceive`
Simulates how an AI shopping agent perceives the store for a specific query.

**Request:**
```json
{
  "store_url": "your-store.myshopify.com",
  "shopify_token": "shpat_...",
  "query": "best snowboard for beginners",
  "apply_fixes": false
}
```

**Response:**
```json
{
  "success": true,
  "query": "best snowboard for beginners",
  "context_used": "RAW STORE DATA",
  "can_answer_query": false,
  "recommended_products": [],
  "products_skipped": [
    {
      "title": "The Inventory Not Tracked Snowboard",
      "reason": "No description or skill level information available"
    }
  ],
  "overall_response": "I don't have enough information...",
  "missing_data_summary": "Product descriptions and skill level tags needed"
}
```

Set `apply_fixes: true` to get the passport-optimized response — this is the **before/after demo**.

### `POST /compare`
Runs passport on your store + competitors, returns gap analysis.

**Request:**
```json
{
  "store_url": "your-store.myshopify.com",
  "shopify_token": "shpat_...",
  "competitor_urls": ["https://kith.com"],
  "monthly_revenue": 10000
}
```

**Response:**
```json
{
  "success": true,
  "summary": "Your store (67/100) outperforms kith.com (49/100) by 18 points.",
  "stores": [
    {"store": "your-store.myshopify.com", "is_yours": true, "store_score": 67},
    {"store": "kith.com", "is_yours": false, "store_score": 49}
  ],
  "gaps": [
    {
      "agent": "context",
      "label": "Shopper query matching",
      "your_score": 33,
      "their_score": 72,
      "gap": 39,
      "urgency": "critical",
      "message": "You're losing on Shopper query matching: 33 vs 72"
    }
  ],
  "wins": [
    {
      "agent": "hallucination",
      "label": "Claim accuracy",
      "your_score": 100,
      "their_score": 23
    }
  ]
}
```

---

## Project Structure

```
backend/
├── main.py              FastAPI app — 3 routes: /analyze /perceive /compare
├── scraper.py           Shopify GraphQL API fetcher (products, metafields, collections)
│                        + fetch_store_data_public() for competitor stores
├── normalizer.py        Raw Shopify data → clean product dicts + pre-computed signals
├── orchestrator.py      Parallel agent runner + score aggregator + revenue calculator
├── competitor.py        Public store scraper + gap comparison logic
├── agents/
│   ├── __init__.py
│   ├── visibility.py    Field audit + fix copy
│   ├── hallucination.py Claim verification + description rewrite
│   ├── context.py       Query simulation + use-case fixes
│   ├── trust.py         Trust signal evaluation + metafield suggestions
│   └── staleness.py     Freshness check + update checklist
├── .env                 API keys (never committed)
├── requirements.txt
└── README.md
```

---

## Setup

### Prerequisites
- Python 3.11+
- Shopify store with Admin API access
- Groq API key (free at console.groq.com)

### Install
```bash
pip install fastapi uvicorn anthropic httpx python-dotenv openai
```

### Environment
Create `.env` in the root:
```
GROQ_API_KEY=gsk_...
SHOPIFY_STORE=your-store.myshopify.com
SHOPIFY_TOKEN=shpat_...
```

### Run
```bash
python -m uvicorn main:app --reload --port 8000
```

### Test
```
http://localhost:8000/docs   ← interactive API docs
http://localhost:8000        ← health check
```

---

## Failure Handling

| Failure | Behaviour |
|---------|-----------|
| Groq rate limit (429) | Agent retries once after 10s, returns neutral score (50) on second failure — analysis continues |
| Agent crash | `_run_agent_safe()` catches exception, returns neutral score — other 4 agents unaffected |
| No products found | 404 with clear error message |
| Invalid Shopify token | Shopify returns 401, propagated as 500 with message |
| Competitor store blocks public access | Error logged per-store, your store result still returned |
| JSON parse failure from LLM | Try/catch returns `{"error": "parse failed"}` — score defaults to 50 |

---

## Tech Stack

| Layer | Choice | Reason |
|-------|--------|--------|
| Framework | FastAPI | Async, auto docs at /docs, Pydantic validation |
| LLM (complex agents) | Groq llama-3.3-70b-versatile | Best free reasoning model, fast LPU inference |
| LLM (simple agents) | Groq llama-3.1-8b-instant | Fast + cheap for deterministic-adjacent tasks |
| Shopify data | GraphQL Admin API 2025-01 | Richer than REST (metafields, SEO, inventory) |
| Competitor data | Public /products.json | No auth needed, works on any Shopify store |
| Parallelism | ThreadPoolExecutor | Cuts per-store analysis from ~25s to ~8s |

---

## What the Passport Fixes

| Problem | Root cause | Agent | Fix generated |
|---------|-----------|-------|--------------|
| Product invisible to AI | Missing description, tags, product type | Visibility | Ready-to-paste description + tags |
| AI hallucinates features | Unverifiable claims in description | Hallucination | Rewritten grounded description |
| Product not surfaced for queries | No use-case context | Context | Use-case tags + audience copy |
| AI hedges recommendation | No reviews, certs, or trust signals | Trust | Metafields to add + review prompt |
| AI distrusts product data | Last updated 90+ days ago | Staleness | Update checklist |

---

## Demo Script (60 seconds)

1. Paste store URL → click Analyze → watch agents run live
2. Show dashboard: **66/100**, **$1,054/month at risk**, 3/3 products invisible
3. Go to Perceive → type "best snowboard for beginners"
4. **Before:** `can_answer_query: false`, confidence 40%, products skipped
5. **After** (apply fixes): `can_answer_query: true`, confidence 80%, product recommended with reason
6. Go to Compare → enter competitor URL → show gap: "You're losing on context: 33 vs 72"
7. One sentence: *"Same store. Same query. The only difference is the AI Passport."*

---

*Built for Kasparro Agentic Commerce Hackathon — Track 5: AI Representation Optimizer*
