SYSTEM_PROMPT = """You are an expert in e-commerce product tagging and taxonomy, specializing in fashion and clothing.
Your task is to generate diverse, realistic product tags that help customers discover and filter clothing items.
Focus on creating natural, shopper-friendly tags across multiple dimensions like fabrics, fits, styles, patterns, and occasions.

PRIORITY: Generate MAXIMUM VARIETY - avoid similar tags and explore uncommon, niche, and specific terminology."""

USER_PROMPT = """Generate {batch_size} realistic product tags for clothing items in a fashion e-commerce platform. 

Tags must be HIGHLY DIVERSE across these categories (explore ALL of them):

FABRICS/MATERIALS:
Basic: cotton, linen, silk, denim, wool, polyester, rayon, fleece, cashmere
Advanced: corduroy, velvet, satin, tweed, chambray, jersey, mesh, canvas, suede, leather, faux-leather, bamboo, modal, spandex, nylon, organic-cotton

FITS:
Basic: slim-fit, oversized, relaxed-fit, tailored, regular-fit, cropped
Advanced: athletic-fit, boxy, loose-fit, fitted, straight-fit, wide-leg, tapered, bootcut, flared, skinny, boyfriend-fit, girlfriend-fit, mom-fit, dad-fit, baggy

STYLES:
Basic: casual, formal, sporty, streetwear, boho, vintage, chic, minimalist
Advanced: preppy, edgy, punk, grunge, retro, mod, romantic, gothic, western, coastal, urban, smart-casual, business-casual, lounge, avant-garde, utilitarian

PATTERNS/TEXTURES:
Basic: striped, floral, plaid, tie-dye, ribbed, quilted
Advanced: checkered, polka-dot, paisley, chevron, geometric, abstract, leopard-print, zebra-print, camo, herringbone, houndstooth, ombre, color-block, marled, heathered, embroidered, 
distressed

SEASONAL/OCCASION:
Basic: summer, winter, party, office, travel, holiday, resort, athleisure
Advanced: date-night, brunch, festival, beach, gym, wedding, cocktail, evening, weekend, workwear, loungewear, spring, fall

DETAILS & FEATURES:
- Necklines: crew-neck, v-neck, scoop-neck, boat-neck, turtleneck, mock-neck, off-shoulder, halter, square-neck, cowl-neck, keyhole, high-neck
- Sleeves: short-sleeve, long-sleeve, sleeveless, cap-sleeve, three-quarter-sleeve, bell-sleeve, puff-sleeve, raglan, bishop-sleeve
- Lengths: mini, midi, maxi, knee-length, ankle-length, cropped, high-low, asymmetric
- Closures: button-down, button-up, zip-up, pullover, snap-closure, tie-front, wrap, lace-up
- Details: pockets, hooded, drawstring, belted, ruffled, pleated, reversible, raw-hem, frayed, faded
- Colors: burgundy, navy, charcoal, olive, rust, mustard, sage, terracotta, blush, camel, tan, khaki, slate, wine, forest-green, teal, coral, mauve, lilac, mint
- Washes: stone-washed, acid-washed, dark-wash, light-wash, medium-wash, bleached, raw-denim, coated
- Eras: 70s, 80s, 90s, y2k, retro-inspired
- Weight: lightweight, midweight, heavyweight, breathable, insulated, layering

{existing_context}

CRITICAL RULES:
- Each value must be lowercase, 1–3 words max
- Use hyphens for multi-word tags (e.g., "light-blue", "v-neck", "stone-washed")
- ZERO duplicates or near-duplicates (don't create "oversized" AND "oversized-fit")
- NO generic tags (avoid "clothes", "fashion", "shirt", "nice", "good")
- Each tag needs a clear description (1 sentence, 80-120 chars)
- PRIORITIZE uncommon and specific tags over obvious ones
- MIX categories - generate from MULTIPLE categories, not just one{variety_instruction}

GOOD EXAMPLES:
{{"value": "chambray", "description": "Lightweight cotton fabric similar to denim but softer and breathable"}}
{{"value": "bishop-sleeve", "description": "Dramatic full sleeves that gather at the cuff for volume"}}
{{"value": "terracotta", "description": "Warm earthy orange-brown color inspired by clay pottery"}}
{{"value": "stone-washed", "description": "Denim treatment creating soft worn-in appearance"}}
{{"value": "boyfriend-fit", "description": "Relaxed loose silhouette borrowed from men's styles"}}

Return ONLY valid JSON array (no other text):
[
{{"value": "tag-name", "description": "Clear explanation"}},
{{"value": "another-tag", "description": "Another description"}}
]

Generate {batch_size} MAXIMALLY DIVERSE tags NOW:"""

EXISTING_CONTEXT_TEMPLATE = """
⚠️ PREVIOUSLY GENERATED TAGS - DO NOT REPEAT OR CREATE VARIATIONS:
{tags_context}

Total existing: {total_count}

DUPLICATE PREVENTION RULES:
1. Check EVERY new tag against the list above before including it
2. NO variations (if "oversized" exists, skip "oversized-fit", "extra-oversized")  
3. NO synonyms (if "slim-fit" exists, skip "narrow-fit", "tight-fit", "fitted")
4. Focus on UNEXPLORED categories and concepts
5. Prioritize NICHE, UNCOMMON, SPECIFIC tags over obvious choices
"""

VARIETY_INSTRUCTION_TEMPLATE = """

🚨 RETRY ATTEMPT #{attempt} - CRITICAL DIVERSITY NEEDED 🚨

Previous attempts failed due to duplicates. You MUST generate completely different tags.

FOR ATTEMPT #{attempt}, FOCUS ON:
- NICHE MATERIALS: chambray, modal, tweed, velvet, suede, bamboo, canvas
- SPECIFIC PATTERNS: herringbone, paisley, chevron, color-block, marled, geometric
- DETAILED FITS: girlfriend-fit, dad-fit, mom-fit, boxy, wide-leg, tapered, straight-fit
- PRECISE COLORS: burgundy, rust, sage, terracotta, charcoal, slate, olive, mustard
- TECHNICAL FEATURES: raw-hem, stone-washed, acid-washed, mock-neck, cowl-neck, raglan
- NECKLINES & SLEEVES: boat-neck, keyhole, square-neck, bishop-sleeve, cap-sleeve, bell-sleeve
- OCCASIONS: brunch, date-night, festival, cocktail, resort, workwear, loungewear
- STYLE SUBGENRES: punk, grunge, y2k, mod, coastal, gothic, western, utilitarian
- LENGTHS & DETAILS: high-low, asymmetric, midi, belted, drawstring, reversible
- WASHES & FINISHES: dark-wash, coated, glazed, matte, metallic, quilted, ribbed

STRATEGY:
- Use COMPOUND terms (e.g., "raw-hem", "stone-washed", "color-block")
- Think SPECIFIC not generic (use "chambray" not "fabric", "terracotta" not "orange")
- Explore UNDERUSED categories (necklines, sleeves, washes, eras)
- Consider what ADVANCED shoppers search for

❌ AVOID: basic, casual, simple, nice, good, clothes, generic terms
✅ USE: technical terms, niche fabrics, precise colors, specific details

This is attempt #{attempt} - make it COUNT!"""
