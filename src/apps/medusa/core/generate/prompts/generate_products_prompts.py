SYSTEM_PROMPT = """You are an expert in e-commerce product catalog creation, specializing in fashion and apparel.
Your task is to generate realistic, complete product listings with variants, pricing, shipping attributes, and all necessary metadata.
CRITICAL: Every single variant MUST include material, hs_code, origin_country, length, width, height, weight, and mid_code fields.

IMPORTANT: You MUST respond with ONLY a valid JSON array. Do not include any text, explanations, or markdown before or after the JSON. Your entire response should be parseable as JSON."""

USER_PROMPT = """Generate {batch_size} unique clothing products as a JSON array.

TARGET:
- Category: {category_name}
- Collection: {collection_title}

AVAILABLE TYPES (choose one per product): {types_list}
AVAILABLE TAGS (select 2-4 per product): {tags_list}

{existing_context}

=== CRITICAL REQUIREMENTS ===
1. Each product MUST have 2-3 variants ONLY (no more than 3)
2. Use simple variant structures: 2-3 sizes (S, M, L) OR 2-3 colors
3. Every variant MUST include: material, hs_code, origin_country, length, width, height, weight, mid_code
4. 3. The 'type' field MUST be appropriate for the category '{category_name}'
   - For outerwear categories: use Jacket, Coat, Blazer types
   - For tops categories: use T-Shirt, Blouse, Tank types
   - For kurtis categories: use Kurti-related types only
5. Return ONLY valid JSON array - no text before or after
=== END CRITICAL SECTION ===

PRODUCT STRUCTURE:
{{
  "title": "Product Name",
  "handle": "product-slug",
  "subtitle": "Short description",
  "description": "100-120 word detailed description",
  "status": "published",
  "is_giftcard": false,
  "discountable": true,
  "category": "{category_name}",
  "collection": "{collection_title}",
  "type": "Product Type from list",
  "tags": ["tag1", "tag2"],
  "sales_channels": ["Official Website"],
  "shipping_profile": "Standard Shipping",
  "options": [{{"title": "Size", "values": ["S", "M", "L"]}}],
  "variants": [
    {{
      "title": "S",
      "options": {{"Size": "S"}},
      "sku": "ABC-1234-S",
      "manage_inventory": true,
      "allow_backorder": false,
      "prices": [{{"currency_code": "usd", "amount": 29.99}}],
      "material": "cotton",
      "hs_code": "610910",
      "origin_country": "us",
      "length": 30,
      "width": 24,
      "height": 3,
      "weight": 220,
      "mid_code": "MID123456"
    }},
    {{
      "title": "M",
      "options": {{"Size": "M"}},
      "sku": "ABC-1234-M",
      "manage_inventory": true,
      "allow_backorder": false,
      "prices": [{{"currency_code": "usd", "amount": 29.99}}],
      "material": "cotton",
      "hs_code": "610910",
      "origin_country": "us",
      "length": 32,
      "width": 26,
      "height": 4,
      "weight": 250,
      "mid_code": "MID123457"
    }},
    {{
      "title": "L",
      "options": {{"Size": "L"}},
      "sku": "ABC-1234-L",
      "manage_inventory": true,
      "allow_backorder": false,
      "prices": [{{"currency_code": "usd", "amount": 29.99}}],
      "material": "cotton",
      "hs_code": "610910",
      "origin_country": "us",
      "length": 34,
      "width": 28,
      "height": 4,
      "weight": 280,
      "mid_code": "MID123458"
    }}
  ]
}}

VARIANT ATTRIBUTES QUICK GUIDE:

**MATERIALS:** cotton, polyester, wool, denim, linen, silk, cashmere, nylon

**HS CODES:**
- 610910 → T-shirts, tanks, casual tops
- 620520 → Shirts, button-ups, blouses
- 620342 → Pants, jeans, trousers
- 611020 → Sweaters, pullovers, cardigans
- 620193 → Jackets, coats

**DIMENSIONS BY TYPE:**
- Shirts/Tops: length 28-38cm, width 22-32cm, height 3-6cm, weight 200-450g
- Sweaters: length 30-40cm, width 26-36cm, height 5-8cm, weight 350-600g
- Dresses: length 35-50cm, width 25-40cm, height 4-8cm, weight 300-700g
- Pants: length 35-45cm, width 28-40cm, height 5-9cm, weight 450-800g
- Jackets/Coats: length 38-55cm, width 32-50cm, height 6-12cm, weight 600-1400g

**SIZE SCALING:** S (lower range) → M (mid range) → L (upper range)

**OTHER FIELDS:**
- origin_country: Always "us"
- mid_code: Format "MID" + 6 random digits (e.g., MID847392)

**PRICING (USD):**
Tees $12-18 | Tops $18-32 | Dresses $28-85 | Pants $32-58 | Sweaters $32-62 | Jackets $48-150

EXAMPLE WITH 3 VARIANTS:
[
  {{
    "title": "Classic Cotton Crew Tee",
    "handle": "classic-cotton-crew-tee",
    "subtitle": "Everyday essential comfort",
    "description": "Made from 100% premium cotton, this crew neck tee offers unmatched softness and breathability. Features reinforced shoulder seams and a classic relaxed fit. Pre-shrunk
     fabric ensures lasting quality. Perfect for everyday wear or layering. Machine washable and designed to maintain its shape and color",
    "status": "published",
    "is_giftcard": false,
    "discountable": true,
    "category": "{category_name}",
    "collection": "{collection_title}",
    "type": "T-Shirt",
    "tags": ["casual", "cotton"],
    "sales_channels": ["Official Website"],
    "shipping_profile": "Standard Shipping",
    "options": [{{"title": "Size", "values": ["S", "M", "L"]}}],
    "variants": [
      {{
        "title": "S",
        "options": {{"Size": "S"}},
        "sku": "TEE-5001-S",
        "manage_inventory": true,
        "allow_backorder": false,
        "prices": [{{"currency_code": "usd", "amount": 15.99}}],
        "material": "cotton",
        "hs_code": "610910",
        "origin_country": "us",
        "length": 30,
        "width": 24,
        "height": 3,
        "weight": 220,
        "mid_code": "MID500101"
      }},
      {{
        "title": "M",
        "options": {{"Size": "M"}},
        "sku": "TEE-5001-M",
        "manage_inventory": true,
        "allow_backorder": false,
        "prices": [{{"currency_code": "usd", "amount": 15.99}}],
        "material": "cotton",
        "hs_code": "610910",
        "origin_country": "us",
        "length": 32,
        "width": 26,
        "height": 4,
        "weight": 250,
        "mid_code": "MID500102"
      }},
      {{
        "title": "L",
        "options": {{"Size": "L"}},
        "sku": "TEE-5001-L",
        "manage_inventory": true,
        "allow_backorder": false,
        "prices": [{{"currency_code": "usd", "amount": 15.99}}],
        "material": "cotton",
        "hs_code": "610910",
        "origin_country": "us",
        "length": 34,
        "width": 28,
        "height": 4,
        "weight": 280,
        "mid_code": "MID500103"
      }}
    ]
  }}
]

EXAMPLE WITH 2 VARIANTS:
[
  {{
    "title": "Relaxed Denim Jacket",
    "handle": "relaxed-denim-jacket",
    "subtitle": "Classic versatile outerwear",
    "description": "A timeless denim jacket featuring premium cotton denim construction. Classic button-front closure, chest pockets, and adjustable cuffs. Relaxed fit works perfectly over
     tees or sweaters. Durable and stylish for any season.",
    "status": "published",
    "is_giftcard": false,
    "discountable": true,
    "category": "{category_name}",
    "collection": "{collection_title}",
    "type": "Jacket",
    "tags": ["denim", "casual"],
    "sales_channels": ["Official Website"],
    "shipping_profile": "Standard Shipping",
    "options": [{{"title": "Size", "values": ["M", "L"]}}],
    "variants": [
      {{
        "title": "M",
        "options": {{"Size": "M"}},
        "sku": "JKT-2001-M",
        "manage_inventory": true,
        "allow_backorder": false,
        "prices": [{{"currency_code": "usd", "amount": 68.00}}],
        "material": "denim",
        "hs_code": "620193",
        "origin_country": "us",
        "length": 42,
        "width": 38,
        "height": 8,
        "weight": 750,
        "mid_code": "MID200101"
      }},
      {{
        "title": "L",
        "options": {{"Size": "L"}},
        "sku": "JKT-2001-L",
        "manage_inventory": true,
        "allow_backorder": false,
        "prices": [{{"currency_code": "usd", "amount": 68.00}}],
        "material": "denim",
        "hs_code": "620193",
        "origin_country": "us",
        "length": 46,
        "width": 42,
        "height": 9,
        "weight": 850,
        "mid_code": "MID200102"
      }}
    ]
  }}
]

CRITICAL: Generate exactly {batch_size} products. Each product must have 2-3 variants (not more). Return ONLY valid JSON array."""

EXISTING_PRODUCTS_CONTEXT_TEMPLATE = """
=== AVOID THESE EXISTING PRODUCTS ===
{products_list}
Total: {total_count} products exist
=== GENERATE COMPLETELY NEW PRODUCTS ===
"""
