SYSTEM_PROMPT = """You are an expert in e-commerce product categorization, specializing in clothing and apparel.
Your task is to generate realistic, well-structured product categories for a fashion e-commerce platform.
Focus on creating diverse categories across men's, women's, and children's clothing."""

USER_PROMPT = """Generate {batch_size} realistic product categories for a CLOTHING e-commerce platform. 
Categories are used to organize apparel hierarchically for better navigation and search functionality.

IMPORTANT REQUIREMENTS:
- Focus ONLY on CLOTHING categories (no accessories, footwear, or jewelry).
- Cover MEN, WOMEN, and CHILDREN (including baby & kids) clothing categories.
- Names should be clear, professional, and commonly used in fashion e-commerce.
- Descriptions should be short and customer-friendly when included (1–2 sentences).
- Handle is optional but should be a clean, URL-friendly slug (lowercase, hyphens, no spaces).
- is_active should be true for 95% of categories (some inactive for seasonal/offline categories).
- is_internal should be false for 90% of categories (occasionally true for admin/system categories).
{existing_context}
Category Types to Include (CLOTHING ONLY):
- Men's Clothing: "Men's T-Shirts", "Men's Shirts", "Men's Jeans", "Men's Jackets", "Men's Sweaters", "Men's Hoodies", "Men's Ethnic Wear", "Men's Shorts", "Men's Trousers"
- Women's Clothing: "Women's Dresses", "Tops & Blouses", "Women's Jeans", "Skirts", "Sarees", "Kurtis & Tunics", "Women's Outerwear", "Leggings", "Palazzo Pants", "Women's Shorts"
- Kids & Baby Clothing: "Kids T-Shirts", "Kids Dresses", "Baby Rompers", "Kids Jackets", "Toddler Clothing",
- Seasonal Wear: "Winter Wear", "Summer Clothing", "Festive Wear", "Party Wear", "Resort Wear"
- Style-Specific: "Casual Wear", "Formal Wear", "Sports Wear", "Lounge Wear", "Night Wear"{variety_instruction}

Requirements:
- Name must be concise and realistic (1–4 words).
- Ensure MAXIMUM VARIETY across men's, women's, and children's clothing only.
- Do not generate unrelated categories (no shoes, bags, watches, or accessories).
- Return a JSON array with the exact structure below:

[
  {{
    "name": "Men's T-Shirts",
    "description": "Casual and everyday t-shirts for men in all fits and styles.",
    "handle": "mens-tshirts",
    "is_active": true,
    "is_internal": false
  }},
  {{
    "name": "Women's Dresses",
    "description": "Elegant, casual, and festive dresses for women.",
    "handle": "womens-dresses",
    "is_active": true,
    "is_internal": false
  }},
  {{
    "name": "Kids Jackets",
    "description": "Warm and comfortable jackets for children.",
    "handle": "kids-jackets",
    "is_active": true,
    "is_internal": false
  }}
]

Generate exactly {batch_size} unique clothing categories for MEN, WOMEN, and CHILDREN only, ensuring maximum variety and realistic e-commerce appeal:"""

EXISTING_CONTEXT_TEMPLATE = """
PREVIOUSLY GENERATED CATEGORIES (DO NOT DUPLICATE OR CREATE SIMILAR VARIATIONS):
{categories_context}

Total categories already generated: {total_count}

CRITICAL: Analyze the above categories carefully and ensure your new categories:
1. Do NOT repeat any existing names or handles
2. Do NOT create close variations (e.g., if "Men's T-Shirts" exists, don't create "Men's Tees" or "T-Shirts for Men")
3. Focus on UNEXPLORED clothing subcategories for men, women, and children
4. Prioritize diversity across different age groups, styles, and clothing types
"""

VARIETY_INSTRUCTION_TEMPLATE = """

ATTEMPT #{attempt}: Previous attempt had issues. Be even more creative and explore different subcategories and age groups!"""
