import re
from datetime import datetime, timezone


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# HELPERS
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def _strip_html(html: str) -> str:
    """Remove HTML tags from description, collapse whitespace."""
    if not html:
        return ""
    text = re.sub(r"<[^>]+>", " ", html)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _safe_float(value) -> float | None:
    """Convert price string to float safely."""
    try:
        return float(value) if value else None
    except (ValueError, TypeError):
        return None


def _days_since(iso_timestamp: str) -> int | None:
    """Return how many days ago an ISO 8601 timestamp was."""
    if not iso_timestamp:
        return None
    try:
        updated = datetime.fromisoformat(iso_timestamp.replace("Z", "+00:00"))
        now = datetime.now(timezone.utc)
        return (now - updated).days
    except Exception:
        return None


def _extract_metafield_map(metafields: list[dict]) -> dict:
    """
    Turn list of {namespace, key, value} into a flat dict.
    Key format: "namespace.key"  e.g. "custom.material"
    Makes it easy for agents to check: mf.get("custom.material")
    """
    return {
        f"{m['namespace']}.{m['key']}": m["value"]
        for m in metafields
        if m.get("namespace") and m.get("key")
    }


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# MAIN NORMALIZER
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def normalize_product(raw: dict) -> dict:
    """
    Takes one raw product dict from scraper.py
    Returns a clean, flat dict ready for all 5 agents.

    Output shape:
    {
      # Core identity
      "id":               str,
      "title":            str,
      "description":      str,   â† HTML stripped
      "product_type":     str,
      "tags":             list[str],
      "status":           str,   â† "ACTIVE" | "DRAFT" | "ARCHIVED"
      "store_url":        str | None,

      # Pricing + inventory (from first variant)
      "price":            float | None,
      "compare_at_price": float | None,
      "available":        bool,
      "inventory":        int | None,
      "sku":              str | None,
      "has_variants":     bool,
      "variant_count":    int,

      # Images
      "image_count":      int,
      "images":           list[{url, alt}],
      "images_with_alt":  int,   â† how many have alt text (AI-readable)
      "images_missing_alt": int, â† how many are invisible to AI

      # SEO
      "seo_title":        str | None,
      "seo_description":  str | None,
      "has_seo":          bool,

      # Collections / categories
      "collections":      list[str],
      "has_collections":  bool,

      # Options (size, color, etc.)
      "options":          list[{name, values}],

      # Metafields â€” flat dict "namespace.key": "value"
      "metafields":       dict,

      # Staleness
      "updated_at":       str,
      "days_since_update": int | None,

      # Pre-computed AI readiness signals
      # (used by agents to avoid re-parsing)
      "signals": {
        "has_description":        bool,
        "description_length":     int,
        "has_tags":               bool,
        "tag_count":              int,
        "has_product_type":       bool,
        "has_collections":        bool,
        "has_price":              bool,
        "has_inventory":          bool,
        "has_sku":                bool,
        "has_images":             bool,
        "has_alt_text":           bool,
        "has_seo_title":          bool,
        "has_seo_description":    bool,
        "has_metafields":         bool,
        "metafield_count":        int,
        "is_active":              bool,
        "is_available":           bool,
        "is_stale":               bool,  â† True if >90 days old
      }
    }
    """
    metafields    = raw.get("metafields", [])
    metafield_map = _extract_metafield_map(metafields)
    variants      = raw.get("variants", [])
    images        = raw.get("images", [])
    seo           = raw.get("seo") or {}
    first_variant = variants[0] if variants else {}

    # Images with and without alt text
    images_with_alt    = [img for img in images if img.get("alt")]
    images_missing_alt = [img for img in images if not img.get("alt")]

    description      = _strip_html(raw.get("description", ""))
    price            = _safe_float(first_variant.get("price"))
    compare_at_price = _safe_float(first_variant.get("compare_at_price"))
    available        = first_variant.get("available", False)
    inventory        = first_variant.get("inventory")
    sku              = first_variant.get("sku") or ""
    seo_title        = seo.get("title") or ""
    seo_description  = seo.get("description") or ""
    tags             = raw.get("tags", [])
    collections      = raw.get("collections", [])
    days_old         = _days_since(raw.get("updated_at", ""))
    product_type     = raw.get("product_type") or ""
    status           = raw.get("status") or ""

    return {
        # Core identity
        "id":               raw.get("id", ""),
        "title":            raw.get("title", ""),
        "description":      description,
        "product_type":     product_type,
        "tags":             tags,
        "status":           status,
        "store_url":        raw.get("store_url"),

        # Pricing + inventory
        "price":            price,
        "compare_at_price": compare_at_price,
        "available":        available,
        "inventory":        inventory,
        "sku":              sku,
        "has_variants":     len(variants) > 1,
        "variant_count":    len(variants),

        # Images
        "image_count":          len(images),
        "images":               images,
        "images_with_alt":      len(images_with_alt),
        "images_missing_alt":   len(images_missing_alt),

        # SEO
        "seo_title":        seo_title,
        "seo_description":  seo_description,
        "has_seo":          bool(seo_title and seo_description),

        # Collections
        "collections":      collections,
        "has_collections":  len(collections) > 0,

        # Options
        "options":          raw.get("options", []),

        # Metafields
        "metafields":       metafield_map,

        # Staleness
        "updated_at":       raw.get("updated_at", ""),
        "days_since_update": days_old,

        # Pre-computed signals for agents
        "signals": {
            "has_description":      len(description) > 0,
            "description_length":   len(description),
            "has_tags":             len(tags) > 0,
            "tag_count":            len(tags),
            "has_product_type":     len(product_type) > 0,
            "has_collections":      len(collections) > 0,
            "has_price":            price is not None,
            "has_inventory":        inventory is not None,
            "has_sku":              len(sku) > 0,
            "has_images":           len(images) > 0,
            "has_alt_text":         len(images_with_alt) > 0,
            "has_seo_title":        len(seo_title) > 0,
            "has_seo_description":  len(seo_description) > 0,
            "has_metafields":       len(metafield_map) > 0,
            "metafield_count":      len(metafield_map),
            "is_active":            status == "ACTIVE",
            "is_available":         available,
            "is_stale":             (days_old or 0) > 90,
        },
    }


