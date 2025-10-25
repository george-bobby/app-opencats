"""Prompt templates for AI-powered product-category mapping."""

SYSTEM_PROMPT = """You are an expert e-commerce product categorization system. Your task is to accurately match products to their correct categories based on product type and name.

CRITICAL RULES:
1. Primary factor: Product Type field (most important)
2. Secondary factor: Product Name (for additional context)
3. Each product type should map to its most specific matching category
4. Different product types must map to different categories
5. Use ONLY categories from the provided list
6. Be consistent with gender-specific categories (Men's vs Women's vs Kids)

Return ONLY valid JSON array with this structure:
[
    {{"product_id": "id", "category": "exact category name"}}
]"""


EXAMPLES_SECTION = """
MAPPING EXAMPLES - Learn these patterns:

MEN'S CLOTHING:
- "Men's Shirt" / "Flannel Shirt" / "Button-Down" → "Men's Shirts"
- "Polo Shirt" → "Men's Polo Shirts"
- "Men's Jeans" / "Denim Jeans" → "Men's Jeans"
- "Hoodie" / "Sweatshirt" / "Cropped Hoodie" → "Men's Hoodies"
- "Men's Sweater" / "Pullover" / "Turtleneck" / "Cowl Neck Sweater" → "Men's Sweaters"
- "Men's Trousers" / "Cargo Pants" / "Chino Pants" → "Men's Trousers"
- "Men's Shorts" / "Chino Shorts" / "Paper Bag Shorts" → "Men's Shorts"
- "Blazer" / "Oversized Blazer" → "Men's Blazers"
- "Joggers" / "Sweatpants" / "Track Pants" / "Vest" / "Utility Vest" → "Men's Activewear"

WOMEN'S CLOTHING:
- "Women's Jacket" / "Coat" / "Bomber" / "Parka" / "Trench" / "Denim Jacket" → "Women's Jackets"
- "Women's Top" / "Blouse" / "Tunic" / "Crop Top" / "Tank" / "Camisole" → "Women's Tops"
- "Skirt" / "Mini Skirt" / "Midi Skirt" / "Maxi Skirt" / "Pencil Skirt" / "Pleated Skirt" → "Women's Skirts"
- "Women's Cardigan" / "Longline Cardigan" / "Kimono Cardigan" / "Shrug" → "Women's Cardigans"
- "Leggings" → "Women's Leggings"
- "Palazzo" / "Culottes" / "Wide Leg Pants" / "Capri" → "Women's Palazzo Pants"
- "Jumpsuit" → "Women's Jumpsuits"
- "Kurti" / "Kurta" → "Women's Kurtis"
- "Saree" → "Women's Sarees"
- "Loungewear" → "Women's Loungewear"
- "Nightwear" / "Sleepwear" / "Pajama" → "Women's Nightwear"

KIDS & BABY CLOTHING:
- "Kids T-Shirt" → "Kids T-Shirts"
- "Kids Dress" / "Shift Dress" / "Maxi Dress" / "Wrap Dress" → "Kids Dresses"
- "Kids Shorts" → "Kids Shorts"
- "Toddler Dungarees" / "Dungaree" / "Overall" → "Toddler Dungarees"
- "Baby Romper" / "Romper" → "Baby Rompers"
- "Baby Onesie" / "Onesie" → "Baby Onesies"
- "Baby Bodysuit" / "Bodysuit" → "Baby Bodysuits"
- "Kids Sleepwear" → "Kids Sleepwear"

KEY MATCHING PRINCIPLES:
✓ "Parka Coat" contains "Jacket/Coat" → "Women's Jackets"
✓ "High-Waisted Jeans" contains "Jeans" → "Men's Jeans"
✓ "Pencil Skirt" contains "Skirt" → "Women's Skirts"
✓ "Cowl Neck Sweater" contains "Sweater" → "Men's Sweaters"
✓ "Baby Romper" contains "Baby" + "Romper" → "Baby Rompers"

WRONG EXAMPLES - Never do this:
❌ Mapping "Parka Coat" to "Baby Rompers" (completely unrelated)
❌ Mapping all different items to same category (lazy mapping)
❌ Ignoring the Product Type keywords
❌ Creating new categories not in the list"""


