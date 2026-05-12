import os
import httpx
from dotenv import load_dotenv

load_dotenv()

SHOPIFY_STORE = os.getenv("SHOPIFY_STORE")   # your-store.myshopify.com
SHOPIFY_TOKEN = os.getenv("SHOPIFY_TOKEN")   # shpat_...
API_VERSION   = "2025-01"
GRAPHQL_URL   = f"https://{SHOPIFY_STORE}/admin/api/{API_VERSION}/graphql.json"

HEADERS = {
    "X-Shopify-Access-Token": SHOPIFY_TOKEN,
    "Content-Type": "application/json",
}

# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# QUERY 1 â€” Products (title, description, tags,
#           price, inventory, images, updatedAt)
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
PRODUCTS_QUERY = """
query GetProducts($first: Int!) {
  products(first: $first) {
    edges {
      node {
        id
        title
        descriptionHtml
        productType
        tags
        status
        updatedAt
        onlineStoreUrl

        seo {
          title
          description
        }

        images(first: 5) {
          edges {
            node {
              url
              altText
            }
          }
        }

        variants(first: 5) {
          edges {
            node {
              id
              title
              price
              compareAtPrice
              availableForSale
              inventoryQuantity
              sku
            }
          }
        }

        options {
          name
          values
        }
      }
    }
  }
}
"""

# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# QUERY 2 â€” Metafields for a single product
# (specs, certifications, materials, reviews)
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
METAFIELDS_QUERY = """
query GetProductMetafields($id: ID!) {
  product(id: $id) {
    metafields(first: 20) {
      edges {
        node {
          namespace
          key
          value
          type
        }
      }
    }
  }
}
"""

# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# QUERY 3 â€” Collections (categories + use cases)
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
COLLECTIONS_QUERY = """
query GetCollections($first: Int!) {
  collections(first: $first) {
    edges {
      node {
        id
        title
        description
        products(first: 20) {
          edges {
            node {
              id
            }
          }
        }
      }
    }
  }
}
"""


def _run_query(query: str, variables: dict = {}) -> dict:
    """
    Sends a GraphQL query to Shopify.
    Returns the 'data' key from the response.
    Raises on HTTP errors or GraphQL errors.
    """
    response = httpx.post(
        GRAPHQL_URL,
        headers=HEADERS,
        json={"query": query, "variables": variables},
        timeout=30,
    )
    response.raise_for_status()
    body = response.json()

    # GraphQL errors come back as 200 with an "errors" key
    if "errors" in body:
        raise ValueError(f"Shopify GraphQL error: {body['errors']}")

    return body["data"]


def fetch_products(limit: int = 5) -> list[dict]:
    """
    Fetch up to `limit` products from the store.
    Returns a flat list of raw product dicts.
    """
    data = _run_query(PRODUCTS_QUERY, {"first": limit})
    products = []

    for edge in data["products"]["edges"]:
        node = edge["node"]

        # Flatten images
        images = [
            {"url": img["node"]["url"], "alt": img["node"]["altText"]}
            for img in node["images"]["edges"]
        ]

        # Flatten variants
        variants = [
            {
                "id":                v["node"]["id"],
                "title":             v["node"]["title"],
                "price":             v["node"]["price"],
                "compare_at_price":  v["node"]["compareAtPrice"],
                "available":         v["node"]["availableForSale"],
                "inventory":         v["node"]["inventoryQuantity"],
                "sku":               v["node"]["sku"],
            }
            for v in node["variants"]["edges"]
        ]

        products.append({
            "id":           node["id"],
            "title":        node["title"],
            "description":  node["descriptionHtml"],
            "product_type": node["productType"],
            "tags":         node["tags"],
            "status":       node["status"],
            "updated_at":   node["updatedAt"],
            "store_url":    node["onlineStoreUrl"],
            "seo":          node["seo"],
            "images":       images,
            "variants":     variants,
            "options":      node["options"],
        })

    return products


def fetch_metafields(product_id: str) -> list[dict]:
    """
    Fetch all metafields for a single product by its GID.
    product_id format: "gid://shopify/Product/123456789"
    Returns a flat list of {namespace, key, value, type} dicts.
    """
    data = _run_query(METAFIELDS_QUERY, {"id": product_id})

    if not data["product"]:
        return []

    return [
        {
            "namespace": m["node"]["namespace"],
            "key":       m["node"]["key"],
            "value":     m["node"]["value"],
            "type":      m["node"]["type"],
        }
        for m in data["product"]["metafields"]["edges"]
    ]


def fetch_collections(limit: int = 20) -> list[dict]:
    """
    Fetch all collections and which product IDs belong to each.
    Returns a list of {id, title, description, product_ids} dicts.
    """
    data = _run_query(COLLECTIONS_QUERY, {"first": limit})

    collections = []
    for edge in data["collections"]["edges"]:
        node = edge["node"]
        product_ids = [
            p["node"]["id"] for p in node["products"]["edges"]
        ]
        collections.append({
            "id":          node["id"],
            "title":       node["title"],
            "description": node["description"],
            "product_ids": product_ids,
        })

    return collections


def fetch_store_data(limit: int = 5) -> dict:
    """
    Master function â€” fetches everything in one call.
    This is what scraper.py exposes to the rest of the backend.

    Returns:
    {
        "products": [...],       â† list of product dicts with metafields
        "collections": [...],    â† list of collection dicts
    }
    """
    print(f"[scraper] Fetching up to {limit} products from {SHOPIFY_STORE}...")
    products = fetch_products(limit)
    print(f"[scraper] Got {len(products)} products. Fetching metafields...")

    # Fetch metafields for each product and attach them
    for product in products:
        metafields = fetch_metafields(product["id"])
        product["metafields"] = metafields
        print(f"[scraper]   â†’ {product['title']}: {len(metafields)} metafields")

    print("[scraper] Fetching collections...")
    collections = fetch_collections()
    print(f"[scraper] Got {len(collections)} collections.")

    # Attach collection names to each product
    for product in products:
        product["collections"] = [
            col["title"]
            for col in collections
            if product["id"] in col["product_ids"]
        ]

    print("[scraper] Done.")
    return {
        "products":    products,
        "collections": collections,
    }


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# Quick test â€” run this file directly to check
# your credentials work before building agents:
#
#   python scraper.py
#
# You should see your products printed out.
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
if __name__ == "__main__":
    import json
    data = fetch_store_data(limit=3)
    print(json.dumps(data, indent=2, default=str))