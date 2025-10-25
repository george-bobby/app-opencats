import asyncio
import json
from pathlib import Path

from apps.spree.config.settings import settings
from apps.spree.libs.cms.article import generate_featured_article_section
from apps.spree.libs.cms.carousel import generate_product_carousel_section
from apps.spree.libs.cms.gallery import generate_image_gallery_section
from apps.spree.libs.cms.hero import generate_hero_image_section
from apps.spree.libs.cms.models import Page, PageTemplate, SinglePageResponse, SpreeCmsPages, SpreeCmsSections, StandardPageResponse
from apps.spree.libs.cms.rich_texts import generate_rich_text_content
from apps.spree.libs.cms.side_by_side import generate_side_by_side_images_section
from apps.spree.utils.ai import instructor_client
from apps.spree.utils.constants import PRODUCTS_FILE, TAXONOMIES_FILE, TAXONS_FILE
from apps.spree.utils.faker import faker
from apps.spree.utils.ids import GlobalIdGenerator
from common.logger import Logger


logger = Logger()


async def load_context_data() -> dict:
    """Load context data from JSON files for AI generation."""
    context = {"store_name": settings.SPREE_STORE_NAME, "store_theme": settings.DATA_THEME_SUBJECT, "taxonomies": [], "taxons": [], "sample_products": []}

    # Load taxonomies
    if TAXONOMIES_FILE.exists():
        try:
            with Path.open(TAXONOMIES_FILE, encoding="utf-8") as f:
                taxonomies_data = json.load(f)
            context["taxonomies"] = taxonomies_data.get("taxonomies", [])
            logger.info(f"  Loaded {len(context['taxonomies'])} taxonomies for context")
        except Exception as e:
            logger.warning(f"Could not load taxonomies: {e}")

    # Load taxons (subcategories)
    if TAXONS_FILE.exists():
        try:
            with Path.open(TAXONS_FILE, encoding="utf-8") as f:
                taxons_data = json.load(f)
            # Get all taxons with their IDs and names for AI context
            all_taxons = taxons_data.get("taxons", [])
            context["taxons"] = [{"id": t.get("id"), "name": t.get("name"), "parent_name": t.get("parent_name")} for t in all_taxons]
            logger.info(f"  Loaded {len(context['taxons'])} taxons for context")
        except Exception as e:
            logger.warning(f"Could not load taxons: {e}")

    # Load sample products
    if PRODUCTS_FILE.exists():
        try:
            with Path.open(PRODUCTS_FILE, encoding="utf-8") as f:
                products_data = json.load(f)
            # Get random sample of products and extract only relevant data for context
            all_products = products_data.get("products", [])
            sample_size = min(100, len(all_products))  # Take up to 30 products, or all if less than 30
            if all_products:
                sampled_products = faker.random_elements(all_products, length=sample_size, unique=True)
                context["sample_products"] = [{"id": product.get("id"), "name": product.get("name"), "taxon_ids": product.get("taxon_ids", [])} for product in sampled_products]
            else:
                context["sample_products"] = []
            logger.info(f"  Loaded {len(context['sample_products'])} randomly sampled products for context")
        except Exception as e:
            logger.warning(f"Could not load products: {e}")

    return context


async def generate_standard_page_content(context: dict, page_template: PageTemplate, page_id: int) -> Page | None:
    """Generate content for a StandardPage (HTML content only, no sections)."""

    # Prepare context summary for AI
    taxonomies_summary = ", ".join([t["name"] for t in context["taxonomies"]])
    products_summary = ", ".join([p["name"] for p in context["sample_products"][:5]])

    # Generate HTML content for StandardPage
    system_prompt = f"""Generate HTML content for the {page_template.title} page of {context["store_name"]}, a {context["store_theme"]} store.

    STORE CONTEXT:
    - Store: {context["store_name"]} 
    - Business: {context["store_theme"]}
    - Categories: {taxonomies_summary}
    - Products: {products_summary}
    
    PAGE DETAILS:
    - Title: {page_template.title}
    - Type: {page_template.type} (StandardPage - HTML content only, no sections)
    - Slug: {page_template.slug}
    - Focus: {page_template.focus}

    STANDARDPAGE REQUIREMENTS:
    - Generate HTML content that goes directly into the page's content field
    - No sections - this is a simple HTML page
    - Content should be comprehensive and self-contained
    - Use proper HTML structure (h1, h2, h3, p, ul, li, strong, em, etc.)
    - Make it informative and helpful for customers
    - Include relevant information based on the page title and focus"""

    user_prompt = f"""Create comprehensive HTML content for the {page_template.title} page of {context["store_name"]}.

    This is a StandardPage, so generate HTML content that will be stored directly in the page's content field.

    Requirements:
    - Title: {page_template.title}
    - Meta title: Include store name for SEO (under 60 chars)
    - Meta description: SEO description (150-160 characters)
    - Slug: {page_template.slug}
    - Type: {page_template.type}
    - Visible: true
    - Locale: en
    - Content: Generate comprehensive HTML content (not sections)

    Content should be:
    - Specific to our {context["store_theme"]} business
    - Professional and informative
    - Well-structured HTML with proper headings and paragraphs
    - SEO optimized
    - Customer-focused and helpful
    - Comprehensive enough to be a standalone page

    Make it relevant to our categories: {taxonomies_summary}

    Generate the complete HTML content that customers will see on this page."""

    page_response = await instructor_client.chat.completions.create(
        model="claude-3-7-sonnet-latest",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        response_model=StandardPageResponse,
        max_tokens=8192,
    )

    # For StandardPage, return page with HTML content and no sections
    page = Page(
        id=page_id,
        title=page_response.page.title,
        meta_title=page_response.page.meta_title,
        content=page_response.page.content,  # HTML content for StandardPage
        meta_description=page_response.page.meta_description,
        visible=page_response.page.visible,
        slug=page_response.page.slug,
        type=page_template.type,
        locale=page_response.page.locale,
        sections=[],  # No sections for StandardPage
    )

    return page


