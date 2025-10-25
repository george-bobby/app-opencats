import json
from datetime import datetime
from io import BytesIO
from pathlib import Path

from PIL import Image

from apps.spree.core.images import DirectImageSeeder
from apps.spree.libs.cms.models import (
    SideBySideImagesSection,
    SideBySideImagesSectionForGeneration,
)
from apps.spree.utils.ai import instructor_client
from apps.spree.utils.constants import PAGES_FILE
from apps.spree.utils.database import db_client
from apps.spree.utils.pexels import PexelsAPI
from common.logger import Logger


logger = Logger()


async def crop_image_to_ratio(image_data: bytes, target_ratio: float = 1.0) -> bytes:
    """Crop an image to a specific aspect ratio."""
    try:
        # Open image from bytes
        image = Image.open(BytesIO(image_data))

        # Convert to RGB if not already
        if image.mode != "RGB":
            image = image.convert("RGB")

        # Calculate target dimensions for the ratio
        original_width, original_height = image.size

        # Calculate new dimensions maintaining aspect ratio
        if original_width / original_height > target_ratio:
            # Image is too wide, crop width
            new_width = int(original_height * target_ratio)
            new_height = original_height
            left = (original_width - new_width) // 2
            top = 0
            right = left + new_width
            bottom = original_height
        else:
            # Image is too tall, crop height
            new_width = original_width
            new_height = int(original_width / target_ratio)
            left = 0
            top = (original_height - new_height) // 2
            right = original_width
            bottom = top + new_height

        # Crop image to center area with target aspect ratio
        cropped_image = image.crop((left, top, right, bottom))

        # Save to bytes
        output_buffer = BytesIO()
        cropped_image.save(output_buffer, format="JPEG", quality=95)
        output_buffer.seek(0)

        result_data = output_buffer.getvalue()
        return result_data

    except Exception as e:
        logger.error(f"Failed to crop image to ratio {target_ratio}: {e}")
        # Return original image data if processing fails
        return image_data


