import base64
import hashlib
import json
from datetime import datetime
from io import BytesIO
from pathlib import Path

import aiofiles
from PIL import Image

from apps.spree.core.images import DirectImageSeeder
from apps.spree.libs.cms.models import HeroImageSection, HeroImageSectionForGeneration
from apps.spree.utils.ai import instructor_client
from apps.spree.utils.constants import PAGES_FILE
from apps.spree.utils.database import db_client
from apps.spree.utils.pexels import PexelsAPI
from common.logger import Logger


logger = Logger()


async def add_white_overlay_to_image(image_data: bytes) -> bytes:
    """Add a 50% white overlay to an image and crop to 12:5 aspect ratio."""
    try:
        # Open image from bytes
        image = Image.open(BytesIO(image_data))

        # Convert to RGBA if not already
        if image.mode != "RGBA":
            image = image.convert("RGBA")

        # Calculate target dimensions for 12:5 aspect ratio
        original_width, original_height = image.size
        target_ratio = 12 / 5  # 12:5 aspect ratio

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

        # Crop image to center area with 12:5 aspect ratio
        cropped_image = image.crop((left, top, right, bottom))

        # Create a gradient overlay from left to right (0% to 65% opacity)
        width, height = cropped_image.size
        gradient_overlay = Image.new("RGBA", (width, height), (0, 0, 0, 0))

        # Create gradient pixels
        for x in range(width):
            # Calculate opacity from 0 at left to max at 65% of width, then stay at max
            peak_position = int(width * 0.65)
            opacity = int((x / peak_position) * 200) if x <= peak_position else 200

            # Create a white pixel with calculated opacity
            pixel_color = (255, 255, 255, opacity)

            # Fill the entire column with this color
            for y in range(height):
                gradient_overlay.putpixel((x, y), pixel_color)

        # Composite the gradient overlay onto the cropped image
        result = Image.alpha_composite(cropped_image, gradient_overlay)

        # Convert back to RGB for JPEG storage
        result = result.convert("RGB")

        # Save to bytes
        output_buffer = BytesIO()
        result.save(output_buffer, format="JPEG", quality=95)
        output_buffer.seek(0)

        return output_buffer.getvalue()

    except Exception as e:
        logger.error(f"Failed to add white overlay to image: {e}")
        # Return original image data if processing fails
        return image_data


async def generate_hero_image_section(context: dict) -> HeroImageSection:
    """Generate a Hero Image section using structured models."""

    context = context.copy()
    del context["sample_products"]

    # Include more taxons and prioritize health-related ones
    all_taxons = context["taxons"]

    # Find health-related taxons first
    health_taxons = [t for t in all_taxons if "health" in t["name"].lower() or "wellness" in t["name"].lower()]

    # Get other relevant taxons (first 15 to ensure we include Health & Wellness)
    other_taxons = [t for t in all_taxons[:15] if t not in health_taxons]

    # Combine health taxons first, then others
    prioritized_taxons = health_taxons + other_taxons

    taxons_summary = ", ".join([f"{t['name']} (ID: {t['id']})" for t in prioritized_taxons])

    system_prompt = f"""Generate a Hero Image section for {context["store_name"]}, a {context["store_theme"]} store.
    Generate a hero image section for the "{context["page_title"]}" page.

    AVAILABLE TAXONS FOR LINKING:
    {taxons_summary}

    HERO IMAGE SECTION REQUIREMENTS:
    - name: Create a descriptive name that reflects the section's purpose
    - settings: Use default gutters setting (usually "Gutters")
    - linked_resource_type: "Spree::Taxon" if linking to category, "Spree::Product" if linking to product, or null
    - linked_resource_id: Valid taxon ID or product ID from list above, or null

    CONTENT REQUIREMENTS:
    - title: Create a compelling, attention-grabbing headline (5-8 words)
    - subtitle: Write an engaging subtitle (1-2 sentences) that expands on the headline
    - button_text: Create a clear, action-oriented button text (2-4 words)

    TAXON SELECTION GUIDELINES:
    - Always choose the most specific and relevant taxon for the content

    Make the content specific to the {context["store_theme"]} business with engaging copy that would attract customers."""

    user_prompt = f"""Create a compelling hero image section for {context["store_name"]}.

    Make it specific to our {context["store_theme"]} business with engaging copy that would attract customers.

    If linking to a category, use one of these taxons:
    {taxons_summary}

    Generate a complete hero section with compelling content and appropriate settings."""

    response = await instructor_client.chat.completions.create(
        model="claude-3-7-sonnet-latest",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        response_model=HeroImageSectionForGeneration,
        max_tokens=2048,
    )

    # Search for image using Pexels based on keywords
    if response and response.keywords:
        try:
            async with PexelsAPI() as pexels:
                query = ", ".join(response.keywords)
                photos = await pexels.get_random_photos(query, count=1, orientation="landscape")
                if photos:
                    image_url = await pexels.download_photo_url(photos[0], size="large")
        except Exception as e:
            logger.error(f"Pexels search error: {e}")

    if response:
        return HeroImageSection(
            linked_resource_type=response.linked_resource_type,
            linked_resource_id=response.linked_resource_id,
            name=response.name,
            content=response.content,
            settings=response.settings,
            image_url=image_url,
            keywords=response.keywords,
        )
    else:
        raise ValueError("Failed to generate hero image section")


