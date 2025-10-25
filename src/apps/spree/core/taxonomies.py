"""Taxonomy generation and seeding for Spree."""

import json
from datetime import datetime
from pathlib import Path

from pydantic import BaseModel, Field

from apps.spree.config.settings import settings
from apps.spree.utils.ai import instructor_client
from apps.spree.utils.database import db_client
from common.logger import Logger


logger = Logger()

TAXONOMIES = [
    {
        "name": "Categories",
        "description": "Product categories",
    }
]
TAXONOMIES_FILE = settings.DATA_PATH / "generated" / "taxonomies.json"
TAXONS_FILE = settings.DATA_PATH / "generated" / "taxons.json"


class Taxonomy(BaseModel):
    """Individual taxonomy model."""

    id: int = Field(description="Unique identifier for the taxonomy")  # noqa: A003, RUF100
    name: str = Field(description="Clear, descriptive name for the taxonomy")
    description: str = Field(description="Brief explanation of what this taxonomy organizes")


class TaxonomyForGeneration(BaseModel):
    """Taxonomy model for AI generation (without ID)."""

    name: str = Field(description="Clear, descriptive name for the taxonomy")
    description: str = Field(description="Brief explanation of what this taxonomy organizes")


class TaxonomyResponse(BaseModel):
    """Response format for generated taxonomies."""

    taxonomies: list[TaxonomyForGeneration]


async def generate_taxonomies(number_of_taxonomies: int) -> dict | None:
    """Generate realistic taxonomies for organizing products using AI."""

    logger.info(f"Generating {number_of_taxonomies} taxonomies using AI...")

    try:
        system_prompt = f"""Generate {number_of_taxonomies} product taxonomies for a {settings.DATA_THEME_SUBJECT}.
        
        Taxonomies are high-level organizational structures for categorizing products. Focus on these specific types:
        
        REQUIRED TAXONOMIES (include these if generating 3+):
        1. Categories - General product types (food, toys, accessories, etc.)
        2. Brands - Realistic manufacturer/brand organization (different product brands, for example: Petkit, LG, Sony, Xiaomi, etc.)
        3. Collections - Curated product groupings (seasonal, themed, special collections)
        
        ADDITIONAL TAXONOMIES (for more than 3):
        - Pet Types (dog, cat, bird, small animals, etc.)
        - Life Stages (puppy, kitten, adult, senior)
        - Special Needs (allergies, sensitive skin, joint health, etc.)
        - Price Tiers (budget-friendly, mid-range, premium, luxury)
        - Product Materials (organic, natural, eco-friendly, synthetic)
        - Size/Breed (small breed, large breed, giant breed)
        
        Each taxonomy should represent a different way customers can browse and filter products.
        Make them practical and useful for an eCommerce {settings.DATA_THEME_SUBJECT}."""

        user_prompt = f"""Generate {number_of_taxonomies} realistic product taxonomies for {settings.SPREE_STORE_NAME}.
        
        IMPORTANT: Always include these taxonomies:
        1. "Categories" - for general product types
        2. "Brands" - for manufacturer/brand organization  
        
        If generating more than 3, include the above plus additional taxonomies from the list.
        
        Each taxonomy should have:
        - name (string): Clear, descriptive name (e.g., "Categories", "Brands", "Collections")
        - description (string): Brief explanation of what this taxonomy organizes
        
        Focus on practical ways customers browse and filter products in an eCommerce store."""

        taxonomy_response = await instructor_client.chat.completions.create(
            model="claude-3-5-haiku-latest",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            response_model=TaxonomyResponse,
            temperature=0.4,
            max_tokens=4096,
        )

        if taxonomy_response and taxonomy_response.taxonomies:
            # Add incrementing IDs to taxonomies
            taxonomies_with_ids = []
            taxonomy_id = 1

            for generated_taxonomy in taxonomy_response.taxonomies:
                # Add ID to taxonomy
                taxonomy_with_id = Taxonomy(
                    id=taxonomy_id,
                    name=generated_taxonomy.name,
                    description=generated_taxonomy.description,
                )
                taxonomies_with_ids.append(taxonomy_with_id)
                taxonomy_id += 1

            # Convert to dict format for JSON serialization
            taxonomies_dict = {"taxonomies": [taxonomy.model_dump() for taxonomy in taxonomies_with_ids]}

            # Ensure the generated directory exists
            TAXONOMIES_FILE.parent.mkdir(parents=True, exist_ok=True)

            # Save to JSON file
            with Path.open(TAXONOMIES_FILE, "w", encoding="utf-8") as f:
                json.dump(taxonomies_dict, f, indent=2, ensure_ascii=False)

            logger.succeed(f"Successfully generated and saved {len(taxonomies_with_ids)} taxonomies to {TAXONOMIES_FILE}")

            return taxonomies_dict
        else:
            logger.error("Failed to parse taxonomy response from AI")
            raise ValueError("Failed to generate taxonomies")

    except Exception as e:
        logger.error(f"Error generating taxonomies: {e}")
        raise


