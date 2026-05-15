import os
import sys
import json
import httpx
from dotenv import load_dotenv
import time

sys.path.append(".")
load_dotenv()


# ─────────────────────────────────────────────
# Public Shopify scraper
# Every Shopify store exposes /products.json
# publicly — no API token needed
# ─────────────────────────────────────────────
def fetch_competitor_products(store_domain: str, limit: int = 3) -> dict:
    """
    Fetches products from ANY public Shopify store.
    Uses the open /products.json endpoint.
    No API token needed.

    Works on: allbirds.com, gymshark.com, etc.
    Any store running on Shopify.
    """
    # Clean domain
    domain = store_domain.strip().rstrip("/")
    domain = domain.replace("https://", "").replace("http://", "")
    domain = domain.split("/")[0]

    url = f"https://{domain}/products.json?limit={limit}"
    print(f"  [competitor] Fetching: {url}")

    response = httpx.get(url, timeout=15, follow_redirects=True)
    response.raise_for_status()

    raw_products = response.json().get("products", [])

    if not raw_products:
        raise ValueError(f"No products found at {url}. Store may not be public or not on Shopify.")

    products = []
    for p in raw_products:
        first_variant = p["variants"][0] if p.get("variants") else {}
        images        = p.get("images", [])

        products.append({
            "id":           f"gid://shopify/Product/{p['id']}",
            "title":        p.get("title", ""),
            "description":  p.get("body_html", ""),
            "product_type": p.get("product_type", ""),
            "tags": p["tags"] if isinstance(p["tags"], list) else [t.strip() for t in p["tags"].split(",")] if p.get("tags") else [],
            "status":       "ACTIVE",
            "updated_at":   p.get("updated_at", ""),
            "store_url":    None,
            "seo": {
                "title":       "",
                "description": "",
            },
            "images": [
                {"url": img.get("src", ""), "alt": img.get("alt")}
                for img in images
            ],
            "variants": [{
                "id":                first_variant.get("id", ""),
                "title":             first_variant.get("title", ""),
                "price":             first_variant.get("price"),
                "compare_at_price":  first_variant.get("compare_at_price"),
                "available":         first_variant.get("available", False),
                "inventoryQuantity": None,  # not exposed publicly
                "sku":               first_variant.get("sku", ""),
            }],
            "options":    p.get("options", []),
            "metafields": [],      # not exposed publicly
            "collections": [],     # fetched separately below
        })

    # Try to fetch collections publicly too
    collections = _fetch_public_collections(domain)

    # Attach collection names to products
    for product in products:
        product["collections"] = [
            col["title"]
            for col in collections
            if product["id"].split("/")[-1] in [
                str(pid) for pid in col.get("product_ids", [])
            ]
        ]

    return {
        "products":    products,
        "collections": collections,
    }


def _fetch_public_collections(domain: str) -> list:
    """
    Tries to fetch collections from public store.
    Returns empty list if not available — non-critical.
    """
    try:
        url      = f"https://{domain}/collections.json?limit=20"
        response = httpx.get(url, timeout=10, follow_redirects=True)
        if response.status_code == 200:
            cols = response.json().get("collections", [])
            return [
                {
                    "id":          str(c.get("id", "")),
                    "title":       c.get("title", ""),
                    "description": c.get("body_html", ""),
                    "product_ids": [],  # not in public endpoint
                }
                for c in cols
            ]
    except Exception:
        pass
    return []