async def generate_feature_page_content(context: dict, page_template: PageTemplate, page_id: int) -> Page | None:
    """Generate content for a Homepage or FeaturePage (sections only, no HTML content)."""

    # Prepare context summary for AI
    taxonomies_summary = ", ".join([t["name"] for t in context["taxonomies"]])
    products_summary = ", ".join([p["name"] for p in context["sample_products"][:5]])

    # Generate sections for Homepage and FeaturePage
    system_prompt = f"""Generate content for the {page_template.title} page of {context["store_name"]}, a {context["store_theme"]} store.

    STORE CONTEXT:
    - Store: {context["store_name"]} 
    - Business: {context["store_theme"]}
    - Categories: {taxonomies_summary}
    - Products: {products_summary}
    
    PAGE DETAILS:
    - Title: {page_template.title}
    - Type: {page_template.type}
    - Slug: {page_template.slug}
    - Focus: {page_template.focus}"""

    user_prompt = f"""Create the {page_template.title} page content for {context["store_name"]}.

    Requirements:
    - Title: {page_template.title}
    - Meta title: Include store name for SEO (under 60 chars)
    - Meta description: SEO description (150-160 characters)
    - Slug: {page_template.slug}
    - Type: {page_template.type}
    - Visible: true
    - Locale: en

    Content should be:
    - Specific to our {context["store_theme"]} business
    - Professional and engaging
    - Well-structured HTML
    - SEO optimized
    - Customer-focused

    Make it relevant to our categories: {taxonomies_summary}"""

    page_response = await instructor_client.chat.completions.create(
        model="claude-3-7-sonnet-latest",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        response_model=SinglePageResponse,
        max_tokens=8192,
    )

    generated_sections = []

    logger.info(f"Generating {len(page_template.sections_needed)} sections for {page_template.title}")

    # Generate sections concurrently
    section_tasks = []
    section_types = []

    for idx, section in enumerate(page_template.sections_needed):
        if section == SpreeCmsSections.HERO_IMAGE:
            task = generate_hero_image_section(context)
        elif section == SpreeCmsSections.FEATURED_ARTICLE:
            task = generate_featured_article_section(context)
        elif section == SpreeCmsSections.PRODUCT_CAROUSEL:
            task = generate_product_carousel_section(context)
        elif section == SpreeCmsSections.IMAGE_GALLERY:
            task = generate_image_gallery_section(context)
        elif section == SpreeCmsSections.SIDE_BY_SIDE_IMAGES:
            task = generate_side_by_side_images_section(context)
        elif section == SpreeCmsSections.RICH_TEXT:
            task = generate_rich_text_content(context)
        else:
            continue

        section_tasks.append(task)
        section_types.append((idx, section))

    # Execute all section generation tasks concurrently
    if section_tasks:
        section_results = await asyncio.gather(*section_tasks, return_exceptions=True)

        # Process results in the correct order
        valid_results = []
        for (idx, section_type), section_content in zip(section_types, section_results, strict=False):
            if isinstance(section_content, Exception):
                logger.error(f"Failed to generate {section_type} section: {section_content}")
                continue
            valid_results.append((idx, section_type, section_content))

        for idx, _section_type, section_content in valid_results:
            section_content.id = GlobalIdGenerator("spree_cms_sections").get_next_id()
            section_content.position = idx + 1
            section_content.cms_page_id = page_id
            generated_sections.append(section_content)

    # For Homepage/FeaturePage, return page with sections and no HTML content
    page = Page(
        id=page_id,
        title=page_response.page.title,
        meta_title=page_response.page.meta_title,
        content=None,  # No HTML content for Homepage/FeaturePage
        meta_description=page_response.page.meta_description,
        visible=page_response.page.visible,
        slug=page_response.page.slug,
        type=page_template.type,
        locale=page_response.page.locale,
        sections=generated_sections,
    )

    return page


async def generate_page_content(context: dict, page_template: PageTemplate, page_id: int) -> Page | None:
    """Generate content for a specific page based on its type."""

    context = context.copy()
    context["page_title"] = page_template.title
    context["page_type"] = page_template.type

    # Route to appropriate generation function based on page type
    if page_template.type == SpreeCmsPages.STANDARDPAGE:
        return await generate_standard_page_content(context, page_template, page_id)
    else:
        return await generate_feature_page_content(context, page_template, page_id)
