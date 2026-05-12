import os
import json
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

client = OpenAI(
    api_key=os.getenv("GROQ_API_KEY"),
    base_url="https://api.groq.com/openai/v1",
)

# 70B â€” needs to judge credibility of signals
MODEL = "llama-3.3-70b-versatile"


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# STEP 1 â€” Extract all trust signals
# Deterministic â€” no LLM needed
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
def _extract_trust_signals(product: dict) -> dict:
    """
    Pulls all verifiable trust signals from
    the product's structured data.
    """
    metafields = product.get("metafields", {})
    signals    = {}

    # Reviews â€” stored by common review apps
    review_keys = ["reviews.rating", "reviews.rating_count",
                   "yotpo.reviews_average", "judgeme.rating"]
    for key in review_keys:
        if key in metafields:
            signals["review_data"] = {
                "source": key,
                "value":  metafields[key]
            }
            break

    # Certifications â€” common metafield keys
    cert_keys = ["custom.certification", "custom.certifications",
                 "specs.certification", "product.certification"]
    for key in cert_keys:
        if key in metafields:
            signals["certification"] = metafields[key]
            break

    # Materials / ingredients
    mat_keys = ["custom.material", "custom.materials",
                "specs.material", "custom.ingredients"]
    for key in mat_keys:
        if key in metafields:
            signals["material"] = metafields[key]
            break

    # Warranty
    warranty_keys = ["custom.warranty", "specs.warranty"]
    for key in warranty_keys:
        if key in metafields:
            signals["warranty"] = metafields[key]
            break

    # Price consistency
    price            = product.get("price")
    compare_at_price = product.get("compare_at_price")
    if price and compare_at_price:
        signals["has_sale_price"]     = compare_at_price > price
        signals["discount_pct"]       = round(
            ((compare_at_price - price) / compare_at_price) * 100
        )

    # Inventory
    inventory = product.get("inventory")
    if inventory is not None:
        signals["inventory_tracked"] = True
        signals["in_stock"]          = inventory > 0
        signals["inventory_qty"]     = inventory
    else:
        signals["inventory_tracked"] = False

    # SKU
    signals["has_sku"] = bool(product.get("sku"))

    # Images with alt text (visual trust)
    signals["images_with_alt"]    = product.get("images_with_alt", 0)
    signals["images_missing_alt"] = product.get("images_missing_alt", 0)

    # SEO as trust signal
    signals["has_seo"] = product.get("has_seo", False)

    return signals


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# STEP 2 â€” LLM trust evaluation
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
def _evaluate_trust(product: dict, trust_signals: dict) -> dict:
    """
    Asks Groq to evaluate whether an AI agent would
    trust and recommend this product based on
    available trust signals.
    """
    prompt = f"""You are an AI shopping agent evaluating whether to trust and recommend a product.

PRODUCT: {product['title']}
PRICE: ${product.get('price', 'unknown')}
DESCRIPTION: {product.get('description', 'EMPTY')[:200]}

TRUST SIGNALS FOUND:
{json.dumps(trust_signals, indent=2)}

AI agents hedge or skip products they can't verify. They need:
- Reviews or ratings to confirm quality
- Certifications to back specific claims
- Accurate inventory to avoid recommending out-of-stock items
- Clear pricing without suspicious discounts
- SKU for precise product identification

Evaluate the trust level of this product for AI recommendation.

Return ONLY valid JSON, no extra text:
{{
  "trust_score": 0-100,
  "would_recommend": true or false,
  "hedges_recommendation": true or false,
  "trust_gaps": [
    {{
      "signal": "what trust signal is missing",
      "impact": "how this gap affects AI recommendation",
      "severity": "high" or "medium" or "low"
    }}
  ],
  "trust_strengths": ["what trust signals work well"],
  "summary": "one sentence on overall trust level",
  "recommendation_confidence": "high" or "medium" or "low" or "none"
}}

hedges_recommendation = true if the AI would say "this product seems to be..." 
instead of confidently recommending it.
would_recommend = false if trust score < 40.
"""

    response = client.chat.completions.create(
        model=MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.1,
        max_tokens=600,
    )

    raw = response.choices[0].message.content.strip()
    raw = raw.replace("```json", "").replace("```", "").strip()
    return json.loads(raw)


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# STEP 3 â€” Generate fix copy
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
def _generate_fixes(product: dict, trust_gaps: list) -> dict:
    """
    Suggests exactly what trust signals to add
    and how to structure them in Shopify.
    """
    if not trust_gaps:
        return {}

    high_gaps = [g for g in trust_gaps if g.get("severity") == "high"]
    if not high_gaps:
        high_gaps = trust_gaps[:2]

    prompt = f"""You are a Shopify trust optimization specialist.

PRODUCT: {product['title']}
PRICE: ${product.get('price', 'unknown')}

TRUST GAPS TO FIX:
{json.dumps(high_gaps, indent=2)}

For each trust gap, provide the exact content or metafield the merchant should add to Shopify.
Be practical and specific â€” give them copy they can paste directly.

Return ONLY valid JSON, no extra text:
{{
  "metafields_to_add": [
    {{
      "namespace": "custom",
      "key": "field_name",
      "value": "the actual value to enter",
      "why": "how this builds trust with AI agents"
    }}
  ],
  "review_prompt": "suggested message to send customers asking for reviews",
  "trust_copy": "2-3 sentences to add to description that build verifiable trust"
}}
"""

    response = client.chat.completions.create(
        model=MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3,
        max_tokens=500,
    )

    raw = response.choices[0].message.content.strip()
    raw = raw.replace("```json", "").replace("```", "").strip()

    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {"error": "Could not parse fix suggestions"}


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# MAIN â€” run_trust_agent
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
def run_trust_agent(product: dict) -> dict:
    """
    Full trust gap audit for one normalized product.
    """
    print(f"  [trust] Auditing: {product['title']}")

    trust_signals = _extract_trust_signals(product)
    result        = _evaluate_trust(product, trust_signals)
    trust_gaps    = result.get("trust_gaps", [])
    fixes         = _generate_fixes(product, trust_gaps) if trust_gaps else {}

    score    = result.get("trust_score", 50)
    if score < 30:
        severity = "critical"
    elif score < 55:
        severity = "high"
    elif score < 75:
        severity = "medium"
    else:
        severity = "low"

    return {
        "agent":                    "trust",
        "score":                    score,
        "severity":                 severity,
        "would_recommend":          result.get("would_recommend", False),
        "hedges_recommendation":    result.get("hedges_recommendation", True),
        "recommendation_confidence": result.get("recommendation_confidence", "low"),
        "trust_signals_found":      trust_signals,
        "trust_gaps":               trust_gaps,
        "trust_strengths":          result.get("trust_strengths", []),
        "summary":                  result.get("summary", ""),
        "fixes":                    fixes,
    }


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# Quick test:
#   python agents/trust.py
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
        result = run_trust_agent(product)

        print(f"PRODUCT    : {product['title']}")
        print(f"SCORE      : {result['score']}/100")
        print(f"SEVERITY   : {result['severity'].upper()}")
        print(f"CONFIDENCE : {result['recommendation_confidence'].upper()}")
        print(f"HEDGES     : {result['hedges_recommendation']}")
        print(f"SUMMARY    : {result['summary']}")

        if result["trust_gaps"]:
            print(f"TRUST GAPS:")
            for g in result["trust_gaps"]:
                print(f"  âœ— {g['signal']} [{g['severity']}]")
                print(f"    â†’ {g['impact']}")

        if result["trust_strengths"]:
            print(f"STRENGTHS  : {result['trust_strengths']}")

        if result["fixes"]:
            fixes = result["fixes"]
            if "metafields_to_add" in fixes:
                print(f"METAFIELDS TO ADD:")
                for mf in fixes["metafields_to_add"]:
                    print(f"  {mf['namespace']}.{mf['key']} = \"{mf['value']}\"")