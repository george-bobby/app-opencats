"""Taxon generation and seeding for Spree."""

import asyncio
import json
import time
from datetime import datetime
from pathlib import Path

from faker import Faker
from pydantic import BaseModel, Field

from apps.spree.config.settings import settings
from apps.spree.utils.ai import instructor_client
from apps.spree.utils.database import db_client
from common.logger import Logger


fake = Faker()
logger = Logger()

TAXONS_FILE = settings.DATA_PATH / "generated" / "taxons.json"


def generate_child_taxons_grid_html(child_taxons: list[dict], root_taxon_name: str) -> str:
    """Generate HTML grid of child taxon links to append to root taxon descriptions."""

    if not child_taxons:
        return ""

    # CSS for the responsive grid layout
    css = """
    <style>
    .child-taxons-grid {
      display: flex;
      flex-direction: column;
      justify-content: flex-start;
      flex-wrap: wrap;
      gap: 8px;
    }

    .child-taxon-item {
      border: 1px solid black;
      border-radius: 10px;
      height: 50px;
      min-width: 120px;
      display: flex;
      align-items: center;
      justify-content: center;
      text-decoration: none;
      color: #333;
      font-weight: bold;
      transition: background-color 0.2s;
      padding: 0 16px;
      text-align: center;
    }

    .child-taxon-item:hover {
      background-color: #f0f0f0;
      color: #000;
    }

    /* Mobile: 1 column */
    @media (max-width: 767px) {
      .child-taxons-grid {
        flex-direction: column;
        flex-wrap: nowrap;
        height: auto;
      }
    
      .child-taxon-item {
        width: 100%;
        max-width: none;
      }
    }

    /* Desktop: 2 columns */
    @media (min-width: 768px) {
      .child-taxons-grid {
        flex-direction: row;
        flex-wrap: wrap;
      }
    
      .child-taxon-item {
        width: calc(50% - 8px);
      }
    }
    </style>
    """

    # Generate root taxon slug
    root_taxon_slug = root_taxon_name.lower().replace(" ", "-")

    # Generate grid items
    grid_items = []
    for taxon in child_taxons:
        # Create a link to the taxon (using slug format for frontend routing)
        taxon_slug = taxon["name"].lower().replace(" ", "-")
        grid_items.append(f'<a href="/t/{root_taxon_slug}/{taxon_slug}" class="child-taxon-item">{taxon["name"]}</a>')

    # Combine CSS and grid
    grid_html = f"""
{css}
<div class="child-taxons-grid">
{chr(10).join(grid_items)}
</div>
"""

    return grid_html


class Taxon(BaseModel):
    """Individual taxon model."""

    id: int = Field(description="Unique identifier for the taxon")  # noqa: A003, RUF100
    name: str = Field(description="Clear, descriptive name for the taxon")
    description: str | None = Field(description="Brief description of the taxon category")
    parent_name: str | None = Field(description="Name of parent taxon, or null for root level")
    meta_title: str | None = Field(description="SEO meta title")
    meta_description: str | None = Field(description="SEO meta description")
    meta_keywords: str | None = Field(description="SEO meta keywords")
    hide_from_nav: bool = Field(description="Whether to hide from navigation", default=False)
    taxonomy_id: int = Field(description="ID of the taxonomy this taxon belongs to")
    lft: int | None = Field(description="Left value for nested set model", default=None)
    rgt: int | None = Field(description="Right value for nested set model", default=None)


class TaxonForGeneration(BaseModel):
    """Taxon model for AI generation (without ID)."""

    name: str = Field(description="Clear, descriptive name for the taxon")
    description: str | None = Field(description="Brief description of the taxon category")
    parent_name: str | None = Field(description="Name of parent taxon, or null for root level")
    meta_title: str | None = Field(description="SEO meta title")
    meta_description: str | None = Field(description="SEO meta description")
    meta_keywords: str | None = Field(description="SEO meta keywords")
    hide_from_nav: bool = Field(description="Whether to hide from navigation", default=False)
    taxonomy_name: str | None = Field(description="Name of the taxonomy this taxon belongs to", default=None)


class TaxonResponse(BaseModel):
    """Response format for generated taxons."""

    taxons: list[TaxonForGeneration]


