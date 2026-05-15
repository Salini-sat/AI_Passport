import os
import json
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

client = OpenAI(
    api_key=os.getenv("GROQ_API_KEY"),
    base_url="https://api.groq.com/openai/v1",
)

# 70B for hallucination â€” needs strong reasoning
# to verify claims against raw data
MODEL = "llama-3.3-70b-versatile"


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# STEP 1 â€” Extract verifiable facts from product
# Builds the "ground truth" from structured data
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
def _build_ground_truth(product: dict) -> dict:
    """
    Extracts all verifiable facts from structured fields.
    This is what the agent checks claims AGAINST.
    Only includes fields that are actually present.
    """
    truth = {}

    if product.get("price"):
        truth["price"] = f"${product['price']}"

    if product.get("tags"):
        truth["tags"] = product["tags"]

    if product.get("product_type"):
        truth["product_type"] = product["product_type"]

    if product.get("collections"):
        truth["collections"] = product["collections"]

    if product.get("inventory") is not None:
        truth["inventory"] = product["inventory"]
        truth["available"] = product.get("available", False)

    if product.get("options"):
        truth["options"] = {
            opt["name"]: opt["values"]
            for opt in product["options"]
        }

    if product.get("metafields"):
        truth["metafields"] = product["metafields"]

    if product.get("images"):
        truth["image_count"] = product["image_count"]
        truth["image_alts"]  = [
            img["alt"] for img in product["images"] if img.get("alt")
        ]

    return truth


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# STEP 2 â€” LLM claim verification
# Checks each claim in description against truth
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
def _verify_claims(product: dict, ground_truth: dict) -> dict:
    """
    Asks Groq to find claims in the description that
    can't be verified from structured product data.
    """
    description = product.get("description", "")

    # If no description â€” nothing to hallucinate from
    if not description or len(description) < 10:
        return {
            "has_unverifiable_claims": False,
            "flagged_claims":          [],
            "verified_claims":         [],
            "hallucination_risk":      "none",
            "confidence_score":        100,
            "summary": "No description to verify â€” product has no content for AI to misrepresent.",
        }

    prompt = f"""You are an AI commerce auditor checking a product for hallucination risk.

PRODUCT TITLE: {product['title']}

PRODUCT DESCRIPTION (what the merchant wrote):
{description}

VERIFIED STRUCTURED DATA (ground truth from Shopify):
{json.dumps(ground_truth, indent=2)}

Your job: Find claims in the description that CANNOT be verified from the structured data.
These are hallucination risks â€” when an AI agent reads this product, it might repeat
unverifiable claims as facts, damaging trust and causing wrong recommendations.

Examples of unverifiable claims:
- "Award-winning formula" â€” no award data in structured fields
- "Sustainably sourced" â€” no certification or metafield confirms this
- "Best seller" â€” no sales data provided
- "Dermatologist tested" â€” no certification field exists
- "Fits true to size" â€” no size chart in metafields

Examples of verifiable claims:
- "Available in 3 colors" â€” confirmed by options field
- "Priced at $49" â€” confirmed by price field
- "Part of our Running collection" â€” confirmed by collections

Return ONLY valid JSON, no extra text:
{{
  "has_unverifiable_claims": true or false,
  "flagged_claims": [
    {{
      "claim": "exact phrase from description",
      "reason": "why this cannot be verified from structured data",
      "severity": "high" or "medium" or "low"
    }}
  ],
  "verified_claims": [
    "claim that IS backed by structured data"
  ],
  "hallucination_risk": "high" or "medium" or "low" or "none",
  "confidence_score": number 0-100 (how trustworthy this product data is),
  "summary": "one sentence summary of the hallucination risk"
}}

If description is empty or very short, return has_unverifiable_claims: false with empty arrays.
Be strict â€” only flag claims that are genuinely unverifiable, not general marketing language.
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
# Rewrites flagged claims to be grounded in truth
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
def _generate_fixes(product: dict, flagged_claims: list, ground_truth: dict) -> dict:
    """
    Rewrites the product description replacing
    unverifiable claims with grounded alternatives.
    Only runs if there are flagged claims.
    """
    if not flagged_claims:
        return {}

    description = product.get("description", "")
    claims_text = "\n".join([
        f"- \"{c['claim']}\" â†’ {c['reason']}"
        for c in flagged_claims
    ])

    prompt = f"""You are a Shopify product copywriter fixing hallucination risks in product descriptions.

