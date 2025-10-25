"""Common models used across content generation modules."""

from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field


# Type aliases for reusability
SpreeLinkType = Literal["Spree::Taxon", "Spree::Product"]
SpreeFitType = Literal["Screen", "Container"]


class SpreeCmsPages(str, Enum):
    HOMEPAGE = "Spree::Cms::Pages::Homepage"
    FEATUREPAGE = "Spree::Cms::Pages::FeaturePage"
    STANDARDPAGE = "Spree::Cms::Pages::StandardPage"


class SpreeCmsSections(str, Enum):
    HERO_IMAGE = "Spree::Cms::Sections::HeroImage"
    FEATURED_ARTICLE = "Spree::Cms::Sections::FeaturedArticle"
    PRODUCT_CAROUSEL = "Spree::Cms::Sections::ProductCarousel"
    IMAGE_GALLERY = "Spree::Cms::Sections::ImageGallery"
    SIDE_BY_SIDE_IMAGES = "Spree::Cms::Sections::SideBySideImages"
    RICH_TEXT = "Spree::Cms::Sections::RichTextContent"


class Page(BaseModel):
    """Individual CMS page model."""

    id: int = Field(description="Unique identifier for the page")  # noqa: A003, RUF100
    title: str = Field(description="Page title")
    meta_title: str | None = Field(description="SEO meta title")
    content: str | None = Field(description="HTML content of the page (for StandardPage) or null (for Homepage/FeaturePage)", default=None)
    meta_description: str | None = Field(description="SEO meta description")
    visible: bool = Field(description="Whether the page is visible", default=True)
    slug: str = Field(description="URL slug for the page")
    type: SpreeCmsPages = Field(description="Page type (Homepage, FeaturePage, StandardPage)")  # noqa: A003, RUF100
    locale: str = Field(description="Page locale", default="en")
    sections: list = Field(description="List of sections for the page (only for Homepage/FeaturePage, not StandardPage)", default_factory=list)


class PageForGeneration(BaseModel):
    """Page model for AI generation (without ID)."""

    title: str = Field(description="Page title")
    meta_title: str | None = Field(description="SEO meta title")
    meta_description: str | None = Field(description="SEO meta description")
    visible: bool = Field(description="Whether the page is visible", default=True)
    slug: str = Field(description="URL slug for the page")
    locale: str = Field(description="Page locale", default="en")


class StandardPageForGeneration(BaseModel):
    """StandardPage model for AI generation (with HTML content)."""

    title: str = Field(description="Page title")
    meta_title: str | None = Field(description="SEO meta title")
    content: str = Field(description="HTML content for the StandardPage")
    meta_description: str | None = Field(description="SEO meta description")
    visible: bool = Field(description="Whether the page is visible", default=True)
    slug: str = Field(description="URL slug for the page")
    locale: str = Field(description="Page locale", default="en")


class StandardPageResponse(BaseModel):
    """Response format for a single generated StandardPage."""

    page: StandardPageForGeneration


class PageResponse(BaseModel):
    """Response format for generated pages."""

    pages: list[PageForGeneration]


class SinglePageResponse(BaseModel):
    """Response format for a single generated page."""

    page: PageForGeneration


class PageTemplate(BaseModel):
    """Template for a page to be generated."""

    title: str = Field(description="Page title")
    type: SpreeCmsPages = Field(description="Page type (Homepage, FeaturePage, StandardPage)")  # noqa: A003, RUF100
    slug: str = Field(description="URL slug for the page")
    focus: str = Field(description="What this page should focus on and contain")
    priority: int = Field(description="Priority order (1=highest priority)")
    sections_needed: list[SpreeCmsSections] = Field(description="List of section types needed for this page (only for Homepage/FeaturePage, not StandardPage)", default_factory=list)


class PageListResponse(BaseModel):
    """Response format for generated page list."""

    pages: list[PageTemplate]