class RootTaxonomyResponse(BaseModel):
    description: str = Field(description="Rich HTML description for the root taxonomy")
    meta_title: str = Field(description="SEO-optimized title")
    meta_description: str = Field(description="SEO-friendly description")
    meta_keywords: str = Field(description="Relevant keywords")


async def generate_root_taxonomy_description(taxonomy: dict, taxonomy_id: int) -> dict:
    """Generate a rich HTML description for a root taxonomy."""

    taxonomy_name = taxonomy["name"]
    taxonomy_description = taxonomy["description"]

    logger.info(f"Generating rich HTML description for root taxonomy: {taxonomy_name}")

    system_prompt = f"""Generate a rich, detailed HTML description for the root taxonomy "{taxonomy_name}" in {settings.SPREE_STORE_NAME}, a {settings.DATA_THEME_SUBJECT}.
    
    Current description: {taxonomy_description}
    
    For "Brands" taxonomy, create a description that explains the importance of brand selection in pet products, highlighting quality, reliability, and customer trust.
    
    For "Categories" taxonomy, create a description that explains how products are organized by type, making it easy for customers to find what they need.
    
    For "Pet Types" taxonomy, create a description that explains how products are tailored to different pet species.
    
    Include HTML formatting tags like <p>, <strong>, <em>, etc. to make the description visually appealing.
    """

    user_prompt = f"""Create a rich, detailed HTML description for the root taxonomy "{taxonomy_name}" in {settings.SPREE_STORE_NAME}.
    
    Include:
    - HTML formatting (<p>, <strong>, <em>, etc.)
    - SEO-friendly content
    - Clear explanation of what this taxonomy organizes
    - Why it's useful for customers
    
    Also provide (ALL REQUIRED):
    - meta_title: SEO-optimized title including "{settings.SPREE_STORE_NAME}"
    - meta_description: SEO-friendly description (150-160 characters)
    - meta_keywords: Relevant keywords for this taxonomy
    """

    try:
        # Define a model for the response
        response = await instructor_client.chat.completions.create(
            model="claude-3-5-haiku-latest",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            response_model=RootTaxonomyResponse,
            temperature=0.3,
            max_tokens=4096,
        )

        if response:
            # Create the root taxon with enhanced description
            root_taxon = {
                "name": taxonomy_name,
                "description": response.description,
                "parent_name": None,  # Top level
                "meta_title": response.meta_title,
                "meta_description": response.meta_description,
                "meta_keywords": response.meta_keywords,
                "hide_from_nav": False,
                "taxonomy_name": taxonomy_name,  # Keep for AI generation context
                "taxonomy_id": taxonomy_id,
            }
            return root_taxon
        else:
            logger.error(f"Failed to generate rich description for root taxonomy: {taxonomy_name}")
            # Return a default taxon with basic description
            return {
                "name": taxonomy_name,
                "description": taxonomy_description,
                "parent_name": None,  # Top level
                "meta_title": f"{taxonomy_name} | {settings.SPREE_STORE_NAME}",
                "meta_description": f"Browse our {taxonomy_description.lower()} at {settings.SPREE_STORE_NAME}",
                "meta_keywords": f"{taxonomy_name.lower()}, {settings.SPREE_STORE_NAME.lower()}",
                "hide_from_nav": False,
                "taxonomy_name": taxonomy_name,  # Keep for AI generation context
                "taxonomy_id": taxonomy_id,
            }
    except Exception as e:
        logger.error(f"Error generating rich description for root taxonomy {taxonomy_name}: {e}")
        # Return a default taxon with basic description
        return {
            "name": taxonomy_name,
            "description": taxonomy_description,
            "parent_name": None,  # Top level
            "meta_title": f"{taxonomy_name} | {settings.SPREE_STORE_NAME}",
            "meta_description": f"Browse our {taxonomy_description.lower()} at {settings.SPREE_STORE_NAME}",
            "meta_keywords": f"{taxonomy_name.lower()}, {settings.SPREE_STORE_NAME.lower()}",
            "hide_from_nav": False,
            "taxonomy_name": taxonomy_name,  # Keep for AI generation context
            "taxonomy_id": taxonomy_id,
        }


