from apps.spree.config.settings import settings
from apps.spree.utils.ai import instructor_client
from apps.spree.utils.constants import IMAGE_TAG_PLACEHOLDER
from common.logger import Logger

from .helpers import _extract_product_specs
from .models import ProductDescriptionForGeneration, ProductForGeneration, SingleDescriptionResponse


logger = Logger()


def _system_prompt(taxons_context: str, target_taxon: dict | None) -> str:
    """Build focused system prompt for marketing content generation."""
    category_context = ""
    if target_taxon:
        category_context = f"""
TARGET MARKET: {target_taxon["name"]} category
CATEGORY CONTEXT: {target_taxon.get("description", "Pet supplies")}
"""

    return f"""Generate compelling marketing content for {settings.SPREE_STORE_NAME}.

FOCUS: Marketing copy only - persuasive descriptions and SEO content.

CONTENT STRATEGY:
- Emotional appeal and benefit-focused messaging
- Professional HTML formatting with strategic structure
- SEO optimization for search engines
- Visual storytelling through image placement

{taxons_context}
{category_context}

TONE: Professional, persuasive, benefit-focused, conversion-oriented."""


def _user_prompt(product_specs: dict) -> str:
    """Build focused user prompt for marketing content."""
    variant_info = ""
    if product_specs["has_variants"]:
        variant_info = f"""
    PRODUCT OPTIONS: {product_specs["variant_count"]} variants available
    PRICING: {product_specs["price_range"]}
    SAMPLE OPTIONS: {", ".join(product_specs["sample_variants"])}"""
    else:
        variant_info = f"SINGLE PRODUCT: ${product_specs['master_price']:.2f}"

    return f"""Create marketing content for:

    PRODUCT: {product_specs["name"]}
    {variant_info}
    
    DELIVERABLES:
    - description: Rich HTML marketing copy (4-6 paragraphs)
      * <p><strong> benefit-driven opening
      * <h3> + <ul><li><strong> feature highlights  
      * Persuasive content with {IMAGE_TAG_PLACEHOLDER} placeholders
      * Trust signals and emotional appeal
    - meta_title: SEO-optimized title (50-60 chars)
    - meta_description: Compelling search preview (150-160 chars)
    - meta_keywords: Search-relevant keywords
    
    Transform technical specs into persuasive marketing content that converts."""


async def generate_product_description(
    basic_product: ProductForGeneration,
    taxons_context: str,
    target_taxon: dict | None = None,
) -> ProductDescriptionForGeneration | None:
    """Generate marketing content for a technical product specification."""
    # start_time = time.time()
    logger.debug(f"Generating description for product: {basic_product.name}")

    # Extract product specs for marketing context
    product_specs = _extract_product_specs(basic_product)

    system_prompt = _system_prompt(taxons_context, target_taxon)

    user_prompt = _user_prompt(product_specs)

    description_response = await instructor_client.chat.completions.create(
        model="claude-3-5-haiku-latest",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        response_model=SingleDescriptionResponse,
        temperature=0.8,  # Higher temperature for creative marketing content
        max_tokens=4096,
    )

    # logger.info(f"Successfully generated description for: {basic_product.name} in {time.time() - start_time:.2f} seconds")

    return description_response.description
