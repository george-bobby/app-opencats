SYSTEM_PROMPT = """You are an expert in fashion e-commerce and product curation, specializing in creating compelling marketing collections.
Your task is to generate realistic, trendy product collections for a clothing and fashion e-commerce platform.
Focus on creating diverse collections that appeal to different customer segments, occasions, and style preferences."""

USER_PROMPT = """Generate {batch_size} realistic product collections for a CLOTHING & FASHION e-commerce platform. 
Collections are used to group related products together for marketing campaigns, seasonal launches, and style curation.

IMPORTANT REQUIREMENTS:
- Titles should be compelling, stylish, and marketing-focused
- Handle is MANDATORY - must be provided for every collection
- Focus ONLY on clothing, footwear, and fashion accessories
- Ensure MAXIMUM VARIETY across men, women, kids, seasonal, occasion-based, and trending fashion collections
{existing_context}
Collection Types to Include:
- Seasonal: "Summer Essentials", "Winter Wardrobe", "Spring Refresh", "Festive Collection", "Autumn Layers"
- Lifestyle & Occasion: "Workwear Staples", "Evening Elegance", "Casual Weekend", "Wedding Ready", "Date Night", "Brunch Outfits"
- Trending: "New Arrivals", "Best Sellers", "Editor's Picks", "Street Style", "Viral Finds", "Trending Now"
- Category-based: "Denim Edit", "Party Dresses", "Athleisure"
- Price-based: "Premium Styles", "Luxury Collection", "Budget Finds", "Sale Picks"
- Demographic-based: "Menswear Edit", "Womenswear Essentials", "Kids Favourites", "Teen Trends", "Plus Size", "Petite Collection"
- Theme-based: "Sustainable Fashion", "Monochrome Looks", "Festival Fits", "Back to School", "Vintage Vibes", "Minimalist Capsule"
- Style-based: "Boho Chic", "Classic Elegance", "Urban Edge", "Preppy Style", "Sporty Luxe"{variety_instruction}

Requirements:
- Title should be catchy and fashion-marketing friendly (2–4 words)
- Handle is MANDATORY - must be unique URL-friendly slug (lowercase, hyphens, no spaces)
- Each collection should clearly target a fashion-related segment, theme, or season

Return ONLY a JSON array with this exact structure (handle is MANDATORY for all items):
[
  {{
    "title": "Summer Essentials",
    "handle": "summer-essentials"
  }},
  {{
    "title": "Evening Elegance",
    "handle": "evening-elegance"
  }},
  {{
    "title": "New Arrivals",
    "handle": "new-arrivals"
  }}
]

Generate exactly {batch_size} unique clothing/fashion collections with maximum variety and strong marketing appeal:"""

EXISTING_CONTEXT_TEMPLATE = """
PREVIOUSLY GENERATED COLLECTIONS (DO NOT DUPLICATE OR CREATE SIMILAR VARIATIONS):
{collections_context}

Total collections already generated: {total_count}

CRITICAL: Analyze the above collections carefully and ensure your new collections:
1. Do NOT repeat any existing titles or handles
2. Do NOT create close variations (e.g., if "Summer Essentials" exists, don't create "Summer Basics" or "Essential Summer")
3. Focus on UNEXPLORED themes, seasons, occasions, or categories
4. Prioritize diversity across different fashion segments
"""

VARIETY_INSTRUCTION_TEMPLATE = """

ATTEMPT #{attempt}: Previous attempt had issues. Be even more creative and explore different themes, occasions, and segments!"""