class Section(BaseModel):
    """Individual CMS section model."""

    id: int = Field(description="Unique identifier for the section")  # noqa: A003, RUF100
    name: str = Field(description="Section name")
    content: str | None = Field(description="JSON content for the section")
    settings: str | None = Field(description="JSON settings for the section")
    fit: str | None = Field(description="How the section fits (Screen, Container, etc.)")
    destination: str | None = Field(description="Link destination")
    type: str = Field(description="Section type")  # noqa: A003, RUF100
    position: int = Field(description="Position order of the section")
    linked_resource_type: str | None = Field(description="Type of linked resource")
    linked_resource_id: int | None = Field(description="ID of linked resource")
    cms_page_id: int = Field(description="ID of the CMS page this section belongs to")


class SectionForGeneration(BaseModel):
    """Section model for AI generation (without ID and cms_page_id)."""

    name: str = Field(description="Section name")
    content: str | None = Field(description="JSON content for the section (for rich text, this contains rte_content key)")
    settings: str | None = Field(description="JSON settings for the section")
    fit: str | None = Field(description="How the section fits (Screen, Container, etc.)")
    destination: str | None = Field(description="Link destination")
    type: str = Field(description="Section type")  # noqa: A003, RUF100
    position: int = Field(description="Position order of the section")
    linked_resource_type: str | None = Field(description="Type of linked resource")
    linked_resource_id: int | None = Field(description="ID of linked resource")


class SectionsResponse(BaseModel):
    """Response format for generated sections."""

    sections: list[SectionForGeneration]


class SingleSectionResponse(BaseModel):
    """Response format for a single generated section."""

    section: SectionForGeneration


class HeroImageContent(BaseModel):
    title: str = Field(
        description="Create a compelling, attention-grabbing headline (5-8 words) that clearly communicates the main value proposition or message",
        examples=["Premium Care for Your Furry Family", "Discover Amazing Products", "Quality You Can Trust"],
    )
    subtitle: str = Field(
        description="Write an engaging subtitle (1-2 sentences) that expands on the headline and provides more context or benefits",
        examples=[
            "Discover quality pet supplies that bring joy to your pets and peace of mind to you",
            "Shop the latest trends and find the perfect items for your lifestyle",
            "Experience exceptional service and products that exceed your expectations",
        ],
    )
    button_text: str = Field(
        description="Create a clear, action-oriented button text (2-4 words) that encourages users to take the next step",
        examples=["Shop Now", "Learn More", "Get Started", "Explore Products", "View Collection"],
    )


class HeroImageSettings(BaseModel):
    gutters: Literal["Gutters", "No Gutters"] = Field(
        description="Gutter setting for the section layout. Use 'Gutters' for standard spacing or 'No Gutters' for edge-to-edge layout",
        default="Gutters",
        examples=["Gutters", "No Gutters"],
    )


class HeroImageSection(BaseModel):
    id: int = Field(description="Unique identifier for the section", default=-1)  # noqa: A003, RUF100
    name: str = Field(description="Section name")
    content: HeroImageContent = Field(description="Structured content for the hero section")
    settings: HeroImageSettings = Field(description="Structured settings for the hero section")
    fit: SpreeFitType = Field(description="How the section fits in the layout", default="Screen")
    destination: str | None = Field(description="Link destination", default=None)
    type: str = SpreeCmsSections.HERO_IMAGE  # noqa: A003, RUF100
    position: int = Field(description="Position order of the section", default=-1)
    linked_resource_type: Literal["Spree::Taxon", "Spree::Product"] | None = Field(description="Type of linked resource (e.g., Spree::Taxon)")
    linked_resource_id: int | None = Field(description="ID of linked resource")
    cms_page_id: int = Field(description="ID of the CMS page this section belongs to", default=-1)
    created_at: str | None = Field(description="Creation timestamp", default=None)
    updated_at: str | None = Field(description="Last update timestamp", default=None)
    image_url: str | None = Field(description="URL of the image for the hero section", default=None)
    keywords: list[str] = Field(description="List of keywords for the hero section", default_factory=list)