async def seed_hero_image_assets() -> None:
    """Create proper image assets for hero sections using the correct Spree asset structure."""

    # Get all hero sections
    hero_sections = await db_client.fetch(
        """
        SELECT id, name, content, cms_page_id
        FROM spree_cms_sections 
        WHERE type = 'Spree::Cms::Sections::HeroImage'
        ORDER BY id
        """
    )

    if not hero_sections:
        logger.warning("No hero sections found")
        return

    # Load pages data to get image URLs
    if not PAGES_FILE.exists():
        logger.warning("Pages file not found, cannot seed hero images")
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
    # We need to map by page_id and position since the section IDs change
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
                    if section.get("type") == "Spree::Cms::Sections::HeroImage" and section.get("image_url"):
                        # Map by page_id and position since section IDs change
                        key = (db_page_id, section.get("position", 1))
                        section_image_mapping[key] = section["image_url"]

    current_time = datetime.utcnow()
    created_assets = 0

    # Use DirectImageSeeder to store images
    async with DirectImageSeeder() as seeder:
        for section in hero_sections:
            try:
                section_id = section["id"]
                section_name = section["name"]
                cms_page_id = section["cms_page_id"]

                # Check if asset already exists for this hero section
                existing_asset = await db_client.fetchval(
                    """
                    SELECT id FROM spree_assets 
                    WHERE viewable_type = 'Spree::CmsSection' 
                    AND viewable_id = $1 
                    AND type = 'Spree::CmsSectionImageOne'
                    """,
                    section_id,
                )

                if existing_asset:
                    logger.info(f"Hero image asset already exists for section {section_id}: {section_name}")
                    continue

                # Get the position of this section
                section_position = await db_client.fetchval("SELECT position FROM spree_cms_sections WHERE id = $1", section_id)

                # Get image URL from the mapping using page_id and position
                image_url = section_image_mapping.get((cms_page_id, section_position))
                if not image_url:
                    logger.warning(f"No image URL found for hero section {section_id}: {section_name} (page_id: {cms_page_id}, position: {section_position})")
                    continue

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
                    "Spree::CmsSectionImageOne",  # Hero sections use ImageOne type
                    1,  # Position is always 1 for hero sections
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

                    # Add white overlay to the image
                    processed_image_data = await add_white_overlay_to_image(image_data)

                    # Calculate checksum and file size for processed image
                    md5_hash = hashlib.md5()
                    md5_hash.update(processed_image_data)
                    checksum = base64.b64encode(md5_hash.digest()).decode("ascii")
                    file_size = len(processed_image_data)

                    # Get filename from URL
                    filename = image_url.split("/")[-1].split("?")[0]
                    if "." not in filename:
                        filename = f"{storage_key}.jpg"

                    # Write processed image to storage
                    storage_file_path = seeder._get_storage_path_for_key(storage_key)
                    Path(storage_file_path).parent.mkdir(parents=True, exist_ok=True)

                    async with aiofiles.open(storage_file_path, "wb") as f:
                        await f.write(processed_image_data)

                    # Insert blob record
                    blob_id = await seeder._insert_blob_record(
                        storage_key=storage_key, filename=f"hero_{section_id}_{filename}", file_size=file_size, checksum=checksum, content_type="image/jpeg"
                    )

                    # Create attachment - note the name is "attachment" not "image"
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
                    logger.error(f"Failed to download or process hero image {image_url}: {e}")

            except Exception as e:
                logger.error(f"Failed to process hero section {section['name']}: {e}")
                continue