async def generate_subcategories_for_taxonomy(taxonomy: dict, subcategories_count: int, taxonomy_id: int) -> list[dict]:
    """Generate subcategories for a single taxonomy in parallel."""

    taxonomy_name = taxonomy["name"]
    taxonomy_description = taxonomy["description"]

    if subcategories_count <= 0:
        return []

    logger.info(f"Generating {subcategories_count} subcategories for {taxonomy_name}")

    # Different system prompts based on taxonomy type
    if taxonomy_name == "Brands":
        system_prompt = f"""Generate {subcategories_count} realistic brand names for pet products in {settings.SPREE_STORE_NAME}, a {settings.DATA_THEME_SUBJECT}.
        
        Parent Category: {taxonomy_name} - {taxonomy_description}
        
        Generate specific brand names like:
        - PetKit (Smart pet technology products)
        - Royal Canin (Premium pet nutrition)
        - Kong (Durable dog toys)
        - Pedan (Cat accessories)
        - Ciao (Premium cat treats)
        - Purina (Pet food and nutrition)
        - Frontline (Pet healthcare)
        - Petmate (Pet carriers and homes)
        
        Each brand should be a real, recognizable brand name in the pet industry.
        All brands should have parent_name = "{taxonomy_name}"."""

        user_prompt = f"""Generate exactly {subcategories_count} specific brand names for {settings.SPREE_STORE_NAME}.
        
        For each brand provide:
        - name: Specific brand name (like "PetKit", "Royal Canin", "Kong", etc.)
        - description: Brief explanation of what products this brand offers (REQUIRED)
        - parent_name: "{taxonomy_name}" (the parent taxonomy)
        - meta_title: SEO title including brand name and "{settings.SPREE_STORE_NAME}" (REQUIRED)
        - meta_description: SEO description about the brand's products (REQUIRED)
        - meta_keywords: Relevant keywords for the brand (REQUIRED)
        - hide_from_nav: false
        - taxonomy_name: "{taxonomy_name}" (to identify which taxonomy this belongs to)"""
    else:
        system_prompt = f"""Generate {subcategories_count} subcategories for the "{taxonomy_name}" category in {settings.SPREE_STORE_NAME}, a {settings.DATA_THEME_SUBJECT}.
        
        Parent Category: {taxonomy_name} - {taxonomy_description}
        
        For "Categories" taxonomy, create these core pet supply subcategories:
        - Dogs (Dog beds, toys, accessories, and essentials)
        - Cats (Cat products for all ages)
        - Treats (Pet snacks and edible rewards)
        - Travel (Pet carriers, travel bowls, portable gear)
        - Grooming (Brushes, shampoos, hygiene products)
        - Toys (Interactive pet toys)
        - Training (Training tools and behavioral aids)
        - Feeding (Bowls, feeders, food storage)
        - Health & Wellness (Supplements, vitamins, pet care)
        - Outdoor (Outdoor adventure gear for pets)
        
        For other taxonomies, create appropriate subcategories based on the taxonomy description.
        
        All subcategories should have parent_name = "{taxonomy_name}"."""

        user_prompt = f"""Generate exactly {subcategories_count} subcategories for the "{taxonomy_name}" category in {settings.SPREE_STORE_NAME}.
        
        For each subcategory provide:
        - name: Clear subcategory name
        - description: Brief explanation of what products belong here (REQUIRED)
        - parent_name: "{taxonomy_name}" (the parent taxonomy)
        - meta_title: SEO title including "{settings.SPREE_STORE_NAME}" (REQUIRED)
        - meta_description: SEO description (REQUIRED)
        - meta_keywords: Relevant keywords (REQUIRED)
        - hide_from_nav: false
        - o iaxonomy_name: "{taxonomy_name}" (to identify which taxonomy this belongs to)"""

    try:
        taxon_response = await instructor_client.chat.completions.create(
            model="claude-3-5-haiku-latest",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            response_model=TaxonResponse,
            temperature=0.3,
            max_tokens=8192,
        )

        if taxon_response and taxon_response.taxons:
            # Add taxonomy name and ID to each subcategory
            subcategories = []
            for taxon in taxon_response.taxons:
                taxon_dict = taxon.model_dump()
                taxon_dict["taxonomy_name"] = taxonomy_name  # Keep for context
                taxon_dict["taxonomy_id"] = taxonomy_id
                subcategories.append(taxon_dict)

            logger.info(f"Generated {len(taxon_response.taxons)} subcategories for {taxonomy_name} [ID: {taxonomy_id}]")
            return subcategories
        else:
            logger.error(f"Failed to parse subcategories response for {taxonomy_name}")
            return []
    except Exception as e:
        logger.error(f"Error generating subcategories for {taxonomy_name}: {e}")
        return []


