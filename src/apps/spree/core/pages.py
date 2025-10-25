import asyncio
import json
from datetime import datetime
from pathlib import Path

from faker import Faker

from apps.spree.config.settings import settings
from apps.spree.libs.cms.carousel import seed_carousel_sections
from apps.spree.libs.cms.content import generate_page_content, load_context_data
from apps.spree.libs.cms.gallery import seed_gallery_sections
from apps.spree.libs.cms.hero import seed_hero_image_assets
from apps.spree.libs.cms.models import SpreeCmsSections
from apps.spree.libs.cms.outline import PageTemplate, generate_outline
from apps.spree.libs.cms.side_by_side import seed_side_by_side_sections
from apps.spree.utils.constants import PAGES_FILE
from apps.spree.utils.database import db_client
from common.logger import Logger


fake = Faker()
logger = Logger()


async def generate_pages(number_of_pages: int) -> dict | None:
    """Generate realistic CMS pages using AI with context from existing store data."""

    logger.info(f"Generating {number_of_pages} CMS pages using AI...")

    try:
        context = await load_context_data()

        # Step 1: Generate list of pages to create
        page_templates = await generate_outline(context, number_of_pages)

        # Print formatted page templates
        print("Generated Page Templates:")
        print("=" * 50)
        for i, template in enumerate(page_templates, 1):
            print(f"\n{i}. {template.title}")
            print(f"   Type: {template.type}")
            print(f"   Slug: {template.slug}")
            print(f"   Priority: {template.priority}")
            print(f"   Focus: {template.focus}")
            if template.sections_needed:
                print(f"   Sections: {', '.join(template.sections_needed)}")
            print("-" * 30)

        # Step 2: Generate content for all pages with concurrency control
        logger.info(f"Generating content for {len(page_templates)} pages with max {settings.MAX_CONCURRENT_GENERATION_REQUESTS} concurrent...")

        # Create semaphore to limit concurrent generation
        semaphore = asyncio.Semaphore(settings.MAX_CONCURRENT_GENERATION_REQUESTS)

        async def generate_with_semaphore(context: dict, page_template: PageTemplate, page_id: int):
            """Generate page content with semaphore limiting."""
            async with semaphore:
                return await generate_page_content(context, page_template, page_id)

        # Create tasks for all pages
        content_tasks = [generate_with_semaphore(context, page_template, page_id) for page_id, page_template in enumerate(page_templates, 1)]
        generated_pages = await asyncio.gather(*content_tasks, return_exceptions=True)

        if generated_pages:
            pages_dict = {"pages": [page.model_dump() for page in generated_pages]}  # type: ignore

            # Ensure the generated directory exists
            PAGES_FILE.parent.mkdir(parents=True, exist_ok=True)

            # Save to JSON file
            with Path.open(PAGES_FILE, "w", encoding="utf-8") as f:
                json.dump(pages_dict, f, indent=2, ensure_ascii=False)

            logger.succeed(f"Successfully generated and saved {len(generated_pages)} pages to {PAGES_FILE}")

            return pages_dict
        else:
            logger.error("Failed to generate any pages")
            raise ValueError("Failed to generate pages")

    except Exception as e:
        logger.error(f"Error generating pages: {e}")
        raise


