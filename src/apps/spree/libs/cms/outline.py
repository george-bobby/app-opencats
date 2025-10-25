from apps.spree.libs.cms.models import PageListResponse, PageTemplate, SpreeCmsPages, SpreeCmsSections
from apps.spree.utils.ai import instructor_client
from common.logger import Logger


logger = Logger()


async def generate_outline(context: dict, number_of_pages: int) -> list[PageTemplate]:
    """First step: Generate a list of pages that should be created for this store."""

    logger.info(f"Planning {number_of_pages} pages for {context['store_name']}...")

    # Prepare context summary for AI
    taxonomies_summary = ", ".join([t["name"] for t in context["taxonomies"]])
    products_summary = ", ".join([p["name"] for p in context["sample_products"][:5]])

    system_prompt = f"""You are planning CMS pages for {context["store_name"]}, a {context["store_theme"]} store.

    STORE CONTEXT:
    - Store Name: {context["store_name"]}
    - Business Type: {context["store_theme"]} 
    - Categories: {taxonomies_summary}
    - Sample Products: {products_summary}
    
    PAGE TYPES AVAILABLE: {SpreeCmsPages}
    
    REQUIREMENTS:
    - ALWAYS include a Homepage as the first page
    - Consider the store's specific business type and products
    - Create pages that would be most valuable for this type of business
    - Standard pages: About, Contact, Shipping/Returns, Privacy Policy, FAQ
    - Feature pages: Product showcases, educational content, promotions
    - Priority 1 = most important, higher numbers = less important
    
    Generate {number_of_pages} pages that would be most relevant and valuable for this specific store."""

    user_prompt = f"""Plan {number_of_pages} CMS pages for {context["store_name"]}.
    
    Based on our business ({context["store_theme"]}) and categories ({taxonomies_summary}), what pages would be most valuable?
    
    For each page, provide:
    - title: Clear page title
    - type: Choose from Homepage, FeaturePage, or StandardPage (with full namespace)
    - slug: URL-friendly slug
    - focus: What content/purpose this page should serve
    - priority: 1-10 (1=most important)
    
    Consider pages like:
    - Homepage (required)
    - About Us, Contact, Privacy Policy (standard business pages)
    - Product education/guides relevant to {context["store_theme"]}
    - Feature pages for promotions, new arrivals, best sellers
    - Customer service pages (FAQ, Shipping, Returns)
    - Sections that this page should have. Choose from: {SpreeCmsSections}. Homepage should have all sections.
    - The number of sections should be relevant to the page type and content needs.
    - The more taxons there are, the more sections should be added, but not too many.
    
    Make the page list specific to our {context["store_theme"]} business focus."""

    list_response = await instructor_client.chat.completions.create(
        model="claude-3-7-sonnet-latest",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        response_model=PageListResponse,
        max_tokens=4096,
    )

    if list_response and list_response.pages:
        # Sort by priority and limit to requested number
        sorted_pages = sorted(list_response.pages, key=lambda x: x.priority)[:number_of_pages]
        logger.info(f"✓ Planned {len(sorted_pages)} pages:")
        for page in sorted_pages:
            logger.info(f"  {page.priority}. {page.title} ({page.type.split('::')[-1]}) - /{page.slug}")
        return sorted_pages
    else:
        raise ValueError("Failed to generate page list")