class HeroImageSectionForGeneration(BaseModel):
    name: str = Field(
        description="Create a descriptive name for this hero section that reflects its purpose and content", examples=["Main Hero Banner", "Welcome Hero Section", "Product Showcase Hero"]
    )
    content: HeroImageContent = Field(description="Generate compelling hero content with engaging headline, subtitle, and call-to-action")
    settings: HeroImageSettings = Field(description="Layout settings for the hero section (usually keep default 'Gutters')", default_factory=lambda: HeroImageSettings())
    linked_resource_type: Literal["Spree::Taxon", "Spree::Product"] | None = Field(
        description="Type of resource this hero section links to (e.g., 'Spree::Taxon' for categories, 'Spree::Product' for products). Leave null if no specific resource link",
        default=None,
        examples=["Spree::Taxon", "Spree::Product", None],
    )
    linked_resource_id: int | None = Field(
        description="ID of the linked resource (taxon ID, product ID, etc.). Must match linked_resource_type. Leave null if no specific resource link",
        default=None,
        examples=[1, 2, 3, None],
    )
    keywords: list[str] = Field(
        description=(
            "List of relevant keywords that describe the visible subject of this hero section. "
            "Must include at least one keyword that describes something visible/tangible "
            "(e.g., 'dogs', 'cats', 'birds', 'toys', 'food', 'beds', 'collars', 'bowls')"
        ),
        default_factory=list,
        examples=[
            ["dogs", "collars", "toys"],
            ["cats", "beds", "bowls"],
            ["birds", "cages", "perches"],
            ["puppies", "food", "treats"],
            ["kittens", "toys", "beds"],
        ],
    )


class RichTextSettings(BaseModel):
    gutters: str = Field(description="Gutter setting for the section layout", default="Gutters", examples=["Gutters", "No Gutters"])
    text_alignment: str = Field(description="Text alignment for the content", default="Left", examples=["Left", "Center", "Right"])
    padding: str = Field(description="Padding setting for the section", default="Standard", examples=["Standard", "Large", "Small"])


class RichTextSectionForGeneration(BaseModel):
    name: str = Field(
        description="Create a descriptive name for this rich text section that reflects its purpose and content",
        examples=["Welcome Section", "About Us Content", "Feature Highlights", "Product Information"],
    )
    content: str = Field(description="Generate engaging rich text content with proper HTML formatting")
    settings: RichTextSettings = Field(description="Layout settings for the rich text section", default_factory=lambda: RichTextSettings())
    linked_resource_type: str | None = Field(
        description="Type of resource this section links to (e.g., 'Spree::Taxon' for categories, 'Spree::Product' for products). Leave null if no specific resource link",
        default=None,
        examples=["Spree::Taxon", "Spree::Product", None],
    )
    linked_resource_id: int | None = Field(
        description="ID of the linked resource (taxon ID, product ID, etc.). Must match linked_resource_type. Leave null if no specific resource link",
        default=None,
        examples=[1, 2, 3, None],
    )


class RichTextSection(BaseModel):
    id: int = Field(description="Unique identifier for the section", default=-1)  # noqa: A003, RUF100
    name: str = Field(description="Section name")
    content: str = Field(
        description=(
            "Generate rich text HTML content with proper structure (h1, h2, h3, p, ul, li, strong, em). "
            "Content should be engaging, professional, and relevant to the store theme. "
            "Include 2-3 paragraphs of well-structured content focused on benefits and features."
        ),
        examples=[
            "<h2>Welcome to Our Store</h2><p>Discover quality products that enhance your lifestyle. "
            "Our carefully curated selection offers the best in comfort, style, and functionality.</p><p>"
            "From premium materials to innovative designs, we ensure every item meets our high standards. "
            "Shop with confidence knowing you're getting exceptional value and outstanding service.</p>",
            "<h2>Quality You Can Trust</h2><p>We're committed to providing products that exceed your expectations. "
            "Our team carefully selects each item based on quality, durability, and customer satisfaction.</p><p>"
            "Experience the difference that attention to detail makes. Whether you're looking for everyday essentials "
            "or special occasion items, we have everything you need.</p>",
        ],
    )
    settings: RichTextSettings = Field(description="Structured settings for the rich text section")
    fit: SpreeFitType = Field(description="How the section fits in the layout", default="Container")
    destination: str | None = Field(description="Link destination", default=None)
    type: str = SpreeCmsSections.RICH_TEXT  # noqa: A003, RUF100
    position: int = Field(description="Position order of the section", default=-1)
    linked_resource_type: str | None = Field(description="Type of linked resource (e.g., Spree::Taxon)")
    linked_resource_id: int | None = Field(description="ID of linked resource")
    cms_page_id: int = Field(description="ID of the CMS page this section belongs to", default=-1)
    created_at: str | None = Field(description="Creation timestamp", default=None)
    updated_at: str | None = Field(description="Last update timestamp", default=None)


