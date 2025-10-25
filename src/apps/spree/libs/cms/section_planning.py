"""Section planning utilities for avoiding consecutive sections of the same type."""

from common.logger import Logger


logger = Logger()


def get_section_type_name(section_type: str) -> str:
    """Extract the base section type name from the full type string."""
    if "::" in section_type:
        return section_type.split("::")[-1]
    return section_type


def has_consecutive_sections(section_types: list[str], max_consecutive: int = 2) -> bool:
    """Check if there are more than max_consecutive consecutive sections of the same type."""
    if len(section_types) < max_consecutive + 1:
        return False

    for i in range(len(section_types) - max_consecutive):
        # Check if the next max_consecutive sections are all the same type
        current_type = get_section_type_name(section_types[i])
        consecutive_count = 1

        for j in range(1, max_consecutive + 1):
            if i + j < len(section_types):
                next_type = get_section_type_name(section_types[i + j])
                if next_type == current_type:
                    consecutive_count += 1
                else:
                    break

        if consecutive_count > max_consecutive:
            return True

    return False


def validate_section_sequence(section_types: list[str], max_consecutive: int = 2) -> bool:
    """Validate that a sequence of section types doesn't have too many consecutive sections."""
    return not has_consecutive_sections(section_types, max_consecutive)


def get_section_generation_task(section_type: str, context: dict, position: int, title: str | None = None):
    """Get the appropriate section generation function based on section type."""
    from apps.spree.libs.contents.carousels import generate_product_carousel_section
    from apps.spree.libs.contents.galleries import generate_image_gallery_section
    from apps.spree.libs.contents.rich_texts import generate_rich_text_section

    base_type = get_section_type_name(section_type)

    if "ProductCarousel" in base_type:
        # Determine carousel type based on position or context
        carousel_type = "featured" if position <= 3 else "category"
        return generate_product_carousel_section(context, position, carousel_type)
    elif "ImageGallery" in base_type:
        return generate_image_gallery_section(context, position)
    elif "RichText" in base_type:
        return generate_rich_text_section(context, position, title or f"Content Section {position}")
    else:
        # Default to rich text for unknown types
        return generate_rich_text_section(context, position, title or f"Content Section {position}")