async def generate_side_by_side_images_section(context: dict) -> SideBySideImagesSection:
    """Generate a Side By Side Images section with keywords and image URLs for each link."""

    # Get available taxons and products from context
    available_taxons = context.get("taxons", [])
    available_products = context.get("sample_products", [])

    # Generate section content using LLM
    context = context.copy()
    del context["sample_products"]

    taxons_summary = ", ".join([f"{t['name']} (ID: {t['id']})" for t in available_taxons[:10]])
    products_summary = ", ".join([f"{p['name']} (ID: {p['id']})" for p in available_products[:10]])

    system_prompt = f"""Generate a Side By Side Images section for {context["store_name"]}, a {context["store_theme"]} store.
    Generate a side by side images section for the "{context["page_title"]}" page.

    AVAILABLE TAXONS FOR LINKING:
    {taxons_summary}

    AVAILABLE PRODUCTS FOR LINKING:
    {products_summary}

    SIDE BY SIDE IMAGES SECTION REQUIREMENTS:
    - name: Create a descriptive name that reflects the section's purpose
    - content: Generate content for 2 side-by-side items with titles, subtitles, links, and keywords
    - settings: Use default gutters setting
    - Each item needs:
      * title: Descriptive title for the item (1-3 words)
      * subtitle: Short, engaging subtitle (3-6 words max) that complements the title
      * link: ONLY provide the numeric ID (e.g., 8 for taxon ID 8, 7 for product ID 7) - NO URL PREFIXES
      * link_type: "Spree::Taxon" for category links or "Spree::Product" for product links
      * keywords: 3-5 relevant keywords for image search (comma-separated) - THIS IS REQUIRED

    CONTENT REQUIREMENTS:
    - Create 2 side-by-side items with engaging titles and short subtitles
    - Choose appropriate link types (taxon or product) based on the page context
    - Generate relevant keywords for each item that would help find good images
    - Keywords should be descriptive and specific (e.g., "dog toys, pet accessories, colorful balls")
    - Make content specific to the {context["store_theme"]} business
    - Keep subtitles concise and impactful (3-6 words maximum)
    - CRITICAL: For links, provide ONLY the numeric ID (e.g., 8, 7, 10) - NO "taxons/" or "products/" prefixes

    IMPORTANT: You MUST generate keywords_one and keywords_two for each item.
    These keywords will be used to search for appropriate images.

    Make the content specific to the {context["store_theme"]} business with engaging copy that would attract customers."""

    user_prompt = f"""Create a compelling side by side images section for {context["store_name"]}.

    Make it specific to our {context["store_theme"]} business with engaging copy that would attract customers.

    Choose appropriate taxons or products from these available options:
    Available taxons: {taxons_summary}
    Available products: {products_summary}

    Generate a complete side by side section with 2 items, each having titles, subtitles, links (numeric ID only), and keywords for image search.
    
    CRITICAL: For links, provide ONLY the numeric ID (e.g., 8 for taxon, 7 for product) - NO URL prefixes like "taxons/" or "products/"."""

    response = await instructor_client.chat.completions.create(
        model="claude-3-7-sonnet-latest",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        response_model=SideBySideImagesSectionForGeneration,
        max_tokens=2048,
    )

    # Search for images using Pexels based on keywords for each link
    image_urls = {}
    if response and response.content:
        try:
            async with PexelsAPI() as pexels:
                # Extract keywords from each link and search for images
                content_data = response.content

                for link_num in range(1, 3):  # Side by side has 2 images
                    keyword_mapping = {1: "keywords_one", 2: "keywords_two"}
                    keywords_key = keyword_mapping[link_num]

                    if hasattr(content_data, keywords_key):
                        keywords = getattr(content_data, keywords_key)
                        if keywords:
                            try:
                                # Search for image using combined keywords
                                query = ", ".join(keywords.split(", "))
                                photos = await pexels.get_random_photos(query, count=1, orientation="landscape")
                                if photos:
                                    image_url = await pexels.download_photo_url(photos[0], size="large")
                                    image_urls[f"image_url_{link_num}"] = image_url
                            except Exception as e:
                                logger.error(f"Pexels search error for link {link_num}: {e}")
        except Exception as e:
            logger.error(f"Pexels API error: {e}")

    title_one = response.content.title_one
    subtitle_one = response.content.subtitle_one
    title_two = response.content.title_two
    subtitle_two = response.content.subtitle_two

    link_one_id = response.content.link_one
    link_two_id = response.content.link_two

    # Store the numeric IDs directly without prefixes
    content = response.content.model_dump()
    content["link_one"] = link_one_id
    content["link_two"] = link_two_id

    content["title_one"] = subtitle_one
    content["title_two"] = subtitle_two
    content["subtitle_one"] = title_one.upper()
    content["subtitle_two"] = title_two.upper()

    # Convert content to JSON string for storage
    content_json = json.dumps(content) if content else None
    settings_json = response.settings.model_dump_json() if response.settings else None

    section = SideBySideImagesSection(
        linked_resource_type=None,
        linked_resource_id=None,
        name=response.name,
        content=content_json,
        settings=settings_json,
        image_urls=image_urls,  # Store image URLs for each link
    )
    return section