async def seed_taxonomies():
    """Seed taxonomies for the store."""
    try:
        # Load taxonomies from generated file
        taxonomies_list = []
        if TAXONOMIES_FILE.exists():
            try:
                with Path.open(TAXONOMIES_FILE, encoding="utf-8") as f:
                    taxonomies_data = json.load(f)
                taxonomies_list = taxonomies_data.get("taxonomies", [])
                logger.info(f"Loaded {len(taxonomies_list)} taxonomies from {TAXONOMIES_FILE}")
            except Exception as e:
                logger.warning(f"Could not load taxonomies from {TAXONOMIES_FILE}: {e}")
                logger.info("Falling back to hardcoded taxonomies")
                taxonomies_list = TAXONOMIES
        else:
            logger.info("No generated taxonomies file found, using hardcoded taxonomies")
            taxonomies_list = TAXONOMIES

        current_time = datetime.now()

        # Check which taxonomies already exist
        taxonomy_names = [tax["name"] for tax in taxonomies_list]
        existing_query = "SELECT name FROM spree_taxonomies WHERE name = ANY($1)"
        existing_names = await db_client.fetch(existing_query, taxonomy_names)
        existing_set = {row["name"] for row in existing_names}

        # Filter out taxonomies that already exist
        new_taxonomies = [tax for tax in taxonomies_list if tax["name"] not in existing_set]

        if not new_taxonomies:
            logger.info("All taxonomies already exist in the database")
            # Still need to check if corresponding taxons exist
            await _ensure_taxons_exist()
            return

        # Prepare the insert query for taxonomies
        taxonomy_insert_query = """
            INSERT INTO spree_taxonomies (name, created_at, updated_at, position, store_id, public_metadata, private_metadata)
            VALUES ($1, $2, $3, $4, $5, $6, $7)
            RETURNING id, name
        """

        # Insert taxonomies and collect their IDs
        inserted_taxonomies = []
        async with db_client.transaction() as conn:
            for index, taxonomy in enumerate(new_taxonomies):
                result = await conn.fetchrow(
                    taxonomy_insert_query,
                    taxonomy["name"],  # name
                    current_time,  # created_at
                    current_time,  # updated_at
                    index + 1,  # position (1-based)
                    1,  # store_id
                    None,  # public_metadata
                    None,  # private_metadata
                )
                inserted_taxonomies.append(result)

            # Now insert corresponding taxons
            taxon_insert_query = """
                INSERT INTO spree_taxons (parent_id, position, name, permalink, taxonomy_id, lft, rgt, description, 
                                        created_at, updated_at, meta_title, meta_description, meta_keywords, 
                                        depth, hide_from_nav, public_metadata, private_metadata)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17)
            """

            # Load taxons from JSON file to get rich descriptions
            taxons_data = {}
            if TAXONS_FILE.exists():
                try:
                    with Path.open(TAXONS_FILE, encoding="utf-8") as f:
                        taxons_data = json.load(f)
                    logger.info(f"Loaded taxons from {TAXONS_FILE} for rich descriptions")
                except Exception as e:
                    logger.warning(f"Could not load taxons from {TAXONS_FILE}: {e}")

            for taxonomy_record in inserted_taxonomies:
                # Look for the taxon in the JSON file to get rich description
                description = None
                meta_title = f"{taxonomy_record['name']} | {settings.SPREE_STORE_NAME}"
                meta_description = None
                meta_keywords = None

                # Try to find the taxon in the JSON file
                if taxons_data and "taxons" in taxons_data:
                    for taxon in taxons_data["taxons"]:
                        if taxon["name"] == taxonomy_record["name"] and taxon.get("parent_name") is None:
                            description = taxon.get("description")
                            meta_title = taxon.get("meta_title", meta_title)
                            meta_description = taxon.get("meta_description")
                            meta_keywords = taxon.get("meta_keywords")
                            logger.info(f"Found rich description for {taxonomy_record['name']} in taxons.json")
                            break

                # Create the permalink
                permalink = taxonomy_record["name"].lower().replace(" ", "-")

                # Insert the taxon with basic information
                await conn.execute(
                    taxon_insert_query,
                    None,  # parent_id (root taxon)
                    0,  # position
                    taxonomy_record["name"],  # name
                    permalink,  # permalink
                    taxonomy_record["id"],  # taxonomy_id
                    1,  # lft (nested set left)
                    2,  # rgt (nested set right)
                    description,  # description (no HTML during seeding)
                    current_time,  # created_at
                    current_time,  # updated_at
                    meta_title,  # meta_title
                    meta_description,  # meta_description
                    meta_keywords,  # meta_keywords
                    0,  # depth (root level)
                    False,  # hide_from_nav
                    None,  # public_metadata
                    None,  # private_metadata
                )

        logger.succeed(f"Successfully seeded {len(new_taxonomies)} taxonomies and their corresponding taxons: {', '.join([tax['name'] for tax in new_taxonomies])}")

    except Exception as e:
        logger.fail(f"Failed to seed taxonomies: {e}")
        raise


