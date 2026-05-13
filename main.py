import sys
import os
import json
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from openai import OpenAI
from dotenv import load_dotenv
from competitor import run_competitor_comparison


sys.path.append(".")
load_dotenv()

from scraper      import fetch_store_data
from normalizer   import normalize_store_data
from orchestrator import analyze_store

app = FastAPI(title="AI Product Passport Engine", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

groq_client = OpenAI(
    api_key=os.getenv("GROQ_API_KEY"),
    base_url="https://api.groq.com/openai/v1",
)


class AnalyzeRequest(BaseModel):
    store_url:       str
    shopify_token:   str
    monthly_revenue: float | None = None
    product_limit:   int          = 5

class PerceiveRequest(BaseModel):
    store_url:     str
    shopify_token: str
    query:         str
    apply_fixes:   bool = False

class CompareRequest(BaseModel):
    store_url:       str
    shopify_token:   str
    competitor_urls: list[str]
    monthly_revenue: float | None = None


def _extract_domain(url: str) -> str:
    url = url.strip().rstrip("/")
    url = url.replace("https://", "").replace("http://", "")
    return url.split("/")[0]


def _build_raw_context(products: list) -> str:
    lines = []
    for p in products:
        lines.append(f"Product: {p['title']}")
        lines.append(f"  Description: {p['description'][:200] if p['description'] else 'NO DESCRIPTION'}")
        lines.append(f"  Type: {p['product_type'] or 'NOT SET'}")
        lines.append(f"  Tags: {', '.join(p['tags']) if p['tags'] else 'NO TAGS'}")
        lines.append(f"  Collections: {', '.join(p['collections']) if p['collections'] else 'NO COLLECTIONS'}")
        lines.append(f"  Price: ${p['price'] or 'unknown'}")
        lines.append(f"  In stock: {p['available']}")
        lines.append("")
    return "\n".join(lines)


def _build_fixed_context(products: list, passport: dict) -> str:
    fix_map = {p["id"]: p for p in passport["products"]}
    lines   = []
    for product in products:
        passport_product = fix_map.get(product["id"], {})
        agent_results    = passport_product.get("agent_results", {})
        vis_fixes        = agent_results.get("visibility", {}).get("fixes", {})
        ctx_fixes        = agent_results.get("context", {}).get("fixes", {})
        description = (vis_fixes.get("fixed_description") or vis_fixes.get("description") or product["description"] or "NO DESCRIPTION")
        tags        = (ctx_fixes.get("use_case_tags") or vis_fixes.get("tags") or product["tags"] or [])
        product_type = (vis_fixes.get("product_type") or product["product_type"] or "NOT SET")
        lines.append(f"Product: {product['title']}")
        lines.append(f"  Description: {str(description)[:300]}")
        lines.append(f"  Type: {product_type}")
        lines.append(f"  Tags: {', '.join(tags) if isinstance(tags, list) else tags}")
        lines.append(f"  Collections: {', '.join(product['collections']) if product['collections'] else 'NONE'}")
        lines.append(f"  Price: ${product['price'] or 'unknown'}")
        lines.append(f"  In stock: {product['available']}")
        lines.append("")
    return "\n".join(lines)


def _avg_agent_scores(products: list) -> dict:
    if not products:
        return {}
    agent_names = ["visibility", "hallucination", "context", "trust", "staleness"]
    averages    = {}
    for agent in agent_names:
        scores = [p["scores"].get(agent, 0) for p in products if "scores" in p]
        averages[agent] = round(sum(scores) / len(scores)) if scores else 0
    return averages


@app.get("/")
def root():
    return {"status": "running", "service": "AI Product Passport Engine", "routes": ["/analyze", "/perceive", "/compare"]}

@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/analyze")
async def analyze(req: AnalyzeRequest):
    try:
        os.environ["SHOPIFY_STORE"] = _extract_domain(req.store_url)
        os.environ["SHOPIFY_TOKEN"] = req.shopify_token
        print(f"[/analyze] Fetching store: {req.store_url}")
        raw        = fetch_store_data(limit=req.product_limit)
        store_data = normalize_store_data(raw)
        if not store_data["products"]:
            raise HTTPException(status_code=404, detail="No products found. Check your store URL and API token.")
        passport = analyze_store(store_data, monthly_revenue=req.monthly_revenue)
        return {"success": True, "store": _extract_domain(req.store_url), **passport}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/perceive")
async def perceive(req: PerceiveRequest):
    try:
        os.environ["SHOPIFY_STORE"] = _extract_domain(req.store_url)
        os.environ["SHOPIFY_TOKEN"] = req.shopify_token
        raw        = fetch_store_data(limit=5)
        store_data = normalize_store_data(raw)
        products   = store_data["products"]
        if not products:
            raise HTTPException(status_code=404, detail="No products found.")
        if req.apply_fixes:
            passport        = analyze_store(store_data)
            product_context = _build_fixed_context(products, passport)
            context_label   = "PASSPORT-OPTIMIZED"
        else:
            product_context = _build_raw_context(products)
            context_label   = "RAW STORE DATA"
        prompt = f"""You are an AI shopping assistant helping a customer find products.

AVAILABLE PRODUCTS FROM THIS STORE ({context_label}):
{product_context}

SHOPPER QUERY: "{req.query}"

Based ONLY on the product information provided above, recommend the best product(s) for this query.
If you cannot confidently recommend a product due to missing information, say so clearly.

Return ONLY valid JSON, no extra text:
{{
  "recommended_products": [
    {{
      "title": "product name",
      "reason": "why you recommend this for the query",
      "confidence": 0-100
    }}
  ],
  "products_skipped": [
    {{
      "title": "product name",
      "reason": "why you could NOT recommend this"
    }}
  ],
  "overall_response": "natural language response as if talking to the shopper",
  "can_answer_query": true or false,
  "missing_data_summary": "what data would have helped answer this query better"
}}"""
        response = groq_client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
            max_tokens=800,
        )
        raw_resp = response.choices[0].message.content.strip()
        raw_resp = raw_resp.replace("```json", "").replace("```", "").strip()
        result   = json.loads(raw_resp)
        return {"success": True, "query": req.query, "context_used": context_label, "apply_fixes": req.apply_fixes, "products_count": len(products), **result}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# Replace the entire /compare route with this simpler version:
@app.post("/compare")
async def compare(req: CompareRequest):
    try:
        os.environ["SHOPIFY_STORE"] = _extract_domain(req.store_url)
        os.environ["SHOPIFY_TOKEN"] = req.shopify_token

        # Analyze your store first
        raw        = fetch_store_data(limit=3)
        store_data = normalize_store_data(raw)
        passport   = analyze_store(store_data, monthly_revenue=req.monthly_revenue)

        # Run competitor comparison
        result = run_competitor_comparison(
            your_passport    = passport,
            your_domain      = _extract_domain(req.store_url),
            competitor_urls  = req.competitor_urls,
            monthly_revenue  = req.monthly_revenue,
        )

        return {"success": True, **result}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)