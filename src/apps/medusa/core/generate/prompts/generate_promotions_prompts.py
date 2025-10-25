PROMOTIONS_PROMPT = """Generate {count} realistic promotional campaigns for a US CLOTHING E-COMMERCE BRAND.

TYPE: {promo_type_name}
Description: {promo_type_description}

CRITICAL: Generate ONLY creative/constant fields. NO actual Medusa IDs or mappings.

REQUIRED FIELDS (Creative Content Only):
1. code: Unique promotion code (avoid: {excluded_codes})
2. type: "{promo_type_type}"
3. is_automatic: {is_automatic}
4. campaign: {campaign_requirement}
   - name: Campaign name for clothing brand
   - description: What the campaign is about
   - campaign_identifier: Uppercase identifier (e.g., SUMMER_SALE_2025)
   - starts_at: null (always)
   - ends_at: null (always)
   - budget:
     * limit: Budget in DOLLARS (e.g., 50000 = $50,000)
     * type: "usage" (always)
5. promotion_config:
   - target_type: "{target_type}"
   - allocation: "{allocation}"
   - value_type: "{value_type}"
   - value: Discount value (percentage: 5-75, fixed: 5-100 dollars)
   - needs_currency: {needs_currency}
   - max_quantity: {max_quantity_requirement}
   {buyget_fields}

REALISTIC PRICING (DOLLARS):
- Fixed discounts: $5-$100 (e.g., 10, 25, 50)
- Percentage: 5-75 (e.g., 10, 15, 20, 25, 30, 50)
- BOGO: 50 or 100 (percentage)
- Campaign budgets: $10,000-$500,000 (e.g., 50000, 100000, 250000)

EXAMPLE PROMOTION CODES FOR CLOTHING:
- SUMMER25, FALL20, WINTER30, SPRING15
- NEWMEMBER, VIP50, LOYAL20
- FLASH50, WEEKEND25, CLEARANCE40
- FREESHIP, SHOPMORE, SAVE20

JSON STRUCTURE:
[
  {{
    "code": "SUMMER25",
    "type": "standard",
    "is_automatic": false,
    "campaign": {{
      "name": "Summer Sale 2025",
      "description": "Special summer discount on clothing",
      "campaign_identifier": "SUMMER_SALE_2025",
      "starts_at": null,
      "ends_at": null,
      "budget": {{
        "limit": 75000,
        "type": "usage"
      }}
    }},
    "promotion_config": {{
      "target_type": "items",
      "allocation": "each",
      "value_type": "percentage",
      "value": 25,
      "needs_currency": false,
      "max_quantity": 5
    }}
  }}
]

CRITICAL RULES:
- Return ONLY valid JSON array
- NO Medusa IDs or mappings
- campaign is null if needs_campaign is false
- All monetary values in DOLLARS
- Unique codes

Generate {count} promotions for type "{promo_type_name}" now:"""