async def _ensure_taxons_exist():
    """Ensure taxons exist for all existing taxonomies."""
    try:
        # Load taxonomies from generated file
        taxonomies_list = []
        if TAXONOMIES_FILE.exists():
            try:
                with Path.open(TAXONOMIES_FILE, encoding="utf-8") as f:
                    taxonomies_data = json.load(f)
                taxonomies_list = taxonomies_data.get("taxonomies", [])
            except Exception as e:
                logger.warning(f"Could not load taxonomies from {TAXONOMIES_FILE}: {e}")
                taxonomies_list = TAXONOMIES
        else:
            taxonomies_list = TAXONOMIES

        current_time = datetime.now()

        # Find taxonomies that don't have corresponding root taxons
        taxonomy_names = [tax["name"] for tax in taxonomies_list]
        missing_taxons_query = """
            SELECT t.id, t.name 
            FROM spree_taxonomies t
            LEFT JOIN spree_taxons tx ON t.id = tx.taxonomy_id AND tx.parent_id IS NULL
            WHERE tx.id IS NULL AND t.name = ANY($1)
        """

        missing_taxons = await db_client.fetch(missing_taxons_query, taxonomy_names)

        if not missing_taxons:
            logger.info("All taxons already exist for existing taxonomies")
            return

        # Insert missing taxons
        taxon_insert_query = """
            INSERT INTO spree_taxons (parent_id, position, name, permalink, taxonomy_id, lft, rgt, description, 
                                    created_at, updated_at, meta_title, meta_description, meta_keywords, 
                                    depth, hide_from_nav, public_metadata, private_metadata)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17)
        """

        # Load taxons from JSON file to get rich descriptions
        taxons_data = {}
        if TAXONS_FILE.exists():
            try:
                with Path.open(TAXONS_FILE, encoding="utf-8") as f:
                    taxons_data = json.load(f)
                logger.info(f"Loaded taxons from {TAXONS_FILE} for rich descriptions")
            except Exception as e:
                logger.warning(f"Could not load taxons from {TAXONS_FILE}: {e}")

        for taxonomy_record in missing_taxons:
            # Look for the taxon in the JSON file to get rich description
            description = None
            meta_title = f"{taxonomy_record['name']} | {settings.SPREE_STORE_NAME}"
            meta_description = None
            meta_keywords = None

            # Try to find the taxon in the JSON file
            if taxons_data and "taxons" in taxons_data:
                for taxon in taxons_data["taxons"]:
                    if taxon["name"] == taxonomy_record["name"] and taxon.get("parent_name") is None:
                        description = taxon.get("description")
                        meta_title = taxon.get("meta_title", meta_title)
                        meta_description = taxon.get("meta_description")
                        meta_keywords = taxon.get("meta_keywords")
                        logger.info(f"Found rich description for {taxonomy_record['name']} in taxons.json")
                        break

            # Create the permalink
            permalink = taxonomy_record["name"].lower().replace(" ", "-")

            # Insert the taxon with basic information
            await db_client.execute(
                taxon_insert_query,
                None,  # parent_id (root taxon)
                0,  # position
                taxonomy_record["name"],  # name
                permalink,  # permalink
                taxonomy_record["id"],  # taxonomy_id
                1,  # lft (nested set left)
                2,  # rgt (nested set right)
                description,  # description (no HTML during seeding)
                current_time,  # created_at
                current_time,  # updated_at
                meta_title,  # meta_title
                meta_description,  # meta_description
                meta_keywords,  # meta_keywords
                0,  # depth (root level)
                False,  # hide_from_nav
                None,  # public_metadata
                None,  # private_metadata
            )

        logger.succeed(f"Created {len(missing_taxons)} missing taxons for existing taxonomies")

    except Exception as e:
        logger.fail(f"Failed to ensure taxons exist: {e}")
        raise