def normalize_store_data(raw_store_data: dict) -> dict:
    """
    Normalizes the full output of scraper.fetch_store_data().
    Returns:
    {
        "products":    [normalized_product, ...],
        "collections": [collection, ...],
    }
    """
    normalized_products = [
        normalize_product(p)
        for p in raw_store_data.get("products", [])
    ]

    return {
        "products":    normalized_products,
        "collections": raw_store_data.get("collections", []),
    }


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# Quick test â€” run directly:
#   python normalizer.py
#
# Prints the normalized version of your first 3 products.
# Check that signals look correct â€” these feed your agents.
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
if __name__ == "__main__":
    import json
    from scraper import fetch_store_data

    raw  = fetch_store_data(limit=3)
    data = normalize_store_data(raw)

    for p in data["products"]:
        print(f"\n{'='*50}")
        print(f"PRODUCT: {p['title']}")
        print(f"  Description length : {p['signals']['description_length']} chars")
        print(f"  Tags               : {p['tags']}")
        print(f"  Collections        : {p['collections']}")
        print(f"  Price              : {p['price']}")
        print(f"  Inventory          : {p['inventory']}")
        print(f"  Images             : {p['image_count']} ({p['images_with_alt']} with alt text)")
        print(f"  Has SEO            : {p['has_seo']}")
        print(f"  Metafields         : {p['signals']['metafield_count']}")
        print(f"  Days since update  : {p['days_since_update']}")
        print(f"  Is stale (>90d)    : {p['signals']['is_stale']}")
        print(f"\n  SIGNALS:")
        for k, v in p["signals"].items():
            flag = "âœ“" if v else "âœ—"
            print(f"    {flag}  {k}: {v}")