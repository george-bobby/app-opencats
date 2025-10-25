from datetime import datetime

from apps.spree.libs.cms.models import (
    ProductCarouselSection,
    ProductCarouselSectionForGeneration,
    SpreeCmsPages,
)
from apps.spree.utils.ai import instructor_client
from apps.spree.utils.database import db_client
from common.logger import Logger


logger = Logger()


async def generate_product_carousel_section(context: dict, carousel_type: str = "featured") -> ProductCarouselSection:
    """Generate a Product Carousel section with valid taxon linking."""

    # Get available taxons and products from context
    available_taxons = context.get("taxons", [])
    available_products = context.get("sample_products", [])

    # Generate carousel content using LLM
    context = context.copy()
    del context["sample_products"]

    # Determine if this is for a homepage (more generic taxons needed)
    is_homepage = context.get("page_type") == SpreeCmsPages.HOMEPAGE
    page_title = context.get("page_title", "")

    taxons_summary = ", ".join([f"{t['name']} (ID: {t['id']})" for t in available_taxons[:10]])
    products_summary = ", ".join([f"{p['name']} (ID: {p['id']})" for p in available_products[:10]])

    if is_homepage:
        # Homepage: Link to taxons only
        system_prompt = f"""Generate a Product Carousel section for {context["store_name"]}, a {context["store_theme"]} store.
        Generate a {carousel_type} product carousel section for the HOMEPAGE.

        AVAILABLE TAXONS FOR LINKING:
        {taxons_summary}

        PRODUCT CAROUSEL SECTION REQUIREMENTS:
        - name: Create a descriptive name that reflects the carousel's purpose
        - linked_resource_type: "Spree::Taxon" (homepage carousels must link to taxons)
        - linked_resource_id: Valid taxon ID from list above

        HOMEPAGE TAXON SELECTION RULES:
        - Choose broad, general taxons that appeal to all visitors
        - Good homepage taxons: "Pet Food", "Toys", "Accessories", "Beds", "Health & Care"
        - Avoid very specific or niche taxons
        - Prioritize popular, widely-appealing categories
        - Make the content specific to the {context["store_theme"]} business with engaging copy

        Make the content specific to the {context["store_theme"]} business with engaging copy that would attract customers."""
    else:
        # Other pages: Can link to products or taxons, must be related to page title
        system_prompt = f"""Generate a Product Carousel section for {context["store_name"]}, a {context["store_theme"]} store.
        Generate a {carousel_type} product carousel section for page: "{page_title}"

        AVAILABLE TAXONS FOR LINKING:
        {taxons_summary}

        AVAILABLE PRODUCTS FOR LINKING:
        {products_summary}

        PRODUCT CAROUSEL SECTION REQUIREMENTS:
        - name: Create a descriptive name that reflects the carousel's purpose
        - linked_resource_type: "Spree::Taxon" or "Spree::Product"
        - linked_resource_id: Valid taxon ID or product ID from lists above

        PAGE-SPECIFIC LINKING RULES:
        - The carousel MUST be related to the page title: "{page_title}"
        - Choose taxons or products that are directly relevant to this specific page
        - For category pages: Link to related products or sub-categories
        - For product pages: Link to similar products or related categories
        - For brand pages: Link to brand products or brand categories
        - Prioritize relevance to the page content over generic selections

        Make the content specific to the {context["store_theme"]} business and relevant to the page: "{page_title}" """

    user_prompt = f"""Create a compelling {carousel_type} product carousel section for {context["store_name"]}.

    Make it specific to our {context["store_theme"]} business with engaging copy that would attract customers.

    {
        "Choose an appropriate taxon from these available options for the homepage:"
        if is_homepage
        else f'Choose an appropriate taxon or product from these available options, related to the page "{page_title}":'
    }

    {f"Available taxons: {taxons_summary}" if is_homepage else f"Available taxons: {taxons_summary}\nAvailable products: {products_summary}"}

    Generate a complete carousel section with a descriptive name and proper linking."""

    response = await instructor_client.chat.completions.create(
        model="claude-3-7-sonnet-latest",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        response_model=ProductCarouselSectionForGeneration,
        max_tokens=2048,
    )

    if response:
        return ProductCarouselSection(
            linked_resource_type=response.linked_resource_type,
            linked_resource_id=response.linked_resource_id,
            name=response.name,
            content=None,
            settings=None,
        )
    else:
        raise ValueError("Failed to generate product carousel section")


async def seed_carousel_sections() -> None:
    """Create product carousel sections with proper taxon linking."""

    # Get all carousel sections
    carousel_sections = await db_client.fetch(
        """
        SELECT id, name, content, linked_resource_id
        FROM spree_cms_sections 
        WHERE type = 'Spree::Cms::Sections::ProductCarousel'
        ORDER BY id
        """
    )

    if not carousel_sections:
        logger.warning("No carousel sections found to update")
        return

    # Load available taxons from database (without parent_name)
    available_taxons = await db_client.fetch(
        """
        SELECT id, name, parent_id
        FROM spree_taxons
        WHERE parent_id IS NOT NULL
        ORDER BY name
        """
    )

    if not available_taxons:
        logger.warning("No taxons available for carousel linking")
        return

    # Get good taxons for carousels (non-root taxons)
    category_taxons = [t for t in available_taxons if t["parent_id"] is not None]
    if not category_taxons:
        category_taxons = available_taxons[:5]  # Fallback

    updated_sections = 0

    for i, section in enumerate(carousel_sections):
        try:
            section_id = section["id"]

            # Select a taxon for this carousel (cycle through available taxons)
            selected_taxon = category_taxons[i % len(category_taxons)]

            # Update the carousel section
            await db_client.execute(
                """
                UPDATE spree_cms_sections 
                SET linked_resource_type = $1, linked_resource_id = $2, updated_at = $3
                WHERE id = $4
                """,
                "Spree::Taxon",
                selected_taxon["id"],
                datetime.now(),
                section_id,
            )

            updated_sections += 1

        except Exception as e:
            logger.error(f"❌ Failed to update carousel section {section_id}: {e}")
            continue