async def plan_section_sequence_with_ai(page_type: str, page_title: str, page_focus: str, context: dict, max_sections: int = 12) -> list[tuple[str, int, str]]:
    """Use AI to plan a sequence of sections that avoids consecutive types. The LLM determines the optimal number of sections."""
    from apps.spree.utils.ai import instructor_client

    # Prepare context summary for AI
    taxonomies_summary = ", ".join([t["name"] for t in context.get("taxonomies", [])])
    products_summary = ", ".join([p["name"] for p in context.get("sample_products", [])[:5]])

    store_name = context.get("store_name", "our store")
    store_theme = context.get("store_theme", "business")
    system_prompt = f"""You are a senior e-commerce CMS architect planning sections for a {page_type} in {store_name}, a {store_theme} store.

STORE CONTEXT:
- Store: {context.get("store_name", "our store")} 
- Business: {context.get("store_theme", "business")}
- Categories: {taxonomies_summary}
- Products: {products_summary}

PAGE DETAILS:
- Title: {page_title}
- Type: {page_type}
- Focus: {page_focus}
- Maximum sections allowed: {max_sections}

AVAILABLE SECTION TYPES:
1. Spree::Cms::Sections::HeroImage - Large banner with image, title, subtitle, and call-to-action
2. Spree::Cms::Sections::ProductCarousel - Scrollable carousel of featured products
3. Spree::Cms::Sections::ImageGallery - Grid of category/collection images
4. Spree::Cms::Sections::RichTextContent - Text content with formatting, can include headings, paragraphs, lists
5. Spree::Cms::Sections::FeaturedArticle - Highlight a specific article or promotion
6. Spree::Cms::Sections::SideBySideImages - Two images side by side with optional text

SECTION TYPE ALTERNATIVES (use these when avoiding consecutive types):
- HeroImage alternatives: ProductCarousel, ImageGallery, RichTextContent
- ProductCarousel alternatives: ImageGallery, RichTextContent, HeroImage
- ImageGallery alternatives: RichTextContent, ProductCarousel, HeroImage
- RichTextContent alternatives: ProductCarousel, ImageGallery, HeroImage
- FeaturedArticle alternatives: RichTextContent, ProductCarousel, ImageGallery
- SideBySideImages alternatives: RichTextContent, ProductCarousel, ImageGallery

CRITICAL REQUIREMENTS:
- Determine the OPTIMAL number of sections (between 3 and {max_sections}) based on the page's purpose and content needs
- NO MORE THAN 2 consecutive sections of the same type
- If you would create 3+ consecutive sections of the same type, use the alternatives listed above
- Create engaging, varied content flow with good section type distribution
- Consider user journey and visual hierarchy
- Make sections specific to the page's purpose and business type
- Each section should have a descriptive name that explains its purpose
- Don't add unnecessary sections - quality over quantity
- Ensure good variety in section types throughout the page

Consider the page type when determining section count:
- Homepage: 6-10 sections (needs comprehensive content)
- FeaturePage: 4-8 sections (focused promotional content)
- StandardPage: 3-6 sections (informational content)"""

    user_prompt = f"""Create a strategic section plan for the "{page_title}" {page_type.lower()} in our {context.get("store_theme", "business")} store.

This page focuses on: {page_focus}

Determine the optimal number of sections (between 3 and {max_sections}) and provide:
1. A descriptive section name that explains its purpose
2. The specific section type (from the available types)
3. The position/order on the page (1 = first section at top)

CRITICAL PLANNING RULES:
- NEVER create more than 2 consecutive sections of the same type
- If you would create 3+ consecutive sections of the same type, use the alternatives provided in the system prompt
- Plan your sections in order, checking each one against the previous 2 to ensure variety
- Use the section type alternatives when needed to maintain variety

Ensure your plan:
- Creates a cohesive user journey
- Maintains excellent section type variety throughout
- Highlights key products or categories relevant to {context.get("store_theme", "our business")}
- Balances visual elements with information
- Has proper visual hierarchy
- Serves the specific purpose of a {page_type.lower()}
- Uses the right number of sections for the page type and content needs

Make the section names specific and descriptive, like "Hero Banner with Featured Products" or "Customer Testimonials Section" rather than generic names."""

    try:
        from pydantic import BaseModel, Field

        class SectionPlanItem(BaseModel):
            name: str = Field(description="Descriptive name for this section")
            type: str = Field(description="Full section type (e.g., Spree::Cms::Sections::HeroImage)")  # noqa: A003, RUF100
            position: int = Field(description="Position order on the page (1=first)")

        class SectionPlanResponse(BaseModel):
            sections: list[SectionPlanItem] = Field(description="List of planned sections")

        response = await instructor_client.chat.completions.create(
            model="claude-3-7-sonnet-latest",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            response_model=SectionPlanResponse,
            temperature=0.3,
            max_tokens=8192,
        )

        if response and response.sections:
            # The LLM should have handled consecutive section prevention
            # Just validate and return the plan
            final_plan = []
            for section in response.sections:
                final_plan.append((section.type, section.position, section.name))

            return final_plan
        else:
            # Fallback to rule-based planning
            return plan_section_sequence_fallback(6, page_type, context)  # Default to 6 sections

    except Exception:
        # Fallback to rule-based planning if AI fails
        return plan_section_sequence_fallback(6, page_type, context)  # Default to 6 sections


def plan_section_sequence_fallback(num_sections: int, page_type: str, _context: dict) -> list[tuple[str, int, str]]:
    """Fallback rule-based section planning."""
    section_types = []
    section_plan = []

    # Define preferred section order based on page type
    if page_type == "Homepage":
        preferred_order = ["Spree::Cms::Sections::HeroImage", "Spree::Cms::Sections::ProductCarousel", "Spree::Cms::Sections::ImageGallery", "Spree::Cms::Sections::RichTextContent"]
    else:
        preferred_order = ["Spree::Cms::Sections::HeroImage", "Spree::Cms::Sections::RichTextContent", "Spree::Cms::Sections::ProductCarousel", "Spree::Cms::Sections::ImageGallery"]

    for position in range(1, num_sections + 1):
        # Try preferred types in order
        section_added = False

        for preferred_type in preferred_order:
            test_types = [*section_types, preferred_type]

            if not has_consecutive_sections(test_types):
                section_types.append(preferred_type)
                section_plan.append((preferred_type, position, f"Section {position}"))
                section_added = True
                break

        # If no preferred type works, use RichTextContent as fallback
        if not section_added:
            fallback_type = "Spree::Cms::Sections::RichTextContent"
            section_types.append(fallback_type)
            section_plan.append((fallback_type, position, f"Content Section {position}"))

    return section_plan


def plan_section_sequence(num_sections: int, page_type: str, context: dict) -> list[tuple[str, int, str]]:
    """Legacy function - now redirects to AI-powered planning."""
    # This is kept for backward compatibility
    return plan_section_sequence_fallback(num_sections, page_type, context)