USER_PROMPT = """AVAILABLE CATEGORIES (use ONLY these exact names):
{categories_list}

PRODUCTS TO MAP:
{products_list}

INSTRUCTIONS:
1. Read each product's type carefully
2. Identify key keywords (shirt, jacket, skirt, jeans, etc.)
3. Match to the most specific category that contains those keywords
4. Ensure gender/age appropriateness (Men's/Women's/Kids/Baby)
5. Return the exact category name from the list above

Return ONLY the JSON array with mappings, no other text."""


FALLBACK_MAPPING_RULES = {
    # Men's categories
    "men's shirt": "Men's Shirts",
    "shirt": "Men's Shirts",
    "flannel": "Men's Shirts",
    "button": "Men's Shirts",
    "polo": "Men's Polo Shirts",
    "men's jean": "Men's Jeans",
    "jeans": "Men's Jeans",
    "denim": "Men's Jeans",
    "hoodie": "Men's Hoodies",
    "sweatshirt": "Men's Hoodies",
    "men's sweater": "Men's Sweaters",
    "sweater": "Men's Sweaters",
    "pullover": "Men's Sweaters",
    "turtleneck": "Men's Sweaters",
    "cowl neck": "Men's Sweaters",
    "men's trouser": "Men's Trousers",
    "trouser": "Men's Trousers",
    "cargo pant": "Men's Trousers",
    "chino pant": "Men's Trousers",
    "men's short": "Men's Shorts",
    "chino short": "Men's Shorts",
    "paper bag short": "Men's Shorts",
    "blazer": "Men's Blazers",
    "joggers": "Men's Activewear",
    "sweatpants": "Men's Activewear",
    "track": "Men's Activewear",
    "vest": "Men's Activewear",
    # Women's categories
    "women's jacket": "Women's Jackets",
    "jacket": "Women's Jackets",
    "coat": "Women's Jackets",
    "bomber": "Women's Jackets",
    "parka": "Women's Jackets",
    "trench": "Women's Jackets",
    "women's top": "Women's Tops",
    "top": "Women's Tops",
    "blouse": "Women's Tops",
    "tunic": "Women's Tops",
    "camisole": "Women's Tops",
    "crop top": "Women's Tops",
    "tank": "Women's Tops",
    "halter": "Women's Tops",
    "skirt": "Women's Skirts",
    "mini skirt": "Women's Skirts",
    "midi skirt": "Women's Skirts",
    "pencil skirt": "Women's Skirts",
    "pleated": "Women's Skirts",
    "women's cardigan": "Women's Cardigans",
    "cardigan": "Women's Cardigans",
    "kimono cardigan": "Women's Cardigans",
    "shrug": "Women's Cardigans",
    "leggings": "Women's Leggings",
    "palazzo": "Women's Palazzo Pants",
    "culottes": "Women's Palazzo Pants",
    "wide leg": "Women's Palazzo Pants",
    "jumpsuit": "Women's Jumpsuits",
    "kurti": "Women's Kurtis",
    "kurta": "Women's Kurtis",
    "saree": "Women's Sarees",
    "loungewear": "Women's Loungewear",
    "nightwear": "Women's Nightwear",
    "sleepwear": "Women's Nightwear",
    "pajama": "Women's Nightwear",
    # Kids & Baby categories
    "kids t-shirt": "Kids T-Shirts",
    "kids dress": "Kids Dresses",
    "dress": "Kids Dresses",
    "shift dress": "Kids Dresses",
    "maxi dress": "Kids Dresses",
    "midi dress": "Kids Dresses",
    "wrap dress": "Kids Dresses",
    "kids short": "Kids Shorts",
    "toddler": "Toddler Dungarees",
    "dungaree": "Toddler Dungarees",
    "overall": "Toddler Dungarees",
    "baby romper": "Baby Rompers",
    "romper": "Baby Rompers",
    "baby onesie": "Baby Onesies",
    "onesie": "Baby Onesies",
    "baby bodysuit": "Baby Bodysuits",
    "bodysuit": "Baby Bodysuits",
    "kids sleepwear": "Kids Sleepwear",
}