class FeaturedArticleContent(BaseModel):
    title: str = Field(
        description="Create a compelling, attention-grabbing headline (3-6 words) that clearly communicates the main value proposition",
        examples=["Premium Pet Care", "Quality You Can Trust", "Expert Pet Solutions"],
    )
    subtitle: str = Field(
        description="Write a concise subtitle (1 sentence) that expands on the headline",
        examples=[
            "Discover quality pet supplies that bring joy to your pets",
            "Shop the latest trends and find perfect items for your lifestyle",
            "Experience exceptional service and products that exceed expectations",
        ],
    )
    button_text: str = Field(
        description="Create a clear, action-oriented button text (2-3 words)",
        examples=["Shop Now", "Learn More", "Get Started", "Explore"],
    )
    rte_content: str = Field(
        description=("Generate concise rich text HTML content (1-2 paragraphs) with proper structure (h1, h2, p, strong, em). Content should be engaging and relevant to the store theme."),
        examples=[
            "<h1>Welcome to Our Store</h1><p>Discover quality products that enhance your lifestyle. "
            "Our carefully curated selection offers the best in comfort, style, and functionality.</p>",
            "<h1>Quality You Can Trust</h1><p>We're committed to providing products that exceed your expectations. Experience the difference that attention to detail makes.</p>",
        ],
    )


class FeaturedArticleSettings(BaseModel):
    gutters: Literal["Gutters", "No Gutters"] = Field(
        description=("Gutter setting for the section layout. Use 'Gutters' for standard spacing or 'No Gutters' for edge-to-edge layout"),
        default="No Gutters",
        examples=["Gutters", "No Gutters"],
    )


class FeaturedArticleSectionForGeneration(BaseModel):
    name: str = Field(
        description="Create a descriptive name for this featured article section that reflects its purpose and content",
        examples=["Featured Article", "Main Article", "Highlighted Content", "Featured Story"],
    )
    content: FeaturedArticleContent = Field(description=("Generate compelling featured article content with engaging headline, subtitle, call-to-action, and rich text content"))
    settings: FeaturedArticleSettings = Field(
        description=("Layout settings for the featured article section (usually keep default 'No Gutters')"), default_factory=lambda: FeaturedArticleSettings()
    )
    linked_resource_type: str | None = Field(
        description=("Type of resource this section links to (e.g., 'Spree::Taxon' for categories, 'Spree::Product' for products). Leave null if no specific resource link"),
        default=None,
        examples=["Spree::Taxon", "Spree::Product", None],
    )
    linked_resource_id: int | None = Field(
        description=("ID of the linked resource (taxon ID, product ID, etc.). Must match linked_resource_type. Leave null if no specific resource link"),
        default=None,
        examples=[1, 2, 3, None],
    )