async def generate_taxons(min_taxons_per_taxonomy: int, max_taxons_per_taxonomy: int) -> dict | None:
    """Generate realistic taxons where each taxonomy gets a different number of taxons."""
    from apps.spree.core.taxonomies import TAXONOMIES, TAXONOMIES_FILE

    logger.info(f"Generating taxons for each taxonomy (range: {min_taxons_per_taxonomy}-{max_taxons_per_taxonomy})...")

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

        # Create mapping from taxonomy names to IDs
        taxonomy_name_to_id = {}
        for taxonomy in taxonomies_list:
            # For generated taxonomies, use the ID field; for hardcoded ones, use position + 1
            taxonomy_id = taxonomy.get("id", taxonomies_list.index(taxonomy) + 1)
            taxonomy_name_to_id[taxonomy["name"]] = taxonomy_id

        all_taxons = []

        # First, create top-level taxons from taxonomies with rich descriptions
        logger.info("Generating rich descriptions for root taxonomies...")

        # Process root taxonomies one by one to avoid rate limiting
        for taxonomy in taxonomies_list:
            taxonomy_name = taxonomy["name"]
            taxonomy_id = taxonomy_name_to_id[taxonomy_name]

            try:
                # Generate a rich description for the root taxonomy
                root_taxon = await generate_root_taxonomy_description(taxonomy, taxonomy_id)
                all_taxons.append(root_taxon)
                logger.info(f"Created enhanced top-level taxon for taxonomy: {taxonomy_name} [ID: {taxonomy_id}]")
            except Exception as e:
                # Fallback to basic description if AI generation fails
                logger.error(f"Error generating root taxonomy description for {taxonomy_name}: {e}")
                taxonomy_description = taxonomy["description"]
                # Create a basic top-level taxon for the taxonomy itself
                taxonomy_taxon = {
                    "name": taxonomy_name,
                    "description": taxonomy_description,
                    "parent_name": None,  # Top level
                    "meta_title": f"{taxonomy_name} | {settings.SPREE_STORE_NAME}",
                    "meta_description": f"Browse our {taxonomy_description.lower()} at {settings.SPREE_STORE_NAME}",
                    "meta_keywords": f"{taxonomy_name.lower()}, {settings.SPREE_STORE_NAME.lower()}",
                    "hide_from_nav": False,
                    "taxonomy_name": taxonomy_name,  # Keep for AI generation context
                    "taxonomy_id": taxonomy_id,
                }
                all_taxons.append(taxonomy_taxon)
                logger.info(f"Created basic top-level taxon for taxonomy: {taxonomy_name} [ID: {taxonomy_id}] (fallback)")

        # Generate subcategories for each taxonomy in parallel
        # Each taxonomy gets a different number of subcategories (minus 1 for the top-level taxon)
        if len(taxonomies_list) > 0:
            logger.info(f"Generating subcategories for {len(taxonomies_list)} taxonomies in parallel...")
            start_time = time.time()

            # Create tasks for parallel execution with different subcategory counts
            tasks = []
            for taxonomy in taxonomies_list:
                taxonomy_id = taxonomy_name_to_id[taxonomy["name"]]
                # Generate a different random number for each taxonomy
                subcategories_count = fake.random_int(min_taxons_per_taxonomy - 1, max_taxons_per_taxonomy - 1)
                subcategories_count = max(0, subcategories_count)  # Ensure non-negative
                logger.info(f"  {taxonomy['name']}: {subcategories_count} subcategories")
                task = generate_subcategories_for_taxonomy(taxonomy, subcategories_count, taxonomy_id)
                tasks.append(task)

            # Execute all taxonomy generations in parallel
            results = await asyncio.gather(*tasks, return_exceptions=True)

            # Process results and add to all_taxons
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    taxonomy_name = taxonomies_list[i]["name"]
                    logger.error(f"Failed to generate subcategories for {taxonomy_name}: {result}")
                else:
                    # result is a list of subcategory dicts
                    if isinstance(result, list):
                        all_taxons.extend(result)
                    else:
                        logger.error(f"Expected list result but got {type(result)} for taxonomy {taxonomies_list[i]['name']}")

            elapsed_time = time.time() - start_time
            logger.info(f"Completed parallel generation for all taxonomies in {elapsed_time:.2f} seconds")

        # Add incrementing IDs to all taxons
        taxons_with_ids = []
        taxon_id = 1

        for taxon_dict in all_taxons:
            # Convert dict to Taxon model with ID
            taxon_with_id = Taxon(
                id=taxon_id,
                name=taxon_dict["name"],
                description=taxon_dict.get("description"),
                parent_name=taxon_dict.get("parent_name"),
                meta_title=taxon_dict.get("meta_title"),
                meta_description=taxon_dict.get("meta_description"),
                meta_keywords=taxon_dict.get("meta_keywords"),
                hide_from_nav=taxon_dict.get("hide_from_nav", False),
                taxonomy_id=taxon_dict["taxonomy_id"],
                lft=None,  # Will be calculated below
                rgt=None,  # Will be calculated below
            )
            taxons_with_ids.append(taxon_with_id)
            taxon_id += 1

        # Calculate nested set values for the generated taxons
        logger.info("Calculating nested set values for generated taxons...")

        # Build parent mapping for nested set calculation
        taxons_by_parent = {}

        for taxon in taxons_with_ids:
            if taxon.parent_name is None:
                # Top-level taxon
                taxons_by_parent[None] = [*taxons_by_parent.get(None, []), {"id": taxon.id, "name": taxon.name}]
            else:
                # Find parent by name
                parent_taxon = next((t for t in taxons_with_ids if t.name == taxon.parent_name), None)
                if parent_taxon:
                    parent_id = parent_taxon.id
                    taxons_by_parent[parent_id] = [*taxons_by_parent.get(parent_id, []), {"id": taxon.id, "name": taxon.name}]

        # Build taxonomy-based mapping for grid generation
        taxons_by_taxonomy = {}
        for taxon in taxons_with_ids:
            if taxon.parent_name is None:
                # Root taxon - initialize empty list for this taxonomy
                taxons_by_taxonomy[taxon.id] = []
            else:
                # Child taxon - add to its taxonomy's root taxon
                # Find the root taxon for this taxonomy
                root_taxon = next((t for t in taxons_with_ids if t.taxonomy_id == taxon.taxonomy_id and t.parent_name is None), None)
                if root_taxon:
                    if root_taxon.id not in taxons_by_taxonomy:
                        taxons_by_taxonomy[root_taxon.id] = []
                    taxons_by_taxonomy[root_taxon.id].append({"id": taxon.id, "name": taxon.name})

        # Append child taxons grid to root taxon descriptions
        logger.info("Appending child taxons grid to root taxon descriptions...")
        for taxon in taxons_with_ids:
            if taxon.parent_name is None:  # Root taxon
                # Get child taxons for this root taxon using taxonomy-based mapping
                child_taxons = taxons_by_taxonomy.get(taxon.id, [])
                if child_taxons:
                    # Generate grid HTML for child taxons
                    grid_html = generate_child_taxons_grid_html(child_taxons, taxon.name)
                    if grid_html:
                        # Append grid to existing description
                        current_description = taxon.description or ""
                        taxon.description = current_description + grid_html
                        logger.info(f"Added child taxons grid to root taxon: {taxon.name} ({len(child_taxons)} children)")
                else:
                    logger.info(f"No child taxons found for root taxon: {taxon.name}")

        # Calculate nested set values
        lft_rgt_values, _ = calculate_nested_set_values(taxons_by_parent, parent_id=None, left_value=1)

        # Update taxons with calculated lft/rgt values
        for taxon in taxons_with_ids:
            if taxon.id in lft_rgt_values:
                taxon.lft = lft_rgt_values[taxon.id]["lft"]
                taxon.rgt = lft_rgt_values[taxon.id]["rgt"]
                logger.info(f"  {taxon.name} (ID:{taxon.id}): lft={taxon.lft}, rgt={taxon.rgt}")
            else:
                logger.warning(f"No nested set values calculated for taxon: {taxon.name} (ID:{taxon.id})")

        # Save all taxons to file
        taxons_dict = {"taxons": [taxon.model_dump() for taxon in taxons_with_ids]}

        settings.DATA_PATH.mkdir(parents=True, exist_ok=True)
        TAXONS_FILE.parent.mkdir(parents=True, exist_ok=True)
        with Path.open(TAXONS_FILE, "w", encoding="utf-8") as f:
            json.dump(taxons_dict, f, indent=2, ensure_ascii=False)

        logger.succeed(f"Successfully generated and saved {len(taxons_with_ids)} total taxons to {TAXONS_FILE}")

        # Group by taxonomy for better logging
        for taxonomy in taxonomies_list:
            taxonomy_id = taxonomy_name_to_id[taxonomy["name"]]
            taxonomy_taxons = [t for t in taxons_with_ids if t.taxonomy_id == taxonomy_id]
            subcategories = [t for t in taxonomy_taxons if t.parent_name is not None]

            logger.info(f"{taxonomy['name']} [ID: {taxonomy_id}]: {len(taxonomy_taxons)} total taxons (1 top-level + {len(subcategories)} subcategories)")
            for taxon in subcategories:
                logger.info(f"  Generated subcategory: {taxon.name} [ID: {taxon.id}]")

        return taxons_dict

    except Exception as e:
        logger.error(f"Error generating taxons: {e}")
        raise


