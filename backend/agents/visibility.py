import os
import json
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# Groq client â€” uses OpenAI-compatible SDK
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
client = OpenAI(
    api_key=os.getenv("GROQ_API_KEY"),
    base_url="https://api.groq.com/openai/v1",
)

# Use fast 8B model â€” visibility is just field
# checking, no heavy reasoning needed
MODEL = "llama-3.1-8b-instant"

# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# Required fields every AI-ready product needs
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
REQUIRED_FIELDS = [
    "title",
    "description",
    "product_type",
    "tags",
    "collections",
    "price",
    "inventory",
    "sku",
    "images",
    "has_alt_text",
    "seo_title",
    "seo_description",
]


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# STEP 1 â€” Deterministic field check
# No LLM needed. Just check signals directly.
# Fast and reliable.
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
def _check_fields(product: dict) -> dict:
    """
    Returns which required fields are present vs missing.
    Uses pre-computed signals from normalizer â€” no parsing needed.
    """
    s = product["signals"]

    field_status = {
        "title":           bool(product.get("title")),
        "description":     s["has_description"],
        "product_type":    s["has_product_type"],
        "tags":            s["has_tags"],
        "collections":     s["has_collections"],
        "price":           s["has_price"],
        "inventory":       s["has_inventory"],
        "sku":             s["has_sku"],
        "images":          s["has_images"],
        "has_alt_text":    s["has_alt_text"],
        "seo_title":       s["has_seo_title"],
        "seo_description": s["has_seo_description"],
    }

    present = [f for f, v in field_status.items() if v]
    missing = [f for f, v in field_status.items() if not v]

    # Score = % of required fields present
    score = round((len(present) / len(REQUIRED_FIELDS)) * 100)

    return {
        "present_fields": present,
        "missing_fields": missing,
        "field_score":    score,
    }


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# STEP 2 â€” LLM analysis
# Claude looks at what's missing and explains
# why it matters for AI discoverability
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
def _analyze_with_llm(product: dict, missing_fields: list[str]) -> dict:
    """
    Asks Groq to explain the impact of missing fields
    and how they affect AI agent discoverability.
    Returns structured JSON with severity + reasoning.
    """
    prompt = f"""You are an AI commerce auditor analyzing a Shopify product for AI readiness.

Product title: {product['title']}
Product type: {product['product_type'] or 'NOT SET'}
Tags: {product['tags'] or 'NONE'}
Collections: {product['collections'] or 'NONE'}
Description length: {product['signals']['description_length']} characters
Missing fields: {missing_fields}

Your job: explain why these missing fields make this product INVISIBLE to AI shopping agents.
AI agents (like ChatGPT shopping, Perplexity, Claude) rely entirely on structured data to recommend products.
If a field is missing, the AI either skips the product or hallucinates information about it.

Return ONLY valid JSON in this exact format, no extra text:
{{
  "invisible_to_ai": true or false,
  "severity": "critical" or "high" or "medium" or "low",
  "impact_summary": "one sentence explaining the main discoverability problem",
  "field_impacts": {{
    "field_name": "why this specific missing field hurts AI discoverability"
  }},
  "discoverability_score": number between 0 and 100
}}

Rules:
- invisible_to_ai = true if more than 3 critical fields are missing
- severity = critical if description OR product_type are missing
- severity = high if tags AND collections are both missing
- severity = medium if seo fields are missing
- severity = low if only sku or alt_text are missing
- discoverability_score should match field_score approximately: {round((len([f for f in REQUIRED_FIELDS if f not in missing_fields]) / len(REQUIRED_FIELDS)) * 100)}
"""

    response = client.chat.completions.create(
        model=MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.1,
        max_tokens=500,
    )

    raw = response.choices[0].message.content.strip()

    # Strip markdown code fences if model adds them
    raw = raw.replace("```json", "").replace("```", "").strip()

    return json.loads(raw)


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# STEP 3 â€” Generate fix copy
# Extra Claude call: writes the actual missing
# content the merchant can paste into Shopify
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
def _generate_fixes(product: dict, missing_fields: list[str]) -> dict:
    """
    For each missing field, generates ready-to-use content
    the merchant can copy-paste directly into Shopify.
    """
    if not missing_fields:
        return {}

    prompt = f"""You are a Shopify product copywriter helping a merchant improve their AI discoverability.

Product title: {product['title']}
Product type: {product['product_type'] or 'unknown'}
Existing tags: {product['tags'] or []}
Existing collections: {product['collections'] or []}
Current description: {product['description'] or 'EMPTY'}

These fields are MISSING and need to be created: {missing_fields}

Write the missing content so AI shopping agents can properly discover and recommend this product.
Be specific, structured, and use natural language that both humans and AI can understand.

Return ONLY valid JSON in this exact format, no extra text:
{{
  "description": "full product description (only if description is in missing fields, else omit)",
  "tags": ["tag1", "tag2", "tag3"] (only if tags missing, else omit),
  "seo_title": "SEO title" (only if seo_title missing, else omit),
  "seo_description": "SEO meta description under 160 chars" (only if seo_description missing, else omit),
  "product_type": "product type category" (only if product_type missing, else omit)
}}

Only include keys for fields that are in the missing fields list: {missing_fields}
"""

    response = client.chat.completions.create(
        model=MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3,
        max_tokens=600,
    )

    raw = response.choices[0].message.content.strip()
    raw = raw.replace("```json", "").replace("```", "").strip()

    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {"error": "Could not parse fix suggestions"}


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# MAIN â€” run_visibility_agent
# This is what orchestrator.py calls
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
def run_visibility_agent(product: dict) -> dict:
    """
    Full visibility audit for one normalized product.

    Returns:
    {
      "agent":            "visibility",
      "score":            int (0-100),
      "severity":         str,
      "invisible_to_ai":  bool,
      "present_fields":   list,
      "missing_fields":   list,
      "impact_summary":   str,
      "field_impacts":    dict,
      "fixes":            dict,   â† ready-to-paste content
    }
    """
    print(f"  [visibility] Auditing: {product['title']}")

    # Step 1 â€” deterministic field check (no API call)
    field_check = _check_fields(product)
    missing     = field_check["missing_fields"]
    score       = field_check["field_score"]

    # Step 2 â€” LLM analysis of impact
    if missing:
        llm_result = _analyze_with_llm(product, missing)
    else:
        # All fields present â€” no LLM call needed
        llm_result = {
            "invisible_to_ai":      False,
            "severity":             "low",
            "impact_summary":       "All required fields present. Product is fully AI-visible.",
            "field_impacts":        {},
            "discoverability_score": 100,
        }

    # Step 3 â€” generate fix copy for missing fields
    # Only generate fixes for fields that matter most
    fixable_fields = [
        f for f in missing
        if f in ["description", "tags", "seo_title", "seo_description", "product_type"]
    ]
    fixes = _generate_fixes(product, fixable_fields) if fixable_fields else {}

    return {
        "agent":           "visibility",
        "score":           score,
        "severity":        llm_result.get("severity", "medium"),
        "invisible_to_ai": llm_result.get("invisible_to_ai", len(missing) > 3),
        "present_fields":  field_check["present_fields"],
        "missing_fields":  missing,
        "impact_summary":  llm_result.get("impact_summary", ""),
        "field_impacts":   llm_result.get("field_impacts", {}),
        "fixes":           fixes,
    }


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# Quick test â€” run directly:
#   python agents/visibility.py
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
if __name__ == "__main__":
    import sys
    sys.path.append(".")  # so it can find scraper + normalizer

    from scraper import fetch_store_data
    from normalizer import normalize_store_data

    raw        = fetch_store_data(limit=2)
    store_data = normalize_store_data(raw)

    for product in store_data["products"]:
        print(f"\n{'='*55}")
        result = run_visibility_agent(product)

        print(f"PRODUCT  : {product['title']}")
        print(f"SCORE    : {result['score']}/100")
        print(f"SEVERITY : {result['severity'].upper()}")
        print(f"INVISIBLE: {result['invisible_to_ai']}")
        print(f"MISSING  : {result['missing_fields']}")
        print(f"IMPACT   : {result['impact_summary']}")
        if result["fixes"]:
            print(f"FIXES    :")
            for field, content in result["fixes"].items():
                preview = str(content)[:80] + "..." if len(str(content)) > 80 else str(content)
                print(f"  {field}: {preview}")