from apps.spree.libs.cms.models import RichTextSection, RichTextSectionForGeneration, RichTextSettings
from apps.spree.utils.ai import instructor_client
from apps.spree.utils.constants import SPREE_SECTION_RICH_TEXT
from common.logger import Logger


logger = Logger()


async def generate_rich_text_content(context: dict) -> RichTextSection:
    """Generate rich text content for a section using structured models."""

    context = context.copy()
    del context["sample_products"]

    taxons_summary = ", ".join([f"{t['name']} (ID: {t['id']})" for t in context["taxons"][:10]])

    system_prompt = f"""Generate a Rich Text Content section for {context["store_name"]}, a {context["store_theme"]} store.
    Generate rich text content for the "{context["page_title"]}" page.

    AVAILABLE TAXONS FOR LINKING:
    {taxons_summary}

    RICH TEXT SECTION REQUIREMENTS:
    - name: Create a descriptive name that reflects the section's purpose
    - settings: Use default settings (gutters: "Gutters", text_alignment: "Left", padding: "Standard")
    - linked_resource_type: "Spree::Taxon" if linking to category, "Spree::Product" if linking to product, or null
    - linked_resource_id: Valid taxon ID or product ID from list above, or null

    CONTENT REQUIREMENTS:
    - rte_content: Generate rich text HTML content with proper structure (h1, h2, h3, p, ul, li, strong, em)
    - Content should be engaging, professional, and relevant to the store theme
    - Include 2-3 paragraphs of well-structured content
    - Focus on benefits and features relevant to the store theme
    - Optimize for readability and SEO

    Make the content specific to the {context["store_theme"]} business with engaging copy that would attract customers."""

    user_prompt = f"""Create engaging rich text content for {context["store_name"]}.

    Make it specific to our {context["store_theme"]} business with engaging copy that would attract customers.

    If linking to a category, use one of these taxons:
    {taxons_summary}

    Generate complete rich text content with proper HTML formatting and appropriate settings."""

    response = await instructor_client.chat.completions.create(
        model="claude-3-7-sonnet-latest",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        response_model=RichTextSectionForGeneration,
        max_tokens=2048,
    )

    return RichTextSection(
        name=response.name,
        content=f"<br>{response.content}</br>",
        settings=RichTextSettings(gutters=response.settings.gutters, text_alignment=response.settings.text_alignment, padding=response.settings.padding),
        linked_resource_type=response.linked_resource_type,
        linked_resource_id=response.linked_resource_id,
        fit="Container",
        destination=None,
        type=SPREE_SECTION_RICH_TEXT,
    )