class FeaturedArticleSection(BaseModel):
    id: int = Field(description="Unique identifier for the section", default=-1)  # noqa: A003, RUF100
    name: str = Field(description="Section name")
    content: FeaturedArticleContent = Field(description="Structured content for the featured article section")
    settings: FeaturedArticleSettings = Field(description="Structured settings for the featured article section")
    fit: SpreeFitType = Field(description="How the section fits in the layout", default="Screen")
    destination: str | None = Field(description="Link destination", default=None)
    type: str = SpreeCmsSections.FEATURED_ARTICLE  # noqa: A003, RUF100
    position: int = Field(description="Position order of the section", default=-1)
    linked_resource_type: str | None = Field(description="Type of linked resource (e.g., Spree::Taxon)")
    linked_resource_id: int | None = Field(description="ID of linked resource")
    cms_page_id: int = Field(description="ID of the CMS page this section belongs to", default=-1)
    created_at: str | None = Field(description="Creation timestamp", default=None)
    updated_at: str | None = Field(description="Last update timestamp", default=None)


class ProductCarouselSectionForGeneration(BaseModel):
    name: str = Field(description="Descriptive name for the carousel section")
    linked_resource_type: SpreeLinkType | None = Field(description="Type of linked resource (Spree::Taxon or Spree::Product)")
    linked_resource_id: int | None = Field(description="ID of the linked taxon or product")


class ProductCarouselSection(BaseModel):
    id: int = Field(description="Unique identifier for the section", default=-1)  # noqa: A003, RUF100
    name: str = Field(description="Section name")
    content: str | None = Field(description="JSON content for the section (usually null for carousels)", default=None)
    settings: str | None = Field(description="JSON settings for the section (usually null for carousels)", default=None)
    fit: SpreeFitType = Field(description="How the section fits in the layout", default="Container")
    destination: str | None = Field(description="Link destination", default=None)
    type: str = SpreeCmsSections.PRODUCT_CAROUSEL  # noqa: A003, RUF100
    position: int = Field(description="Position order of the section", default=-1)
    linked_resource_type: SpreeLinkType | None = Field(description="Type of linked resource (Spree::Taxon or Spree::Product)")
    linked_resource_id: int | None = Field(description="ID of linked resource")
    cms_page_id: int = Field(description="ID of the CMS page this section belongs to", default=-1)
    created_at: str | None = Field(description="Creation timestamp", default=None)
    updated_at: str | None = Field(description="Last update timestamp", default=None)


class ImageGalleryContent(BaseModel):
    link_type_one: SpreeLinkType = Field(description="Type of first link (Spree::Taxon or Spree::Product)")
    link_type_two: SpreeLinkType = Field(description="Type of second link (Spree::Taxon or Spree::Product)")
    link_type_three: SpreeLinkType = Field(description="Type of third link (Spree::Taxon or Spree::Product)")
    title_one: str = Field(description="Title for first gallery item")
    title_two: str = Field(description="Title for second gallery item")
    title_three: str = Field(description="Title for third gallery item")
    link_one: int = Field(description="ID of first link (taxon ID or product ID)")
    link_two: int = Field(description="ID of second link (taxon ID or product ID)")
    link_three: int = Field(description="ID of third link (taxon ID or product ID)")
    keywords_one: str = Field(description="Comma-separated keywords for first image search")
    keywords_two: str = Field(description="Comma-separated keywords for second image search")
    keywords_three: str = Field(description="Comma-separated keywords for third image search")


class ImageGallerySettings(BaseModel):
    layout_style: str = Field(description="Layout style for the gallery", default="Default", examples=["Default", "Grid", "Masonry"])
    display_labels: str = Field(description="Whether to display labels", default="Show", examples=["Show", "Hide"])


class ImageGallerySectionForGeneration(BaseModel):
    name: str = Field(
        description="Create a descriptive name for this image gallery section that reflects its purpose and content",
        examples=["Category Gallery", "Product Showcase", "Featured Categories", "Browse Collections"],
    )
    content: ImageGalleryContent = Field(
        description=(
            "Generate gallery content with three images and their links. Choose between taxons (categories) "
            "and products based on the gallery purpose. Use taxons for category browsing, use products for "
            "specific product showcases. Provide only numeric IDs for links."
        )
    )
    settings: ImageGallerySettings = Field(description="Layout settings for the image gallery section", default_factory=lambda: ImageGallerySettings())


