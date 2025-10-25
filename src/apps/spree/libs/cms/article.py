from apps.spree.libs.cms.models import FeaturedArticleSection, FeaturedArticleSectionForGeneration
from apps.spree.utils.ai import instructor_client
from apps.spree.utils.constants import SPREE_SECTION_FEATURED_ARTICLE
from common.logger import Logger


logger = Logger()


async def generate_featured_article_section(context: dict) -> FeaturedArticleSection:
    """Generate featured article content for a section using structured models."""

    context = context.copy()

    taxons_summary = ", ".join([f"{t['name']} (ID: {t['id']})" for t in context["taxons"][:10]])

    system_prompt = f"""Generate a Featured Article section for {context["store_name"]}, a {context["store_theme"]} store.
    Generate featured article content for the "{context["page_title"]}" page.

    AVAILABLE TAXONS FOR LINKING:
    {taxons_summary}

    FEATURED ARTICLE SECTION REQUIREMENTS:
    - name: Create a descriptive name that reflects the section's purpose
    - settings: Use default settings (gutters: "No Gutters")
    - linked_resource_type: "Spree::Taxon" if linking to category, "Spree::Product" if linking to product, or null
    - linked_resource_id: Valid taxon ID or product ID from list above, or null

    CONTENT REQUIREMENTS (CONCISE FOR CENTERED LAYOUT):
    - title: Create a compelling, attention-grabbing headline (3-6 words)
    - subtitle: Write a concise subtitle (1 sentence) that expands on the headline
    - button_text: Create a clear, action-oriented button text (2-3 words)
    - rte_content: Generate concise rich text HTML content (1-2 paragraphs) with proper structure (h1, h2, p, strong, em)
    - Content should be engaging, professional, and relevant to the store theme
    - Keep content concise since it will be displayed in a centered layout
    - Focus on key benefits and features relevant to the store theme
    - Optimize for readability and impact

    Make the content specific to the {context["store_theme"]} business with engaging copy that would attract customers."""

    user_prompt = f"""Create concise, engaging featured article content for {context["store_name"]}.

    Make it specific to our {context["store_theme"]} business with engaging copy that would attract customers.
    Keep content concise and impactful since it will be displayed in a centered layout.

    If linking to a category, use one of these taxons:
    {taxons_summary}

    Generate concise featured article content with compelling headline, subtitle, call-to-action, and brief rich text content."""

    response = await instructor_client.chat.completions.create(
        model="claude-3-7-sonnet-latest",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        response_model=FeaturedArticleSectionForGeneration,
        max_tokens=4096,
    )

    return FeaturedArticleSection(
        name=response.name,
        content=response.content,
        settings=response.settings,
        linked_resource_type=response.linked_resource_type,
        linked_resource_id=response.linked_resource_id,
        fit="Screen",
        destination=None,
        type=SPREE_SECTION_FEATURED_ARTICLE,
    )