PRODUCT: {product['title']}

ORIGINAL DESCRIPTION:
{description}

UNVERIFIABLE CLAIMS TO FIX:
{claims_text}

VERIFIED DATA YOU CAN USE:
{json.dumps(ground_truth, indent=2)}

Rewrite the description to:
1. Remove or replace all unverifiable claims
2. Only make claims backed by the structured data
3. Keep the same tone and marketing appeal
4. Be specific and useful for AI shopping agents

Return ONLY valid JSON, no extra text:
{{
  "fixed_description": "the full rewritten description",
  "changes_made": ["list of specific changes you made"]
}}
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
# MAIN â€” run_hallucination_agent
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
def run_hallucination_agent(product: dict) -> dict:
    """
    Full hallucination audit for one normalized product.

    Returns:
    {
      "agent":                   "hallucination",
      "score":                   int (0-100),
      "severity":                str,
      "has_unverifiable_claims": bool,
      "flagged_claims":          list,
      "verified_claims":         list,
      "hallucination_risk":      str,
      "summary":                 str,
      "fixes":                   dict,
    }
    """
    print(f"  [hallucination] Auditing: {product['title']}")

    # Step 1 â€” build ground truth from structured data
    ground_truth = _build_ground_truth(product)

    # Step 2 â€” verify claims in description against truth
    result = _verify_claims(product, ground_truth)

    # Step 3 â€” generate fixed description if needed
    flagged = result.get("flagged_claims", [])
    fixes   = _generate_fixes(product, flagged, ground_truth) if flagged else {}

    # Score: start at confidence_score, penalise per flagged claim
    base_score    = result.get("confidence_score", 100)
    penalty       = len(flagged) * 10
    score         = max(0, min(100, base_score - penalty))

    # Severity mapping
    risk          = result.get("hallucination_risk", "none")
    severity_map  = {"high": "critical", "medium": "high", "low": "medium", "none": "low"}
    severity      = severity_map.get(risk, "medium")

    return {
        "agent":                   "hallucination",
        "score":                   score,
        "severity":                severity,
        "has_unverifiable_claims": result.get("has_unverifiable_claims", False),
        "flagged_claims":          flagged,
        "verified_claims":         result.get("verified_claims", []),
        "hallucination_risk":      risk,
        "summary":                 result.get("summary", ""),
        "fixes":                   fixes,
    }


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# Quick test:
#   python agents/hallucination.py
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
        result = run_hallucination_agent(product)

        print(f"PRODUCT  : {product['title']}")
        print(f"SCORE    : {result['score']}/100")
        print(f"SEVERITY : {result['severity'].upper()}")
        print(f"RISK     : {result['hallucination_risk'].upper()}")
        print(f"SUMMARY  : {result['summary']}")

        if result["flagged_claims"]:
            print(f"FLAGGED CLAIMS:")
            for c in result["flagged_claims"]:
                print(f"  âš  \"{c['claim']}\"")
                print(f"    â†’ {c['reason']}")

        if result["verified_claims"]:
            print(f"VERIFIED CLAIMS:")
            for c in result["verified_claims"]:
                print(f"  âœ“ {c}")

        if result["fixes"]:
            print(f"FIXED DESCRIPTION (preview):")
            fixed = result["fixes"].get("fixed_description", "")
            print(f"  {fixed[:150]}...")