class ImageGallerySection(BaseModel):
    id: int = Field(description="Unique identifier for the section", default=-1)  # noqa: A003, RUF100
    name: str = Field(description="Section name")
    content: str | None = Field(description="JSON content for the section")
    settings: str | None = Field(description="JSON settings for the section")
    fit: SpreeFitType = Field(description="How the section fits in the layout", default="Container")
    destination: str | None = Field(description="Link destination", default=None)
    type: str = SpreeCmsSections.IMAGE_GALLERY  # noqa: A003, RUF100
    position: int = Field(description="Position order of the section", default=-1)
    linked_resource_type: SpreeLinkType | None = Field(description="Type of linked resource (Spree::Taxon or Spree::Product)")
    linked_resource_id: int | None = Field(description="ID of linked resource")
    cms_page_id: int = Field(description="ID of the CMS page this section belongs to", default=-1)
    created_at: str | None = Field(description="Creation timestamp", default=None)
    updated_at: str | None = Field(description="Last update timestamp", default=None)
    image_urls: dict[str, str] = Field(description="Image URLs for each gallery link", default_factory=dict)


class SideBySideImagesContent(BaseModel):
    link_type_one: SpreeLinkType = Field(description="Type of first link (Spree::Taxon or Spree::Product)")
    link_type_two: SpreeLinkType = Field(description="Type of second link (Spree::Taxon or Spree::Product)")
    title_one: str = Field(description="Title for first side by side item")
    title_two: str = Field(description="Title for second side by side item")
    subtitle_one: str = Field(description="Subtitle for first side by side item")
    subtitle_two: str = Field(description="Subtitle for second side by side item")
    link_one: int = Field(description="ID of first link (taxon ID or product ID)")
    link_two: int = Field(description="ID of second link (taxon ID or product ID)")
    keywords_one: str = Field(description="Comma-separated keywords for first image search")
    keywords_two: str = Field(description="Comma-separated keywords for second image search")


class SideBySideImagesSettings(BaseModel):
    gutters: str = Field(description="Gutter setting for the section layout", default="Gutters", examples=["Gutters", "No Gutters"])


class SideBySideImagesSectionForGeneration(BaseModel):
    name: str = Field(
        description="Create a descriptive name for this side by side images section that reflects its purpose and content",
        examples=["Side By Side Comparison", "Product Showcase", "Category Comparison", "Feature Comparison"],
    )
    content: SideBySideImagesContent = Field(
        description="Generate side by side content with two items, each having titles, subtitles, link IDs, and keywords for image search. Provide only numeric IDs for links."
    )
    settings: SideBySideImagesSettings = Field(description="Layout settings for the side by side images section", default_factory=lambda: SideBySideImagesSettings())


class SideBySideImagesSection(BaseModel):
    id: int = Field(description="Unique identifier for the section", default=-1)  # noqa: A003, RUF100
    name: str = Field(description="Section name")
    content: str | None = Field(description="JSON content for the section")
    settings: str | None = Field(description="JSON settings for the section")
    fit: SpreeFitType = Field(description="How the section fits in the layout", default="Container")
    destination: str | None = Field(description="Link destination", default=None)
    type: str = SpreeCmsSections.SIDE_BY_SIDE_IMAGES  # noqa: A003, RUF100
    position: int = Field(description="Position order of the section", default=-1)
    linked_resource_type: SpreeLinkType | None = Field(description="Type of linked resource (Spree::Taxon or Spree::Product)")
    linked_resource_id: int | None = Field(description="ID of linked resource")
    cms_page_id: int = Field(description="ID of the CMS page this section belongs to", default=-1)
    created_at: str | None = Field(description="Creation timestamp", default=None)
    updated_at: str | None = Field(description="Last update timestamp", default=None)
    image_urls: dict[str, str] = Field(description="Image URLs for each side by side link", default_factory=dict)