# ─────────────────────────────────────────────
# Run competitor comparison
# Analyzes your store + 1-2 competitors
# Returns side-by-side gap report
# ─────────────────────────────────────────────
def run_competitor_comparison(
    your_passport:       dict,
    your_domain:         str,
    competitor_urls:     list[str],
    monthly_revenue:     float | None = None,
) -> dict:
    """
    Takes your already-computed passport and
    compares it against competitor stores.

    Args:
        your_passport:   output of analyze_store() for your store
        your_domain:     your store domain
        competitor_urls: list of competitor store URLs (max 2)
        monthly_revenue: optional for revenue comparison

    Returns comparison report with gaps.
    """
    from normalizer   import normalize_store_data
    from orchestrator import analyze_store

    all_stores = []

    # Your store — already analyzed
    your_avg_scores = _avg_scores(your_passport["products"])
    all_stores.append({
        "store":       your_domain,
        "is_yours":    True,
        "store_score": your_passport["store_score"],
        "scores":      your_avg_scores,
        "invisible_pct": your_passport["store_summary"].get("invisible_pct", 0),
        "top_missing": your_passport["store_summary"].get("top_missing_fields", []),
    })

    # Competitors
    for url in competitor_urls[:2]:
        domain = url.strip().rstrip("/").replace("https://", "").replace("http://", "").split("/")[0]
        print(f"\n[competitor] Analyzing: {domain}")

        try:
            raw_data   = fetch_competitor_products(domain, limit=3)
            store_data = normalize_store_data(raw_data)

            if not store_data["products"]:
                raise ValueError("No products found")
            
            time.sleep(8)  # be nice to their servers

            passport   = analyze_store(store_data)
            avg_scores = _avg_scores(passport["products"])

            all_stores.append({
                "store":         domain,
                "is_yours":      False,
                "store_score":   passport["store_score"],
                "scores":        avg_scores,
                "invisible_pct": passport["store_summary"].get("invisible_pct", 0),
                "top_missing":   passport["store_summary"].get("top_missing_fields", []),
            })
            print(f"  [competitor] {domain} → {passport['store_score']}/100")

        except Exception as e:
            print(f"  [competitor] Failed to analyze {domain}: {e}")
            all_stores.append({
                "store":    domain,
                "is_yours": False,
                "error":    str(e),
            })

    # Build gap analysis
    your_store  = all_stores[0]
    gaps        = []
    wins        = []

    agent_labels = {
        "visibility":    "AI product visibility",
        "hallucination": "Claim accuracy",
        "context":       "Shopper query matching",
        "trust":         "Trust signals",
        "staleness":     "Data freshness",
    }

    for comp in all_stores[1:]:
        if "error" in comp:
            continue

        for agent in ["visibility", "hallucination", "context", "trust", "staleness"]:
            your_score = your_store["scores"].get(agent, 0)
            comp_score = comp["scores"].get(agent, 0)
            diff       = comp_score - your_score

            if diff > 10:
                gaps.append({
                    "agent":       agent,
                    "label":       agent_labels.get(agent, agent),
                    "your_score":  your_score,
                    "their_score": comp_score,
                    "gap":         diff,
                    "competitor":  comp["store"],
                    "message":     f"You're losing on {agent_labels.get(agent, agent)}: {your_score} vs {comp_score}",
                    "urgency":     "critical" if diff > 30 else "high" if diff > 20 else "medium",
                })
            elif diff < -10:
                wins.append({
                    "agent":       agent,
                    "label":       agent_labels.get(agent, agent),
                    "your_score":  your_score,
                    "their_score": comp_score,
                    "advantage":   abs(diff),
                    "competitor":  comp["store"],
                    "message":     f"You're ahead on {agent_labels.get(agent, agent)}: {your_score} vs {comp_score}",
                })

    gaps.sort(key=lambda x: x["gap"], reverse=True)
    wins.sort(key=lambda x: x["advantage"], reverse=True)

    return {
        "stores":          all_stores,
        "gaps":            gaps,
        "wins":            wins,
        "you_are_winning": len(gaps) == 0,
        "biggest_gap":     gaps[0] if gaps else None,
        "biggest_win":     wins[0] if wins else None,
        "summary":         _build_summary(your_store, all_stores, gaps, wins),
    }


def _avg_scores(products: list) -> dict:
    """Average agent scores across all products."""
    if not products:
        return {}
    agents   = ["visibility", "hallucination", "context", "trust", "staleness"]
    averages = {}
    for agent in agents:
        scores = [p["scores"].get(agent, 0) for p in products if "scores" in p]
        averages[agent] = round(sum(scores) / len(scores)) if scores else 0
    return averages


def _build_summary(your_store: dict, all_stores: list, gaps: list, wins: list) -> str:
    """Builds a plain-language summary of the comparison."""
    competitors = [s for s in all_stores if not s.get("is_yours") and "error" not in s]
    if not competitors:
        return "No competitor data available."

    comp_names  = ", ".join(c["store"] for c in competitors)
    your_score  = your_store["store_score"]
    comp_scores = [c["store_score"] for c in competitors]
    avg_comp    = round(sum(comp_scores) / len(comp_scores))

    if your_score > avg_comp:
        diff = your_score - avg_comp
        return f"Your store ({your_score}/100) outperforms {comp_names} (avg {avg_comp}/100) by {diff} points overall."
    else:
        diff = avg_comp - your_score
        return f"Your store ({your_score}/100) trails {comp_names} (avg {avg_comp}/100) by {diff} points. Focus on: {', '.join(g['agent'] for g in gaps[:2])}."


# ─────────────────────────────────────────────
# Quick test:
#   python competitor.py
#
# Tests public scraping on a real Shopify store
# ─────────────────────────────────────────────
if __name__ == "__main__":
    from normalizer   import normalize_store_data
    from orchestrator import analyze_store
    from scraper      import fetch_store_data

    # Your store passport first
    print("Fetching your store...")
    your_domain   = os.getenv("SHOPIFY_STORE")
    raw           = fetch_store_data(limit=3)
    store_data    = normalize_store_data(raw)
    your_passport = analyze_store(store_data, monthly_revenue=10000)

    print(f"Your store score: {your_passport['store_score']}/100")

    # Compare against a public Shopify store
    # Replace with any real Shopify store URL
    competitor_url = "https://www.allbirds.com"

    print(f"\nComparing against: {competitor_url}")
    result = run_competitor_comparison(
        your_passport    = your_passport,
        your_domain      = your_domain,
        competitor_urls  = [competitor_url],
        monthly_revenue  = 10000,
    )

    print(f"\n{'='*55}")
    print(f"COMPARISON SUMMARY")
    print(f"{'='*55}")
    print(f"Summary: {result['summary']}")

    print(f"\nSTORE SCORES:")
    for store in result["stores"]:
        if "error" in store:
            print(f"  {store['store']}: ERROR - {store['error']}")
            continue
        tag = " ← YOU" if store["is_yours"] else ""
        print(f"  {store['store']}: {store['store_score']}/100{tag}")

    if result["gaps"]:
        print(f"\nGAPS (where you're losing):")
        for g in result["gaps"]:
            print(f"  ✗ {g['label']}: {g['your_score']} vs {g['their_score']} [{g['urgency'].upper()}]")

    if result["wins"]:
        print(f"\nWINS (where you're ahead):")
        for w in result["wins"]:
            print(f"  ✓ {w['label']}: {w['your_score']} vs {w['their_score']}")