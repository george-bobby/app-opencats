SYSTEM_PROMPT = """You are an expert in e-commerce product categorization and taxonomy.
Your task is to generate realistic, diverse product type names for fashion and apparel categories.

IMPORTANT: You MUST respond with ONLY a valid JSON array. Do not include any text, explanations, or markdown before or after the JSON. Your entire response should be parseable as JSON."""

USER_PROMPT = """Generate {batch_size} unique product type names as a JSON array.

{existing_context}

{variety_instruction}

=== CRITICAL REQUIREMENTS ===
1. Generate diverse product types for fashion and apparel
2. Do NOT generate types related to school uniforms, work uniforms, or institutional clothing
3. Focus on casual, everyday fashion and apparel only
4. Return ONLY valid JSON array - no text before or after
=== END CRITICAL SECTION ===

TYPE STRUCTURE:
{{
  "value": "Type Name"
}}

EXAMPLES:
[
  {{"value": "T-Shirt"}},
  {{"value": "Dress"}},
  {{"value": "Jeans"}},
  {{"value": "Sweater"}},
  {{"value": "Jacket"}},
  {{"value": "Blouse"}},
  {{"value": "Cardigan"}},
  {{"value": "Hoodie"}},
  {{"value": "Polo Shirt"}},
  {{"value": "Tank Top"}}
]

CATEGORIES TO INCLUDE:
- Tops (T-shirts, blouses, shirts, tanks, polos, etc.)
- Bottoms (jeans, pants, shorts, skirts, leggings, etc.)
- Dresses (casual, formal, maxi, mini, midi, etc.)
- Outerwear (jackets, coats, blazers, vests, etc.)
- Sweaters & Knits (sweaters, cardigans, pullovers, hoodies, etc.)
- Activewear (joggers, track pants, sports tops, etc.)

EXCLUSIONS:
- School uniforms or uniform-related items
- Work uniforms or professional uniforms
- Institutional clothing
- Safety or protective wear

CRITICAL: Generate exactly {batch_size} unique product types. Return ONLY valid JSON array."""

EXISTING_CONTEXT_TEMPLATE = """
=== AVOID THESE EXISTING TYPES ===
{types_context}
Total: {total_count} types exist
=== GENERATE COMPLETELY NEW TYPES ===
"""

VARIETY_INSTRUCTION_TEMPLATE = """
=== VARIETY REQUIREMENT (Attempt {attempt}) ===
Previous attempts may have generated similar types.
Focus on MAXIMUM VARIETY and CREATIVITY in this batch.
Think of niche, specific, or unique clothing types.
=== END VARIETY REQUIREMENT ===
"""
