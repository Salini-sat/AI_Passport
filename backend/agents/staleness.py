import os
import json
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

client = OpenAI(
    api_key=os.getenv("GROQ_API_KEY"),
    base_url="https://api.groq.com/openai/v1",
)

# 8B is fine â€” staleness is mostly deterministic
MODEL = "llama-3.1-8b-instant"

# Thresholds in days
STALE_THRESHOLD    = 90   # >90 days = stale
CRITICAL_THRESHOLD = 180  # >180 days = critical


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# STEP 1 â€” Deterministic freshness check
# No LLM needed for the core logic
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
def _check_freshness(product: dict) -> dict:
    """
    Checks how fresh the product data is.
    Returns freshness metrics.
    """
    days = product.get("days_since_update")

    if days is None:
        return {
            "days_since_update": None,
            "freshness_status":  "unknown",
            "is_stale":          False,
            "is_critical":       False,
            "freshness_score":   50,
        }

    # Score: 100 at 0 days, 0 at 365+ days
    freshness_score = max(0, round(100 - (days / 365) * 100))

    if days > CRITICAL_THRESHOLD:
        status   = "critical"
        is_stale = True
        is_crit  = True
    elif days > STALE_THRESHOLD:
        status   = "stale"
        is_stale = True
        is_crit  = False
    elif days > 30:
        status   = "aging"
        is_stale = False
        is_crit  = False
    else:
        status   = "fresh"
        is_stale = False
        is_crit  = False

    return {
        "days_since_update": days,
        "freshness_status":  status,
        "is_stale":          is_stale,
        "is_critical":       is_crit,
        "freshness_score":   freshness_score,
    }


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# STEP 2 â€” LLM staleness impact analysis
# Only called if product is stale
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
def _analyze_staleness_impact(product: dict, freshness: dict) -> dict:
    """
    Explains the business impact of stale data
    for AI recommendation engines.
    Only runs if product is stale.
    """
    days   = freshness["days_since_update"]
    status = freshness["freshness_status"]

    prompt = f"""You are an AI shopping agent evaluating whether product data is fresh enough to recommend.

PRODUCT: {product['title']}
PRICE: ${product.get('price', 'unknown')}
LAST UPDATED: {days} days ago
STATUS: {status}
IN STOCK: {product.get('available', 'unknown')}
INVENTORY: {product.get('inventory', 'unknown')}

AI agents distrust stale product data because:
- Prices may have changed
- Products may be discontinued
- Inventory shown may be inaccurate
- Seasonal products may no longer be relevant

Evaluate the impact of this staleness on AI recommendation quality.

Return ONLY valid JSON, no extra text:
{{
  "impact_summary": "one sentence on how staleness affects AI recommendations",
  "specific_risks": [
    "specific risk 1 for this product type",
    "specific risk 2"
  ],
  "recommendation_impact": "high" or "medium" or "low",
  "should_flag_to_merchant": true or false
}}
"""

    response = client.chat.completions.create(
        model=MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.1,
        max_tokens=300,
    )

    raw = response.choices[0].message.content.strip()
    raw = raw.replace("```json", "").replace("```", "").strip()

    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {
            "impact_summary":         f"Product data is {days} days old and may be inaccurate.",
            "specific_risks":         ["Price may have changed", "Inventory may be incorrect"],
            "recommendation_impact":  "medium",
            "should_flag_to_merchant": True,
        }


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# MAIN â€” run_staleness_agent
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
def run_staleness_agent(product: dict) -> dict:
    """
    Full staleness audit for one normalized product.
    """
    print(f"  [staleness] Auditing: {product['title']}")

    freshness = _check_freshness(product)
    score     = freshness["freshness_score"]

    # Only call LLM if product is actually stale
    if freshness["is_stale"]:
        impact = _analyze_staleness_impact(product, freshness)
    else:
        impact = {
            "impact_summary":         "Product data is fresh and reliable for AI recommendations.",
            "specific_risks":         [],
            "recommendation_impact":  "low",
            "should_flag_to_merchant": False,
        }

    # Severity
    if freshness["is_critical"]:
        severity = "critical"
    elif freshness["is_stale"]:
        severity = "high"
    elif freshness["freshness_status"] == "aging":
        severity = "medium"
    else:
        severity = "low"

    # Fix advice â€” always deterministic, no LLM needed
    fixes = {}
    if freshness["is_stale"]:
        fixes = {
            "action":      "Update this product in Shopify admin to refresh its timestamp",
            "priority":    "high" if freshness["is_critical"] else "medium",
            "what_to_update": [
                "Review and update the product description",
                "Verify current price is accurate",
                "Check and update inventory quantity",
                "Add any new tags or collections that apply",
                "Refresh product images if outdated",
            ]
        }

    return {
        "agent":              "staleness",
        "score":              score,
        "severity":           severity,
        "days_since_update":  freshness["days_since_update"],
        "freshness_status":   freshness["freshness_status"],
        "is_stale":           freshness["is_stale"],
        "impact_summary":     impact["impact_summary"],
        "specific_risks":     impact.get("specific_risks", []),
        "recommendation_impact": impact.get("recommendation_impact", "low"),
        "fixes":              fixes,
    }


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# Quick test:
#   python agents/staleness.py
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
        result = run_staleness_agent(product)

        print(f"PRODUCT   : {product['title']}")
        print(f"SCORE     : {result['score']}/100")
        print(f"SEVERITY  : {result['severity'].upper()}")
        print(f"STATUS    : {result['freshness_status'].upper()}")
        print(f"DAYS OLD  : {result['days_since_update']}")
        print(f"IMPACT    : {result['impact_summary']}")

        if result["specific_risks"]:
            print(f"RISKS:")
            for r in result["specific_risks"]:
                print(f"  âš  {r}")

        if result["fixes"]:
            print(f"ACTION    : {result['fixes']['action']}")