async def seed_side_by_side_sections() -> None:
    """Create image assets for side by side sections using the correct Spree asset structure."""

    # Get all side by side sections
    side_by_side_sections = await db_client.fetch(
        """
        SELECT id, name, content, cms_page_id
        FROM spree_cms_sections
        WHERE type = 'Spree::Cms::Sections::SideBySideImages'
        ORDER BY id
        """
    )

    if not side_by_side_sections:
        logger.warning("No side by side sections found")
        return

    # Load pages data to get image URLs
    if not PAGES_FILE.exists():
        logger.warning("Pages file not found, cannot seed side by side images")
        return

    with Path.open(PAGES_FILE, encoding="utf-8") as f:
        pages_data = json.load(f)

    # Create a mapping of page IDs to their original JSON IDs
    page_id_mapping = {}
    for page in pages_data.get("pages", []):
        json_page_id = page.get("id")
        if json_page_id:
            # Find the corresponding database page ID
            db_page = await db_client.fetchrow("SELECT id FROM spree_cms_pages WHERE id = $1 OR slug = $2", json_page_id, page.get("slug", ""))
            if db_page:
                page_id_mapping[db_page["id"]] = json_page_id

    # Create a mapping of section IDs to image URLs from the JSON data
    section_image_mapping = {}
    for page in pages_data.get("pages", []):
        json_page_id = page.get("id")
        if json_page_id in page_id_mapping.values():
            # Find the database page ID for this JSON page
            db_page_id = None
            for db_id, json_id in page_id_mapping.items():
                if json_id == json_page_id:
                    db_page_id = db_id
                    break

            if db_page_id:
                for section in page.get("sections", []):
                    if section.get("type") == "Spree::Cms::Sections::SideBySideImages" and section.get("image_urls"):
                        # Map by page_id and position since section IDs change
                        key = (db_page_id, section.get("position", 1))
                        section_image_mapping[key] = section["image_urls"]

    current_time = datetime.utcnow()
    created_assets = 0

    # Use DirectImageSeeder to store images
    async with DirectImageSeeder() as seeder:
        for section in side_by_side_sections:
            try:
                section_id = section["id"]
                section_name = section["name"]
                cms_page_id = section["cms_page_id"]

                # Get the position of this section
                section_position = await db_client.fetchval("SELECT position FROM spree_cms_sections WHERE id = $1", section_id)

                # Get image URLs from the mapping using page_id and position
                image_urls = section_image_mapping.get((cms_page_id, section_position))
                if not image_urls:
                    logger.warning(f"No image URLs found for side by side section {section_id}: {section_name} (page_id: {cms_page_id}, position: {section_position})")
                    continue

                # Process each image URL for this side by side section
                for link_num in range(1, 3):  # Side by side has 2 images
                    image_url_key = f"image_url_{link_num}"
                    image_url = image_urls.get(image_url_key)

                    if not image_url:
                        logger.warning(f"No image URL found for side by side link {link_num} in section {section_id}")
                        continue

                    # Map link number to the correct asset type
                    asset_type_map = {1: "Spree::CmsSectionImageOne", 2: "Spree::CmsSectionImageTwo"}
                    image_type = asset_type_map[link_num]

                    # Create asset record
                    asset_id = await db_client.fetchval(
                        """
                        INSERT INTO spree_assets
                        (viewable_type, viewable_id, type, position, created_at, updated_at)
                        VALUES ($1, $2, $3, $4, $5, $6)
                        RETURNING id
                        """,
                        "Spree::CmsSection",
                        section_id,
                        image_type,  # Use correct asset type for each position
                        1,  # Position is always 1 for each type
                        current_time,
                        current_time,
                    )

                    # Generate unique storage key
                    storage_key = seeder._generate_storage_key()

                    try:
                        # Download image to memory first
                        if not seeder.session:
                            raise RuntimeError("Session not initialized")

                        async with seeder.session.get(image_url) as response:
                            response.raise_for_status()
                            image_data = await response.read()

                        # Calculate checksum and file size for processed image
                        import base64
                        import hashlib

                        md5_hash = hashlib.md5()
                        md5_hash.update(image_data)
                        checksum = base64.b64encode(md5_hash.digest()).decode("ascii")
                        file_size = len(image_data)

                        # Get filename from URL
                        filename = image_url.split("/")[-1].split("?")[0]
                        if "." not in filename:
                            filename = f"{storage_key}.jpg"

                        # Write processed image to storage
                        storage_file_path = seeder._get_storage_path_for_key(storage_key)
                        Path(storage_file_path).parent.mkdir(parents=True, exist_ok=True)

                        import aiofiles

                        async with aiofiles.open(storage_file_path, "wb") as f:
                            await f.write(image_data)

                        # Insert blob record
                        blob_id = await seeder._insert_blob_record(
                            storage_key=storage_key, filename=f"sidebyside_{section_id}_{link_num}_{filename}", file_size=file_size, checksum=checksum, content_type="image/jpeg"
                        )

                        # Create attachment
                        await db_client.execute(
                            """
                            INSERT INTO active_storage_attachments
                            (name, record_type, record_id, blob_id, created_at)
                            VALUES ($1, $2, $3, $4, $5)
                            """,
                            "attachment",  # Important: Spree expects "attachment" not "image"
                            "Spree::Asset",
                            asset_id,
                            blob_id,
                            current_time,
                        )

                        created_assets += 1

                    except Exception as e:
                        logger.error(f"Failed to download or process side by side image {image_url}: {e}")

            except Exception as e:
                logger.error(f"Failed to process side by side section {section['name']}: {e}")
                continue
