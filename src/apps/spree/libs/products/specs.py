import random
from datetime import datetime, timedelta

from apps.spree.config.settings import settings
from apps.spree.utils.ai import instructor_client
from apps.spree.utils.faker import faker
from common.logger import Logger

from .helpers import _build_constraints_context, _deduplicate_variants
from .models import ProductForGeneration, SingleProductResponse


logger = Logger()

BATCH_SIZE = settings.MAX_CONCURRENT_GENERATION_REQUESTS


def _system_prompt(prototypes_context: str, option_types_context: str, properties_context: str, taxons_context: str, constraints: str, price_range: str) -> str:
    """Build focused system prompt for technical product generation."""
    return f"""Generate technical product specifications for {settings.SPREE_STORE_NAME}.

FOCUS: Technical data only - no marketing copy, descriptions, or promotional content.

SPREE DATA MODEL:
- Prototypes: Define option types and properties for products
- Variants: All combinations of option values (Size × Color = matrix)
- Master variant: Base configuration with master price

AVAILABLE DATA:
{prototypes_context}
{option_types_context}
{properties_context}
    {taxons_context}

CONSTRAINTS:
{constraints}

PRICING GUIDELINES:
- Target price range: {price_range}
- Master price should be within this range
- Variant prices can vary ±20% from master price

PRODUCT NAMING:
- ALWAYS include the brand name in the product name
- Format: "[Brand Name] [Product Type/Description]"
- Examples: "Royal Canin Adult Dog Food", "Kong Classic Dog Toy", "Purina Pro Plan Puppy Formula"
- Make product names clear, functional, and brand-specific

TAXON ASSOCIATION:
- ALWAYS include the brand taxon ID in taxon_ids when a brand is specified
- Brand taxon ID is mandatory - never omit it
- Use the taxon IDs from the available taxons list above

VARIANT LOGIC:
- Single option type (Size only): Generate all size variants
- Multiple option types (Size + Color): Generate ALL combinations (Size × Color)
- Empty variants []: Single-variant product
- CRITICAL: Each variant must have unique option_values combination
- NO DUPLICATES: Never create two variants with identical option_values

IMAGE KEYWORDS:
- Generate 3-6 concise, subject-focused terms for stock photos
- Use primary subject only (e.g., "dog treat" not "happy dog eating treat")
- Focus on the main product/subject, avoid descriptive actions or emotions

OUTPUT: Pure technical specifications ready for database insertion."""


def _user_prompt(product_index: int, selected_taxons: list[dict] | None, price_range: str) -> str:
    """Build focused user prompt for technical generation."""

    # Find brand from selected taxons
    target_brand = None
    if selected_taxons:
        for taxon in selected_taxons:
            if taxon.get("parent_name") == "Brands":
                target_brand = taxon
                break

    brand_focus = ""
    if target_brand:
        brand_focus = f"BRAND FOCUS: Create product for '{target_brand['name']}' brand (ID: {target_brand['id']}) - MUST include this brand ID in taxon_ids"

    # Build list of required taxon IDs
    required_taxon_ids = []
    if selected_taxons:
        for taxon in selected_taxons:
            required_taxon_ids.append(f"{taxon['name']} (ID: {taxon['id']})")

    taxon_requirements = ""
    if required_taxon_ids:
        taxon_requirements = f"REQUIRED TAXON IDs: {', '.join(required_taxon_ids)}"

    return f"""Generate technical product data:

    {brand_focus}
    {taxon_requirements}
    
    PRICE RANGE: {price_range}
    
    REQUIRED OUTPUT:
    - name: Clear, functional product name that includes the brand name (e.g., "Royal Canin Adult Dog Food" or "Kong Classic Dog Toy")
    - prototype_id: Select from available prototypes
    - master_price: Realistic base price within {price_range}
    - sku: [CODE]-{product_index:03d} format
    - variants: Generate ALL option combinations OR empty [] for single variant
    - image_keywords: 3-6 concise subject terms for stock photos
    - status: "active"
    - promotionable: true
    - taxon_ids: {f"MUST include ALL of these IDs: [{', '.join([str(t['id']) for t in selected_taxons])}]" if selected_taxons else "1-3 category IDs"}
    
    VARIANT STRUCTURE:
    - Each variant needs: option_values[], price, stock_quantity, sku_suffix, position
    - Sequential positions: 1, 2, 3...
    - Stock quantities: 100-500 per variant
    
    Create complete technical specifications for database insertion."""


async def generate_product_specs(
    prototypes_context: str,
    option_types_context: str,
    properties_context: str,
    taxons_context: str,
    product_index: int,
    existing_names: set[str] | None = None,
    existing_skus: set[str] | None = None,
    selected_taxons: list[dict] | None = None,
) -> ProductForGeneration | None:
    """Generate technical product specifications only (no marketing content)."""
    # start_time = time.time()
    # logger.info(f"Generating product specs for {product_index}")

    # Generate random price range
    price_ranges = [
        (5.99, 29.99),
        (15.99, 59.99),
        (29.99, 99.99),
        (49.99, 199.99),
        (99.99, 499.99),
        (499.99, 999.99),
        (999.99, 9999.99),
    ]
    min_price, max_price = faker.random_element(price_ranges)
    price_range = f"${min_price:.2f} - ${max_price:.2f}"

    # Prepare constraints
    constraints = _build_constraints_context(existing_names, existing_skus, None)

    system_prompt = _system_prompt(prototypes_context, option_types_context, properties_context, taxons_context, constraints, price_range)

    user_prompt = _user_prompt(product_index, selected_taxons, price_range)

    try:
        product_response = await instructor_client.chat.completions.create(
            model="claude-3-5-haiku-latest",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            response_model=SingleProductResponse,
            max_tokens=4096,
        )

        # Deduplicate variants to avoid database constraint violations
        product_with_date = product_response.product
        if product_with_date.variants:
            original_count = len(product_with_date.variants)
            product_with_date.variants = _deduplicate_variants(product_with_date.variants)
            if len(product_with_date.variants) < original_count:
                logger.info(f"Removed {original_count - len(product_with_date.variants)} duplicate variants from product {product_index}")

        # Add a random past date for availability
        random_days = random.randint(1, 365)
        past_date = (datetime.now() - timedelta(days=random_days)).strftime("%Y-%m-%d")
        product_with_date.available_on = past_date

        # logger.info(f"Generated product specs for {product_index} in {time.time() - start_time:.2f} seconds")

        return product_with_date

    except Exception as e:
        logger.error(f"Error generating product {product_index}: {e}")
        return None