async def seed_pages():
    """Insert CMS pages and sections into the database."""

    logger.start("Inserting CMS pages and sections into database...")

    try:
        # Load pages from JSON file
        if not PAGES_FILE.exists():
            logger.error(f"Pages file not found at {PAGES_FILE}. Run generate command first.")
            raise FileNotFoundError("Pages file not found")

        with Path.open(PAGES_FILE, encoding="utf-8") as f:
            data = json.load(f)

        pages = data.get("pages", [])
        logger.info(f"Loaded {len(pages)} pages from {PAGES_FILE}")

        current_time = datetime.now()
        store_id = 1  # Default store ID

        # Insert pages first
        inserted_pages = 0
        skipped_pages = 0
        page_id_mapping = {}  # Map generated page IDs to actual database IDs

        for page in pages:
            try:
                # Use specific ID from JSON data
                page_id = page.get("id")
                if not page_id:
                    logger.warning(f"No ID found for page {page['title']}, skipping")
                    continue

                # Check if page already exists by ID or slug
                existing_page = await db_client.fetchrow(
                    "SELECT id FROM spree_cms_pages WHERE id = $1 OR (slug = $2 AND store_id = $3) AND deleted_at IS NULL", page_id, page["slug"], store_id
                )

                if existing_page:
                    logger.info(f"Page already exists: {page['title']} [ID: {page_id}] (/{page['slug']})")
                    page_id_mapping[page["id"]] = existing_page["id"]
                    skipped_pages += 1
                    continue

                # Insert page with specific ID
                page_record = await db_client.fetchrow(
                    """
                    INSERT INTO spree_cms_pages (id, title, meta_title, content, meta_description, 
                                               visible, slug, type, locale, store_id, 
                                               created_at, updated_at)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12)
                    RETURNING id
                    """,
                    page_id,  # Use specific ID from JSON
                    page["title"],
                    page.get("meta_title"),
                    page.get("content"),
                    page.get("meta_description"),
                    page.get("visible", True),
                    page["slug"],
                    page["type"],
                    page.get("locale", "en"),
                    store_id,
                    current_time,
                    current_time,
                )

                if page_record:
                    page_id_mapping[page["id"]] = page_record["id"]  # Should be the same as page_id
                    page_type = page["type"].split("::")[-1]  # Get just the class name
                    logger.info(f"Inserted {page_type}: {page['title']} [ID: {page_id}] - /{page['slug']}")
                    inserted_pages += 1

            except Exception as e:
                logger.error(f"Failed to insert page {page['title']}: {e}")
                continue

        logger.info(f"Pages: {inserted_pages} inserted, {skipped_pages} skipped")

        # Insert sections from embedded sections in each page
        inserted_sections = 0
        skipped_sections = 0

        for page in pages:
            page_sections = page.get("sections", [])
            if not page_sections:
                continue

            for section in page_sections:
                try:
                    # Get the actual page ID from our mapping
                    actual_page_id = page_id_mapping.get(page["id"])
                    if not actual_page_id:
                        logger.warning(f"Could not find page ID for section: {section['name']}")
                        continue

                    # Check if section already exists (by name and page_id)
                    existing_section = await db_client.fetchrow("SELECT id FROM spree_cms_sections WHERE name = $1 AND cms_page_id = $2", section["name"], actual_page_id)

                    if existing_section:
                        logger.info(f"Section already exists: {section['name']}")
                        skipped_sections += 1
                        continue

                    # Handle content field based on section type
                    content_value = section.get("content")
                    if isinstance(content_value, dict):
                        # For structured content (like HeroImage), convert to JSON string
                        content_value = json.dumps(content_value)
                    elif isinstance(content_value, str) and section["type"] == SpreeCmsSections.RICH_TEXT:
                        # For rich text content, wrap in rte_content structure
                        content_value = json.dumps({"rte_content": content_value})

                    # Handle settings field
                    settings_value = section.get("settings")
                    if isinstance(settings_value, dict):
                        settings_value = json.dumps(settings_value)

                    # Insert section
                    section_record = await db_client.fetchrow(
                        """
                        INSERT INTO spree_cms_sections (name, content, settings, fit, destination, 
                                                      type, position, linked_resource_type, 
                                                      linked_resource_id, cms_page_id, 
                                                      created_at, updated_at)
                        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12)
                        RETURNING id
                        """,
                        section["name"],
                        content_value,
                        settings_value,
                        section.get("fit"),
                        section.get("destination"),
                        section["type"],
                        section["position"],
                        section.get("linked_resource_type"),
                        section.get("linked_resource_id"),
                        actual_page_id,
                        current_time,
                        current_time,
                    )

                    if section_record:
                        section_type = section["type"].split("::")[-1]
                        logger.info(f"Inserted {section_type}: {section['name']} [ID: {section_record['id']}] (pos: {section['position']})")
                        inserted_sections += 1

                except Exception as e:
                    logger.error(f"Failed to insert section {section['name']}: {e}")
                    continue

        logger.info(f"Sections: {inserted_sections} inserted, {skipped_sections} skipped")

        # Reset PostgreSQL sequences to prevent primary key conflicts
        if inserted_pages > 0:
            logger.info("Resetting PostgreSQL sequences after manual ID insertions...")

            # Reset spree_cms_pages sequence
            await db_client.execute("SELECT setval('spree_cms_pages_id_seq', (SELECT COALESCE(MAX(id), 1) FROM spree_cms_pages))")

            # Reset spree_cms_sections sequence
            await db_client.execute("SELECT setval('spree_cms_sections_id_seq', (SELECT COALESCE(MAX(id), 1) FROM spree_cms_sections))")

            logger.info("PostgreSQL sequences reset successfully")

        logger.succeed(f"Successfully seeded {inserted_pages} pages and {inserted_sections} sections")

        # Log summary by type
        if inserted_pages > 0:
            page_type_counts = {}
            for page in pages:
                page_type = page["type"].split("::")[-1]
                page_type_counts[page_type] = page_type_counts.get(page_type, 0) + 1
            logger.info(f"Page type distribution: {dict(page_type_counts)}")

        if inserted_sections > 0:
            section_type_counts = {}
            for page in pages:
                for section in page.get("sections", []):
                    section_type = section["type"].split("::")[-1]
                    section_type_counts[section_type] = section_type_counts.get(section_type, 0) + 1
            logger.info(f"Section type distribution: {dict(section_type_counts)}")

        if inserted_pages > 0:
            logger.start("Seeding hero image assets...")
            await seed_hero_image_assets()
            logger.succeed("Successfully seeded hero image assets")

            logger.start("Seeding carousel sections...")
            await seed_carousel_sections()
            logger.succeed("Successfully seeded carousel sections")

            logger.start("Seeding gallery sections...")
            await seed_gallery_sections()
            logger.succeed("Successfully seeded gallery sections")

            logger.start("Seeding side-by-side sections...")
            await seed_side_by_side_sections()
            logger.succeed("Successfully seeded side-by-side sections")

    except Exception as e:
        logger.error(f"Error seeding pages and sections in database: {e}")
        raise
