import os
import json
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

client = OpenAI(
    api_key=os.getenv("GROQ_API_KEY"),
    base_url="https://api.groq.com/openai/v1",
)

# 70B â€” needs to simulate real shopper intent
MODEL = "llama-3.3-70b-versatile"


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# STEP 1 â€” Generate realistic shopper queries
# Based on product type + tags + collections
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
def _generate_queries(product: dict) -> list[str]:
    """
    Generates 5 realistic shopper queries someone
    might type into an AI shopping agent for this
    product category.
    """
    prompt = f"""You are simulating a real online shopper using an AI shopping assistant.

Product: {product['title']}
Type: {product['product_type'] or 'unknown'}
Tags: {product['tags'] or []}
Collections: {product['collections'] or []}
Price: ${product['price'] or 'unknown'}

Generate 5 realistic shopper queries that someone might ask an AI shopping agent
when looking for a product like this. Make them specific and natural â€” the way
real people actually talk to AI assistants.

Examples of good queries:
- "best snowboard for intermediate riders under $400"
- "gift card for online shopping for my teenage nephew"
- "eco-friendly running shoes for wide feet"

Return ONLY valid JSON, no extra text:
{{
  "queries": [
    "query 1",
    "query 2",
    "query 3",
    "query 4",
    "query 5"
  ]
}}
"""

    response = client.chat.completions.create(
        model=MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.4,
        max_tokens=300,
    )

    raw = response.choices[0].message.content.strip()
    raw = raw.replace("```json", "").replace("```", "").strip()

    try:
        return json.loads(raw)["queries"]
    except Exception:
        # Fallback generic queries
        return [
            f"best {product['product_type'] or product['title']}",
            f"buy {product['title']} online",
            f"{product['title']} review",
            f"affordable {product['product_type'] or 'product'} recommendation",
            f"where to buy {product['title']}",
        ]


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# STEP 2 â€” Score how well product surfaces
# for each query given its current data
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
def _score_query_fit(product: dict, queries: list[str]) -> dict:
    """
    For each query, judges whether the product's
    current data would allow an AI agent to surface
    and recommend it confidently.
    """
    # Build a summary of what data is available
    available_data = {
        "title":        product["title"],
        "description":  product["description"][:300] if product["description"] else "EMPTY",
        "product_type": product["product_type"] or "NOT SET",
        "tags":         product["tags"] or [],
        "collections":  product["collections"] or [],
        "price":        product["price"],
        "metafields":   list(product["metafields"].keys()) if product["metafields"] else [],
        "has_seo":      product["has_seo"],
    }

    prompt = f"""You are an AI shopping agent evaluating whether you can confidently recommend a product.

AVAILABLE PRODUCT DATA:
{json.dumps(available_data, indent=2)}

SHOPPER QUERIES TO EVALUATE:
{json.dumps(queries, indent=2)}

For each query, decide:
1. Would you surface this product? (yes/no)
2. How confidently? (0-100)
3. What data is missing that would help?

A product surfaces for a query when:
- Its description/tags/type clearly match the query intent
- You have enough information to make a specific recommendation
- The product has structured attributes to answer the shopper's criteria

A product FAILS to surface when:
- Description is empty â€” you have nothing to say about it
- No tags/type â€” you can't match it to the query category
- No use-case context â€” you don't know who it's for

Return ONLY valid JSON, no extra text:
{{
  "query_results": [
    {{
      "query": "exact query text",
      "surfaces": true or false,
      "confidence": 0-100,
      "missing_context": "what data would help this product surface for this query"
    }}
  ],
  "overall_context_score": 0-100,
  "context_collapse_detected": true or false,
  "worst_query": "the query this product fails most badly for",
  "root_cause": "the main reason this product fails to surface for AI queries",
  "use_case_clarity": "high" or "medium" or "low"
}}

context_collapse_detected = true if more than 3 queries fail to surface.
"""

    response = client.chat.completions.create(
        model=MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.1,
        max_tokens=700,
    )

    raw = response.choices[0].message.content.strip()
    raw = raw.replace("```json", "").replace("```", "").strip()

    return json.loads(raw)


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# STEP 3 â€” Generate fix copy
# Writes use-case tags + context that would help
# the product surface for failed queries
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
def _generate_fixes(product: dict, query_results: list, root_cause: str) -> dict:
    """
    Generates specific tags, use-case descriptions,
    and structured attributes to fix context collapse.
    """
    failed_queries = [
        q["query"] for q in query_results if not q.get("surfaces", True)
    ]

    if not failed_queries:
        return {}

    prompt = f"""You are a Shopify product data specialist fixing context collapse for AI shopping agents.

PRODUCT: {product['title']}
CURRENT TAGS: {product['tags'] or []}
CURRENT DESCRIPTION: {product['description'][:200] if product['description'] else 'EMPTY'}
ROOT CAUSE: {root_cause}

The product FAILS to surface for these shopper queries:
{json.dumps(failed_queries, indent=2)}

Generate the exact content needed to fix this. Think about:
- What use-case tags would match these queries?
- What context in the description would help AI understand who this is for?
- What structured attributes are missing?

Return ONLY valid JSON, no extra text:
{{
  "use_case_tags": ["tag1", "tag2", "tag3", "tag4", "tag5"],
  "context_description": "2-3 sentences that explicitly state who this product is for and what use cases it serves",
  "target_audience": "who this product is for",
  "use_cases": ["use case 1", "use case 2", "use case 3"]
}}
"""

    response = client.chat.completions.create(
        model=MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3,
        max_tokens=400,
    )

    raw = response.choices[0].message.content.strip()
    raw = raw.replace("```json", "").replace("```", "").strip()

    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {"error": "Could not parse fix suggestions"}


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# MAIN â€” run_context_agent
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
def run_context_agent(product: dict) -> dict:
    """
    Full context collapse audit for one normalized product.

    Returns:
    {
      "agent":                    "context",
      "score":                    int (0-100),
      "severity":                 str,
      "context_collapse_detected": bool,
      "queries_tested":           list,
      "queries_surfaced":         int,
      "queries_failed":           int,
      "worst_query":              str,
      "root_cause":               str,
      "use_case_clarity":         str,
      "fixes":                    dict,
    }
    """
    print(f"  [context] Auditing: {product['title']}")

    # Step 1 â€” generate realistic queries for this product
    queries = _generate_queries(product)

    # Step 2 â€” score how well product surfaces for each query
    result = _score_query_fit(product, queries)

    # Step 3 â€” generate fixes for failed queries
    query_results = result.get("query_results", [])
    root_cause    = result.get("root_cause", "")
    fixes         = _generate_fixes(product, query_results, root_cause)

    # Count surfaces vs failures
    surfaced = sum(1 for q in query_results if q.get("surfaces", False))
    failed   = len(query_results) - surfaced

    # Severity
    score    = result.get("overall_context_score", 50)
    if score < 30:
        severity = "critical"
    elif score < 55:
        severity = "high"
    elif score < 75:
        severity = "medium"
    else:
        severity = "low"

    return {
        "agent":                     "context",
        "score":                     score,
        "severity":                  severity,
        "context_collapse_detected": result.get("context_collapse_detected", failed > 3),
        "queries_tested":            query_results,
        "queries_surfaced":          surfaced,
        "queries_failed":            failed,
        "worst_query":               result.get("worst_query", ""),
        "root_cause":                root_cause,
        "use_case_clarity":          result.get("use_case_clarity", "low"),
        "fixes":                     fixes,
    }


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# Quick test:
#   python agents/context.py
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
if __name__ == "__main__":
    import sys
    sys.path.append(".")

    from scraper import fetch_store_data
    from normalizer import normalize_store_data

    raw        = fetch_store_data(limit=2)
    store_data = normalize_store_data(raw)

    for product in store_data["products"]:
        print(f"\n{'='*55}")
        result = run_context_agent(product)

        print(f"PRODUCT   : {product['title']}")
        print(f"SCORE     : {result['score']}/100")
        print(f"SEVERITY  : {result['severity'].upper()}")
        print(f"COLLAPSE  : {result['context_collapse_detected']}")
        print(f"SURFACED  : {result['queries_surfaced']}/5 queries")
        print(f"ROOT CAUSE: {result['root_cause']}")
        print(f"\nQUERY RESULTS:")
        for q in result["queries_tested"]:
            icon = "âœ“" if q.get("surfaces") else "âœ—"
            conf = q.get("confidence", 0)
            print(f"  {icon} [{conf:3d}%] {q['query']}")
            if not q.get("surfaces"):
                print(f"         â†’ {q.get('missing_context', '')}")
        if result["fixes"]:
            print(f"\nFIXES:")
            fixes = result["fixes"]
            if "use_case_tags" in fixes:
                print(f"  Tags    : {fixes['use_case_tags']}")
            if "target_audience" in fixes:
                print(f"  Audience: {fixes['target_audience']}")
            if "context_description" in fixes:
                print(f"  Context : {fixes['context_description'][:120]}...")