def calculate_nested_set_values(taxons_by_parent: dict, parent_id: int | None = None, left_value: int = 1) -> tuple[dict, int]:
    """Calculate left and right values for nested set model.

    This follows the nested set model where:
    - Each node gets a left (lft) value when first visited
    - Each node gets a right (rgt) value after all its children are processed
    - Sequential numbering: parent lft=1, child1 lft=2, child1 rgt=3, child2 lft=4, child2 rgt=5, parent rgt=6
    """
    current_left = left_value
    lft_rgt_values = {}

    children = taxons_by_parent.get(parent_id, [])

    # Sort children by name for consistent ordering
    children = sorted(children, key=lambda x: x["name"])

    for child in children:
        child_id = child["id"]

        # Set left value for this node
        lft_rgt_values[child_id] = {"lft": current_left}
        current_left += 1

        # Recursively process children (if any)
        child_values, current_left = calculate_nested_set_values(taxons_by_parent, child_id, current_left)
        lft_rgt_values.update(child_values)

        # Set right value for this node (after all children are processed)
        lft_rgt_values[child_id]["rgt"] = current_left
        current_left += 1

    return lft_rgt_values, current_left


async def seed_taxons():
    """Insert taxons into the database."""
    from apps.spree.core.taxonomies import TAXONOMIES, TAXONOMIES_FILE

    logger.start("Inserting taxons into spree_taxons table...")

    try:
        # Load taxons from JSON file
        if not TAXONS_FILE.exists():
            logger.error(f"Taxons file not found at {TAXONS_FILE}. Run generate command first.")
            raise FileNotFoundError("Taxons file not found")

        with Path.open(TAXONS_FILE, encoding="utf-8") as f:
            data = json.load(f)

        taxons = data.get("taxons", [])
        logger.info(f"Loaded {len(taxons)} taxons from {TAXONS_FILE}")

        # Load taxonomies from generated file to get taxonomy names
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

        # Get all taxonomy IDs
        taxonomy_names = [tax["name"] for tax in taxonomies_list]
        taxonomy_records = await db_client.fetch("SELECT id, name FROM spree_taxonomies WHERE name = ANY($1)", taxonomy_names)

        if not taxonomy_records:
            logger.error("No taxonomies found. Please seed taxonomies first.")
            raise ValueError("No taxonomies found")

        taxonomy_id_map = {record["name"]: record["id"] for record in taxonomy_records}
        logger.info(f"Found taxonomies: {list(taxonomy_id_map.keys())}")

        current_time = datetime.now()

        # First pass: Insert all taxons and build parent mapping
        taxon_id_map = {}  # name -> database id
        taxons_by_parent = {}  # parent_id -> list of children

        # All taxons with parent_name = null are top-level taxons under the taxonomy
        top_level_taxons = [t for t in taxons if t.get("parent_name") is None]
        child_taxons = [t for t in taxons if t.get("parent_name") is not None]

        logger.info(f"Processing {len(top_level_taxons)} top-level taxons first")

        for taxon in top_level_taxons:
            try:
                # Get taxonomy_id for this taxon
                taxonomy_id = taxon.get("taxonomy_id")
                if taxonomy_id is None:
                    # Fallback to taxonomy_name lookup for backward compatibility
                    taxon_taxonomy_name = taxon.get("taxonomy_name", "Categories")
                    if taxon_taxonomy_name not in taxonomy_id_map:
                        logger.warning(f"Taxonomy '{taxon_taxonomy_name}' not found for taxon '{taxon['name']}', skipping")
                        continue
                    taxonomy_id = taxonomy_id_map[taxon_taxonomy_name]
                    logger.info(f"Using fallback taxonomy lookup for taxon '{taxon['name']}'")
                else:
                    # Verify the taxonomy_id exists in the database
                    if taxonomy_id not in taxonomy_id_map.values():
                        logger.warning(f"Taxonomy ID {taxonomy_id} not found in database for taxon '{taxon['name']}', skipping")
                        continue

                # Check if taxon already exists
                existing_taxon = await db_client.fetchrow("SELECT id FROM spree_taxons WHERE name = $1 AND taxonomy_id = $2 AND parent_id IS NULL", taxon["name"], taxonomy_id)

                if existing_taxon:
                    taxon_id_map[taxon["name"]] = existing_taxon["id"]
                    logger.info(f"Found existing top-level taxon: {taxon['name']}")
                    continue

                # Create permalink
                permalink = taxon["name"].lower().replace(" ", "-").replace("&", "and")

                # Insert top-level taxon with lft/rgt values from JSON or temporary values
                lft_value = taxon.get("lft", 1)  # Use from JSON or default to 1
                rgt_value = taxon.get("rgt", 2)  # Use from JSON or default to 2

                taxon_record = await db_client.fetchrow(
                    """
                    INSERT INTO spree_taxons (parent_id, position, name, permalink, taxonomy_id, 
                                            lft, rgt, description, created_at, updated_at,
                                            meta_title, meta_description, meta_keywords, depth,
                                            hide_from_nav, public_metadata, private_metadata)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17)
                    RETURNING id
                    """,
                    None,  # parent_id (direct child of taxonomy)
                    0,  # position (will be updated)
                    taxon["name"],
                    permalink,
                    taxonomy_id,
                    lft_value,  # lft from JSON or temporary
                    rgt_value,  # rgt from JSON or temporary
                    taxon.get("description"),
                    current_time,
                    current_time,
                    taxon.get("meta_title"),
                    taxon.get("meta_description"),
                    taxon.get("meta_keywords"),
                    0,  # depth (top level under taxonomy)
                    taxon.get("hide_from_nav", False),
                    None,  # public_metadata
                    None,  # private_metadata
                )

                if taxon_record:
                    taxon_id_map[taxon["name"]] = taxon_record["id"]
                    taxons_by_parent[None] = [*taxons_by_parent.get(None, []), {"id": taxon_record["id"], "name": taxon["name"]}]
                    logger.info(f"Inserted top-level taxon: {taxon['name']}")

            except Exception as e:
                logger.error(f"Failed to insert top-level taxon {taxon['name']}: {e}")
                continue

        # Second pass: Insert child taxons
        logger.info(f"Processing {len(child_taxons)} child taxons")

        for taxon in child_taxons:
            try:
                # Get taxonomy_id for this taxon
                taxonomy_id = taxon.get("taxonomy_id")
                if taxonomy_id is None:
                    # Fallback to taxonomy_name lookup for backward compatibility
                    taxon_taxonomy_name = taxon.get("taxonomy_name", "Categories")
                    if taxon_taxonomy_name not in taxonomy_id_map:
                        logger.warning(f"Taxonomy '{taxon_taxonomy_name}' not found for taxon '{taxon['name']}', skipping")
                        continue
                    taxonomy_id = taxonomy_id_map[taxon_taxonomy_name]
                    logger.info(f"Using fallback taxonomy lookup for taxon '{taxon['name']}'")
                else:
                    # Verify the taxonomy_id exists in the database
                    if taxonomy_id not in taxonomy_id_map.values():
                        logger.warning(f"Taxonomy ID {taxonomy_id} not found in database for taxon '{taxon['name']}', skipping")
                        continue

                parent_name = taxon.get("parent_name")
                if not parent_name or parent_name not in taxon_id_map:
                    logger.warning(f"Parent '{parent_name}' not found for taxon '{taxon['name']}', skipping")
                    continue

                parent_id = taxon_id_map[parent_name]

                # Check if taxon already exists
                existing_taxon = await db_client.fetchrow("SELECT id FROM spree_taxons WHERE name = $1 AND parent_id = $2", taxon["name"], parent_id)

                if existing_taxon:
                    taxon_id_map[taxon["name"]] = existing_taxon["id"]
                    logger.info(f"Found existing child taxon: {taxon['name']}")
                    continue

                # Calculate depth
                depth = 1  # Child of root
                if parent_name in [t["name"] for t in child_taxons]:
                    depth = 2  # Grandchild

                # Create permalink
                permalink = f"{parent_name.lower().replace(' ', '-')}/{taxon['name'].lower().replace(' ', '-').replace('&', 'and')}"

                # Insert child taxon with lft/rgt values from JSON or temporary values
                lft_value = taxon.get("lft", 1)  # Use from JSON or default to 1
                rgt_value = taxon.get("rgt", 2)  # Use from JSON or default to 2

                taxon_record = await db_client.fetchrow(
                    """
                    INSERT INTO spree_taxons (parent_id, position, name, permalink, taxonomy_id, 
                                            lft, rgt, description, created_at, updated_at,
                                            meta_title, meta_description, meta_keywords, depth,
                                            hide_from_nav, public_metadata, private_metadata)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17)
                    RETURNING id
                    """,
                    parent_id,
                    0,  # position (will be updated)
                    taxon["name"],
                    permalink,
                    taxonomy_id,
                    lft_value,  # lft from JSON or temporary
                    rgt_value,  # rgt from JSON or temporary
                    taxon.get("description"),
                    current_time,
                    current_time,
                    taxon.get("meta_title"),
                    taxon.get("meta_description"),
                    taxon.get("meta_keywords"),
                    depth,
                    taxon.get("hide_from_nav", False),
                    None,  # public_metadata
                    None,  # private_metadata
                )

                if taxon_record:
                    taxon_id_map[taxon["name"]] = taxon_record["id"]
                    taxons_by_parent[parent_id] = [*taxons_by_parent.get(parent_id, []), {"id": taxon_record["id"], "name": taxon["name"]}]

            except Exception as e:
                logger.error(f"Failed to insert child taxon {taxon['name']}: {e}")
                continue

        # Third pass: Update nested set values and positions (only if needed)
        # Check if the taxons in JSON already have lft/rgt values
        taxons_have_nested_values = any(taxon.get("lft") is not None and taxon.get("rgt") is not None for taxon in taxons)

        if not taxons_have_nested_values:
            logger.info("Calculating nested set values and updating positions...")

            # Debug: Log the taxons_by_parent structure
            logger.info("Taxons by parent structure:")
            for parent_id, children in taxons_by_parent.items():
                parent_name = "ROOT" if parent_id is None else f"ID:{parent_id}"
                child_names = [child["name"] for child in children]
                logger.info(f"  {parent_name} -> [{', '.join(child_names)}]")

            # Calculate nested set values starting from root (None = top level)
            lft_rgt_values, _ = calculate_nested_set_values(taxons_by_parent, parent_id=None, left_value=1)

            # Debug: Log the calculated nested set values
            logger.info("Calculated nested set values:")
            for taxon_id, values in lft_rgt_values.items():
                taxon_name = next((child["name"] for children in taxons_by_parent.values() for child in children if child["id"] == taxon_id), f"Unknown-{taxon_id}")
                logger.info(f"  {taxon_name} (ID:{taxon_id}): lft={values['lft']}, rgt={values['rgt']}")

            for taxon_id, values in lft_rgt_values.items():
                await db_client.execute("UPDATE spree_taxons SET lft = $1, rgt = $2 WHERE id = $3", values["lft"], values["rgt"], taxon_id)
        else:
            logger.info("Using pre-calculated nested set values from JSON file - no recalculation needed")

        # Update positions within each parent group
        for _, children in taxons_by_parent.items():
            for position, child in enumerate(children):
                await db_client.execute("UPDATE spree_taxons SET position = $1 WHERE id = $2", position, child["id"])

        logger.succeed(f"Successfully processed {len(taxon_id_map)} taxons in the database")

    except Exception as e:
        logger.error(f"Error seeding taxons in database: {e}")
        raise
