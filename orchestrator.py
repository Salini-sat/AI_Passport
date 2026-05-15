import sys
import json
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

sys.path.append(".")

from agents.visibility   import run_visibility_agent
from agents.hallucination import run_hallucination_agent
from agents.context      import run_context_agent
from agents.trust        import run_trust_agent
from agents.staleness    import run_staleness_agent

# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# Agent weights â€” based on severity from research
# Must add up to 1.0
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
WEIGHTS = {
    "visibility":    0.30,  # Critical â€” 40% of products invisible
    "hallucination": 0.30,  # Critical â€” causes wrong recommendations
    "context":       0.20,  # High     â€” affects conversion
    "trust":         0.15,  # High     â€” affects credibility
    "staleness":     0.05,  # Medium   â€” easier to fix
}

# Revenue at risk multiplier
# Source: research stats from hackathon brief
# 31% revenue lost due to poor AI representation
AI_REVENUE_IMPACT = 0.31


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# Run one agent safely â€” catches errors so one
# failing agent doesn't break the whole passport
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
def _run_agent_safe(agent_fn, product: dict, agent_name: str) -> dict:
    """Runs one agent, returns error dict if it fails."""
    try:
        return agent_fn(product)
    except Exception as e:
        print(f"  [orchestrator] âš  {agent_name} failed: {e}")
        return {
            "agent":    agent_name,
            "score":    50,       # neutral score on failure
            "severity": "medium",
            "error":    str(e),
        }


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# Run all 5 agents on one product in parallel
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
def _run_all_agents(product: dict) -> dict:
    """
    Runs all 5 agents concurrently using threads.
    Returns dict of {agent_name: result}.

    Parallel execution cuts analysis time from
    ~25s sequential to ~8s concurrent.
    """
    
    agents = {
        "visibility":    run_visibility_agent,
        "hallucination": run_hallucination_agent,
        "context":       run_context_agent,
        "trust":         run_trust_agent,
        "staleness":     run_staleness_agent,
    }

    results = {}

    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = {
            executor.submit(
                _run_agent_safe, fn, product, name
            ): name
            for name, fn in agents.items()
        }

        for future in as_completed(futures):
            name          = futures[future]
            results[name] = future.result()

    return results


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# Aggregate 5 agent scores into one passport
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
def _aggregate_scores(agent_results: dict) -> dict:
    """
    Computes weighted overall score and
    builds ranked action plan.
    """
    # Weighted score
    overall = sum(
        agent_results[agent]["score"] * weight
        for agent, weight in WEIGHTS.items()
        if agent in agent_results
    )
    overall_score = round(overall)

    # Per-agent score summary
    scores = {
        name: result.get("score", 50)
        for name, result in agent_results.items()
    }

    # Build action plan â€” sorted by score ascending
    # (lowest score = highest priority fix)
    action_plan = []
    priority    = 1

    agent_labels = {
        "visibility":    "Fix missing product fields",
        "hallucination": "Remove unverifiable claims",
        "context":       "Add use-case context and tags",
        "trust":         "Add trust signals and certifications",
        "staleness":     "Update stale product data",
    }

    severity_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}

    sorted_agents = sorted(
        agent_results.items(),
        key=lambda x: (
            severity_order.get(x[1].get("severity", "medium"), 2),
            x[1].get("score", 50)
        )
    )

    for agent_name, result in sorted_agents:
        if result.get("score", 100) < 80:
            # Collect all fixes from this agent
            fixes = result.get("fixes", {})

            action_plan.append({
                "priority":    priority,
                "agent":       agent_name,
                "label":       agent_labels.get(agent_name, agent_name),
                "severity":    result.get("severity", "medium"),
                "score":       result.get("score", 50),
                "summary":     result.get(
                    "impact_summary",
                    result.get("summary", "")
                ),
                "fixes":       fixes,
                "score_gain":  round((80 - result.get("score", 50)) * WEIGHTS[agent_name]),
            })
            priority += 1

    return {
        "overall_score": overall_score,
        "scores":        scores,
        "action_plan":   action_plan,
    }


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# Revenue at risk calculator
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
def _calculate_revenue_at_risk(
    overall_score: int,
    monthly_revenue: float | None = None
) -> dict:
    """
    Estimates revenue at risk from AI invisibility.
    If monthly_revenue provided, gives $ estimate.
    Otherwise gives % estimate only.
    """
    # How invisible is this store to AI?
    # Score 0 = fully invisible, 100 = fully visible
    invisibility_pct = (100 - overall_score) / 100

    # Compound: invisibility Ã— AI commerce impact rate
    at_risk_pct = round(invisibility_pct * AI_REVENUE_IMPACT * 100, 1)

    result = {
        "overall_score":    overall_score,
        "invisibility_pct": round(invisibility_pct * 100, 1),
        "at_risk_pct":      at_risk_pct,
        "ai_commerce_stat": "31% of revenue is impacted by AI recommendation quality",
    }

    if monthly_revenue:
        at_risk_amount = round(monthly_revenue * invisibility_pct * AI_REVENUE_IMPACT)
        result["monthly_revenue"]    = monthly_revenue
        result["at_risk_monthly"]    = at_risk_amount
        result["at_risk_annually"]   = at_risk_amount * 12
        result["formatted_monthly"]  = f"${at_risk_amount:,}"
        result["formatted_annually"] = f"${at_risk_amount * 12:,}"

    return result


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# Build store-level summary across all products
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
def _build_store_summary(product_passports: list) -> dict:
    """
    Aggregates per-product results into store-level insights.
    """
    if not product_passports:
        return {}

    scores = [p["overall_score"] for p in product_passports]
    store_score = round(sum(scores) / len(scores))

    # How many products are critically invisible?
    invisible_count = sum(
        1 for p in product_passports
        if p["agent_results"].get("visibility", {}).get("invisible_to_ai", False)
    )

    # Most common missing fields across all products
    all_missing = []
    for p in product_passports:
        vis = p["agent_results"].get("visibility", {})
        all_missing.extend(vis.get("missing_fields", []))

    from collections import Counter
    field_counts    = Counter(all_missing)
    top_missing     = [field for field, _ in field_counts.most_common(5)]

    # Context collapse count
    collapse_count = sum(
        1 for p in product_passports
        if p["agent_results"].get("context", {}).get("context_collapse_detected", False)
    )

    return {
        "store_score":          store_score,
        "products_analyzed":    len(product_passports),
        "invisible_products":   invisible_count,
        "invisible_pct":        round((invisible_count / len(product_passports)) * 100),
        "context_collapse_count": collapse_count,
        "top_missing_fields":   top_missing,
        "worst_product":        min(product_passports, key=lambda p: p["overall_score"])["title"],
        "best_product":         max(product_passports, key=lambda p: p["overall_score"])["title"],
    }


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# MAIN â€” analyze_store
# This is what main.py calls
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
def analyze_store(
    store_data:      dict,
    monthly_revenue: float | None = None
) -> dict:
    """
    Full passport analysis for an entire store.

    Args:
        store_data:      output of normalize_store_data()
        monthly_revenue: optional, for revenue at risk calc

    Returns complete passport:
    {
      "store_score":       int,
      "revenue_at_risk":   dict,
      "store_summary":     dict,
      "products":          [product_passport, ...],
    }
    """
    products         = store_data.get("products", [])
    product_passports = []

    print(f"\n[orchestrator] Analyzing {len(products)} products...")
    start = time.time()

    for i, product in enumerate(products, 1):
        
        print(f"\n[orchestrator] Product {i}/{len(products)}: {product['title']}")
        if i > 1:
            time.sleep(5)
        # Run all 5 agents in parallel
        agent_results = _run_all_agents(product)

        # Aggregate into product passport
        aggregated = _aggregate_scores(agent_results)

        product_passports.append({
            "id":            product["id"],
            "title":         product["title"],
            "store_url":     product.get("store_url"),
            "overall_score": aggregated["overall_score"],
            "scores":        aggregated["scores"],
            "action_plan":   aggregated["action_plan"],
            "agent_results": agent_results,
        })

        print(f"  â†’ Overall score: {aggregated['overall_score']}/100")

    elapsed = round(time.time() - start, 1)
    print(f"\n[orchestrator] Done in {elapsed}s")

    # Store-level summary
    store_summary = _build_store_summary(product_passports)
    store_score   = store_summary.get("store_score", 0)

    # Revenue at risk
    revenue_at_risk = _calculate_revenue_at_risk(store_score, monthly_revenue)

    return {
        "store_score":     store_score,
        "revenue_at_risk": revenue_at_risk,
        "store_summary":   store_summary,
        "products":        product_passports,
        "analysis_time_s": elapsed,
    }


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# Quick test:
#   python orchestrator.py
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
if __name__ == "__main__":
    from scraper    import fetch_store_data
    from normalizer import normalize_store_data

    raw        = fetch_store_data(limit=3)
    store_data = normalize_store_data(raw)

    # Pass optional monthly revenue for $ estimate
    passport = analyze_store(store_data, monthly_revenue=10000)

    print(f"\n{'='*55}")
    print(f"STORE PASSPORT SUMMARY")
    print(f"{'='*55}")
    print(f"Store score      : {passport['store_score']}/100")
    print(f"Products analyzed: {passport['store_summary']['products_analyzed']}")
    print(f"Invisible products: {passport['store_summary']['invisible_products']}")
    print(f"Revenue at risk  : {passport['revenue_at_risk'].get('formatted_monthly', 'N/A')}/month")
    print(f"Top missing fields: {passport['store_summary']['top_missing_fields']}")
    print(f"Analysis time    : {passport['analysis_time_s']}s")

    print(f"\nPER-PRODUCT SCORES:")
    for p in passport["products"]:
        print(f"  {p['title'][:40]:<40} {p['overall_score']:>3}/100")
        for agent, score in p["scores"].items():
            bar = "#" * (score // 10) + "-" * (10 - score // 10)
            print(f"    {agent:<14} {bar} {score}")

    print(f"\nTOP ACTION PLAN (product 1):")
    for action in passport["products"][0]["action_plan"][:3]:
        print(f"  #{action['priority']} [{action['severity'].upper()}] {action['label']}")
        print(f"     Score: {action['score']}/100 â†’ +{action['score_gain']} pts if fixed")