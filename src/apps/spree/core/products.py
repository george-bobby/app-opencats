import asyncio
import json
import random
from datetime import datetime, timedelta
from pathlib import Path

from apps.spree.config.settings import settings
from apps.spree.libs.products.description import generate_product_description
from apps.spree.libs.products.images import clear_image_cache, generate_images_for_products_batch, replace_image_placeholders_in_descriptions
from apps.spree.libs.products.models import Product, ProductDescriptionForGeneration, ProductForGeneration
from apps.spree.libs.products.specs import generate_product_specs
from apps.spree.utils.constants import (
    OPTION_TYPES_FILE,
    PRODUCTS_FILE,
    PROPERTIES_FILE,
    PROTOTYPES_FILE,
    TAXONS_FILE,
)
from apps.spree.utils.database import db_client
from common.logger import Logger


logger = Logger()
BATCH_SIZE = settings.MAX_CONCURRENT_GENERATION_REQUESTS


async def generate_products(number_of_products: int) -> dict | None:
    """Generate realistic products for a pet supplies eCommerce store."""

    logger.info(f"Generating {number_of_products} products for pet supplies store...")

    # Load existing data for context
    prototypes_context = ""
    properties_context = ""
    option_types_context = ""

    # Load prototypes from JSON file only (no database calls)
    prototypes_context = ""
    if PROTOTYPES_FILE.exists():
        try:
            with PROTOTYPES_FILE.open(encoding="utf-8") as f:
                import json

                prototypes_data = json.load(f)
            prototypes = prototypes_data.get("prototypes", [])
            if prototypes:
                # Check if prototypes have IDs
                if "id" in prototypes[0]:
                    # Use IDs from JSON
                    prototypes_with_ids = {}
                    for _idx, prototype in enumerate(prototypes):
                        prototypes_with_ids[prototype["name"]] = prototype["id"]
                    prototypes_context = f"Available prototypes with IDs: {prototypes_with_ids}"
                    logger.info(f"  Loaded {len(prototypes)} prototypes from JSON file")
                else:
                    # Assign sequential IDs (1, 2, 3, ...) for generation
                    prototypes_with_ids = {}
                    for idx, prototype in enumerate(prototypes, 1):
                        prototypes_with_ids[prototype["name"]] = idx
                    prototypes_context = f"Available prototypes with IDs: {prototypes_with_ids}"
                    logger.info(f"  Loaded {len(prototypes)} prototypes from JSON file")
        except Exception as e:
            logger.warning(f"Could not load prototypes from file: {e}")

    # Load properties
    available_properties = []
    if PROPERTIES_FILE.exists():
        try:
            with PROPERTIES_FILE.open(encoding="utf-8") as f:
                import json

                properties_data = json.load(f)
            properties = properties_data.get("properties", [])
            if properties:
                available_properties = [prop["name"] for prop in properties]
                properties_context = f"Available properties: {', '.join(available_properties)}"
                logger.info(f"  Loaded {len(properties)} properties for context")
        except Exception as e:
            logger.warning(f"Could not load properties for context: {e}")

    option_types_context = ""
    if OPTION_TYPES_FILE.exists():
        try:
            with OPTION_TYPES_FILE.open(encoding="utf-8") as f:
                import json

                option_types_data = json.load(f)
            option_types = option_types_data.get("option_types", [])
            if option_types:
                option_types_with_ids = {}
                for option_type in option_types:
                    option_type_name = option_type["name"]
                    option_types_with_ids[option_type_name] = []
                    for option_value in option_type.get("option_values", []):
                        option_types_with_ids[option_type_name].append({"name": option_value["name"], "id": option_value["id"]})

                option_types_context = f"  Available option types: {option_types_with_ids}"
                logger.info(f"  Loaded {len(option_types)} option types from JSON file")
        except Exception as e:
            logger.warning(f"Could not load option types from file: {e}")

    taxons_context = ""
    all_taxons = []
    if TAXONS_FILE.exists():
        try:
            with TAXONS_FILE.open(encoding="utf-8") as f:
                import json

                taxons_data = json.load(f)
            all_taxons = taxons_data.get("taxons", [])
            if all_taxons:
                # Create a mapping of taxon names to IDs for easy reference
                taxons_with_ids = {}
                for taxon in all_taxons:
                    taxons_with_ids[taxon["name"]] = taxon["id"]
                taxons_context = f"  Available taxons: {taxons_with_ids}"
                logger.info(f"  Loaded {len(all_taxons)} taxons from JSON file")
        except Exception as e:
            logger.warning(f"Could not load taxons from file: {e}")

    # Generate all products with semaphore limiting concurrency
    all_products = []
    generated_names = set()
    generated_skus = set()

    logger.info(f"Generating {number_of_products} products with max {BATCH_SIZE} concurrent")
    start_time = datetime.now()

    # Create semaphore to limit concurrent execution
    semaphore = asyncio.Semaphore(BATCH_SIZE)

    async def generate_with_semaphore(product_index: int):
        """Generate a single product with semaphore limiting."""
        async with semaphore:
            return await generate_single_complete_product(
                product_index,
                prototypes_context,
                option_types_context,
                properties_context,
                taxons_context,
                generated_names,
                generated_skus,
                all_taxons,
            )

    # Create all tasks at once
    product_tasks = [generate_with_semaphore(i + 1) for i in range(number_of_products)]

    # Execute all tasks (semaphore will limit concurrency)
    results = await asyncio.gather(*product_tasks, return_exceptions=True)

    # Process results
    for result in results:
        if isinstance(result, Exception):
            logger.error(f"Failed to generate product: {result}")
            continue
        elif result is not None and isinstance(result, tuple):
            all_products.append(result)
            # Update tracking sets
            product, description = result
            generated_names.add(product.name.lower())
            generated_skus.add(product.sku)

    if not all_products:
        logger.error("No products were successfully generated")
        return None

    # Descriptions are already generated, extract them
    description_results = []
    for _, description_result in all_products:
        description_results.append(description_result)

    # Add incrementing IDs to products
    products_with_ids = []
    product_id = 1

    for _, ((generated_product, description_result), _) in enumerate(zip(all_products, description_results, strict=False)):
        # Add delay to avoid overwhelming the API

        random_days = random.randint(1, 365)
        past_date = (datetime.now() - timedelta(days=random_days)).strftime("%Y-%m-%d")

        # Use generated description or fallback
        if isinstance(description_result, Exception):
            logger.error(f"Failed to generate description for {generated_product.name}: {description_result}")
            description = ""
            meta_title = generated_product.name
            meta_description = generated_product.name[:160]
            meta_keywords = generated_product.name.lower().replace(" ", ", ")
        elif description_result is not None:
            # Type assertion: description_result is ProductDescriptionForGeneration
            from apps.spree.libs.products.models import ProductDescriptionForGeneration

            assert isinstance(description_result, ProductDescriptionForGeneration)
            description = description_result.description
            meta_title = description_result.meta_title
            meta_description = description_result.meta_description
            meta_keywords = description_result.meta_keywords
        else:
            logger.warning(f"Failed to generate description for {generated_product.name}, using fallback")
            description = ""
            meta_title = generated_product.name
            meta_description = generated_product.name[:160]
            meta_keywords = generated_product.name.lower().replace(" ", ", ")

        product_with_id = Product(
            id=product_id,
            name=generated_product.name,
            description=description,
            prototype_id=generated_product.prototype_id,
            master_price=generated_product.master_price,
            sku=generated_product.sku,
            variants=generated_product.variants,
            image_keywords=generated_product.image_keywords,
            meta_title=meta_title,
            meta_description=meta_description,
            meta_keywords=meta_keywords,
            status=generated_product.status,
            promotionable=generated_product.promotionable,
            taxon_ids=generated_product.taxon_ids,
            available_on=past_date,
        )
        products_with_ids.append(product_with_id)
        product_id += 1

    # Convert to dict format for JSON serialization
    products_data = {"products": [product.model_dump() for product in products_with_ids]}

    # Generate images for all products
    images_data = await generate_images_for_products_batch(products_data["products"], max_concurrent=8)

    # Embed image data into products
    for product in products_data["products"]:
        product_id = str(product.get("id"))
        if product_id in images_data.get("images", {}):
            product["images"] = images_data["images"][product_id]
        else:
            product["images"] = {"product_id": product.get("id"), "product_name": product.get("name"), "main_images": [], "variant_images": {}}

    # Replace IMAGE_TAG_PLACEHOLDER with actual image tags
    logger.info("Replacing image placeholders in product descriptions...")
    products_data = replace_image_placeholders_in_descriptions(products_data)

    # Save products with embedded image data and replaced placeholders
    settings.DATA_PATH.mkdir(parents=True, exist_ok=True)
    PRODUCTS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with PRODUCTS_FILE.open("w", encoding="utf-8") as f:
        json.dump(products_data, f, indent=2, ensure_ascii=False)

    # Cache is automatically saved by generate_images_for_products_batch, no need to clear it

    elapsed_time = (datetime.now() - start_time).total_seconds()
    logger.succeed(f"Successfully generated and saved {len(products_data['products'])} products to {PRODUCTS_FILE} in {elapsed_time:.2f} seconds")

    # Log summary statistics
    total_variants = sum(len(product.get("variants", [])) for product in products_data["products"])
    logger.info(f"Generated {len(products_data['products'])} products with {total_variants} total variants")

    clear_image_cache()
    return products_data


async def generate_single_complete_product(
    product_index: int,
    prototypes_context: str,
    option_types_context: str,
    properties_context: str,
    taxons_context: str,
    generated_names: set,
    generated_skus: set,
    all_taxons: list,
) -> tuple[ProductForGeneration, ProductDescriptionForGeneration | None] | None:
    """Generate both specs and description for a single product."""

    # Select one taxon from each taxonomy for comprehensive categorization
    selected_taxons = {}

    # Group taxons by taxonomy
    taxons_by_taxonomy = {}
    for taxon in all_taxons:
        taxonomy_id = taxon.get("taxonomy_id")
        if taxonomy_id not in taxons_by_taxonomy:
            taxons_by_taxonomy[taxonomy_id] = []
        taxons_by_taxonomy[taxonomy_id].append(taxon)

    # Select one random taxon from each taxonomy
    for taxonomy_id, taxonomy_taxons in taxons_by_taxonomy.items():
        # Only select from child taxons (not root taxons)
        child_taxons = [t for t in taxonomy_taxons if t.get("parent_name") is not None]
        if child_taxons:
            selected_taxon = random.choice(child_taxons)
            selected_taxons[taxonomy_id] = selected_taxon

    try:
        # Generate product specs
        basic_result = await generate_product_specs(
            prototypes_context,
            option_types_context,
            properties_context,
            taxons_context,
            product_index,
            generated_names,
            generated_skus,
            list(selected_taxons.values()),
        )

        if basic_result is None:
            return None

        # Check for duplicates
        if basic_result.name.lower() in generated_names or basic_result.sku in generated_skus:
            logger.warning(f"Skipping duplicate product: {basic_result.name} (SKU: {basic_result.sku})")
            return None

        # Generate description immediately (pass None for target_taxon since we use all selected_taxons now)
        description_result = await generate_product_description(basic_result, taxons_context, None)

        return (basic_result, description_result)

    except Exception as e:
        logger.error(f"Failed to generate complete product {product_index}: {e}")
        return None


def find_exact_taxon_matches(taxon_name: str, all_taxons: list) -> list[int]:
    """Find all taxons with EXACT names across different taxonomies.

    For example, if a product belongs to "Cats" (Categories), it should also
    be associated with "Cats" (Pet Types), "Cats" (Life Stages), etc.

    NOTE: This should NOT be used for brand taxons as brands are unique.
    """
    exact_match_taxon_ids = []

    # Normalize the taxon name for comparison (lowercase, remove spaces)
    normalized_name = taxon_name.lower().replace(" ", "").replace("-", "").replace("&", "and")

    for taxon in all_taxons:
        # Skip if this is a brand taxon - brands should not have cross-taxonomy associations
        if taxon.get("parent_name") == "Brands":
            continue

        # Normalize the comparison taxon name
        comparison_name = taxon["name"].lower().replace(" ", "").replace("-", "").replace("&", "and")

        # Only match EXACT names (no partial matches)
        if comparison_name == normalized_name:
            exact_match_taxon_ids.append(taxon["id"])

    return exact_match_taxon_ids


async def seed_products():
    """Insert products, variants, and relationships into the database."""

    logger.start("Inserting products and variants into database tables...")

    try:
        # Load products from JSON file
        if not PRODUCTS_FILE.exists():
            logger.error(f"Products file not found at {PRODUCTS_FILE}. Run generate command first.")
            raise FileNotFoundError("Products file not found")

        with Path.open(PRODUCTS_FILE, encoding="utf-8") as f:
            data = json.load(f)

        products = data.get("products", [])
        logger.info(f"Loaded {len(products)} products from {PRODUCTS_FILE}")

        current_time = datetime.now()

        # Get existing IDs for relationships
        logger.info("Loading existing prototypes, properties, and option type IDs for validation...")

        # Load prototype IDs from JSON file
        prototype_id_map = {}
        if PROTOTYPES_FILE.exists():
            try:
                with Path.open(PROTOTYPES_FILE, encoding="utf-8") as f:
                    prototypes_data = json.load(f)
                prototypes = prototypes_data.get("prototypes", [])
                for prototype in prototypes:
                    # Assume prototype has 'id' field, fallback to name lookup if not
                    prototype_id_map[prototype["name"]] = prototype.get("id", True)  # True for validation if id not present
                logger.info(f"Loaded {len(prototype_id_map)} prototypes from JSON file")
            except Exception as e:
                logger.warning(f"Could not load prototypes from JSON: {e}")
                # Fallback to database
                prototype_records = await db_client.fetch("SELECT name FROM spree_prototypes")
                prototype_id_map = {record["name"]: True for record in prototype_records}
                logger.info(f"Found {len(prototype_id_map)} prototypes in database (fallback)")
        else:
            # Fallback to database
            prototype_records = await db_client.fetch("SELECT name FROM spree_prototypes")
            prototype_id_map = {record["name"]: True for record in prototype_records}
            logger.info(f"Found {len(prototype_id_map)} prototypes in database (fallback)")

        # Load property IDs
        property_records = await db_client.fetch("SELECT id, name FROM spree_properties")
        property_id_map = {record["name"]: record["id"] for record in property_records}
        logger.info(f"Found {len(property_id_map)} properties in database")

        # Load taxons for cross-taxonomy associations
        all_taxons = []
        if TAXONS_FILE.exists():
            try:
                with Path.open(TAXONS_FILE, encoding="utf-8") as f:
                    taxons_data = json.load(f)
                all_taxons = taxons_data.get("taxons", [])
                logger.info(f"Loaded {len(all_taxons)} taxons for cross-taxonomy associations")
            except Exception as e:
                logger.warning(f"Could not load taxons from {TAXONS_FILE}: {e}")

        # Note: Option value IDs are now directly used in generated data

        # Get default shipping category, tax category, and store
        default_shipping_category = await db_client.fetchrow("SELECT id FROM spree_shipping_categories WHERE name = 'Default' LIMIT 1")
        default_tax_category = await db_client.fetchrow("SELECT id FROM spree_tax_categories WHERE is_default = true LIMIT 1")
        default_store = await db_client.fetchrow("SELECT id FROM spree_stores ORDER BY created_at ASC LIMIT 1")

        if not default_shipping_category:
            logger.error("Default shipping category not found")
            raise ValueError("Default shipping category not found")

        if not default_tax_category:
            logger.error("Default tax category not found")
            raise ValueError("Default tax category not found")

        if not default_store:
            logger.error("Default store not found")
            raise ValueError("Default store not found")

        shipping_category_id = default_shipping_category["id"]
        tax_category_id = default_tax_category["id"]
        store_id = default_store["id"]

        # Process each product
        inserted_products = 0
        existing_products = 0
        total_variants = 0

        for product_data in products:
            try:
                # Use product ID from JSON data
                product_id = product_data.get("id")
                if not product_id:
                    logger.warning(f"No ID found for product {product_data['name']}, skipping")
                    continue

                # Check if product already exists by ID or slug
                existing_product = await db_client.fetchrow("SELECT id FROM spree_products WHERE id = $1 OR slug = $2", product_id, product_data["sku"].lower())

                if existing_product:
                    existing_products += 1
                    logger.info(f"Found existing product: {product_data['name']} [ID: {product_id}]")
                    continue

                # Use prototype_id directly from generated data
                prototype_id = product_data.get("prototype_id")
                if not prototype_id:
                    logger.warning(f"No prototype_id found for product {product_data['name']}")
                    continue

                # Insert new product with specific ID
                # Use available_on from the product data if available, otherwise use current time
                available_on_date = product_data.get("available_on")
                if available_on_date:
                    try:
                        available_on_datetime = datetime.fromisoformat(available_on_date)
                    except ValueError:
                        available_on_datetime = current_time
                        logger.warning(f"Invalid available_on date format for product {product_id}, using current time")
                else:
                    available_on_datetime = current_time

                product_record = await db_client.fetchrow(
                    """
                    INSERT INTO spree_products (id, name, description, slug, created_at, updated_at,
                                              meta_title, meta_description, meta_keywords, 
                                              shipping_category_id, tax_category_id,
                                              status, promotionable, available_on)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14)
                    RETURNING id
                    """,
                    product_id,  # Use specific ID from JSON
                    product_data["name"],
                    product_data["description"],
                    product_data["sku"].lower(),
                    current_time,
                    current_time,
                    product_data.get("meta_title", product_data["name"]),
                    product_data.get("meta_description", product_data["description"][:160]),
                    product_data.get("meta_keywords", product_data["name"].lower().replace(" ", ", ")),
                    shipping_category_id,
                    tax_category_id,
                    product_data.get("status", "active"),
                    product_data.get("promotionable", True),
                    available_on_datetime,  # Use the past date from product data
                )

                if not product_record:
                    logger.error(f"Failed to insert product: {product_data['name']}")
                    continue

                # product_id already set from JSON data above
                inserted_products += 1

                # Associate product with default store
                await db_client.execute(
                    """
                    INSERT INTO spree_products_stores (product_id, store_id, created_at, updated_at)
                    VALUES ($1, $2, $3, $4)
                    """,
                    product_id,
                    store_id,
                    current_time,
                    current_time,
                )

                # Associate product with taxons (including cross-taxonomy associations)
                if product_data.get("taxon_ids"):
                    # Get the taxon names for cross-taxonomy lookup
                    taxon_names = []
                    for taxon_id in product_data["taxon_ids"]:
                        # Find taxon name by ID from the loaded taxons
                        taxon_name = next((t["name"] for t in all_taxons if t["id"] == taxon_id), None)
                        if taxon_name:
                            taxon_names.append(taxon_name)

                    # Collect all taxon IDs to associate (original + similar names across taxonomies)
                    all_taxon_ids = set(product_data["taxon_ids"])  # Start with original taxon IDs

                    # Find similar taxon names across different taxonomies (excluding brand taxons)
                    for taxon_name in taxon_names:
                        # Skip cross-taxonomy associations for brand taxons
                        taxon_info = next((t for t in all_taxons if t["name"] == taxon_name), None)
                        if taxon_info and taxon_info.get("parent_name") == "Brands":
                            continue  # Skip cross-taxonomy associations for brands

                        exact_match_taxon_ids = find_exact_taxon_matches(taxon_name, all_taxons)
                        all_taxon_ids.update(exact_match_taxon_ids)

                    # Insert all taxon associations
                    for position, taxon_id in enumerate(all_taxon_ids, 1):
                        await db_client.execute(
                            """
                            INSERT INTO spree_products_taxons (product_id, taxon_id, position, created_at, updated_at)
                            VALUES ($1, $2, $3, $4, $5)
                            """,
                            product_id,
                            taxon_id,
                            position,
                            current_time,
                            current_time,
                        )

                    if len(all_taxon_ids) > len(product_data["taxon_ids"]):
                        logger.info(f"Product {product_data['name']}: Added {len(all_taxon_ids) - len(product_data['taxon_ids'])} exact cross-taxonomy matches")

                # Associate product with option types based on variants
                # Collect all option value IDs used in variants
                all_option_value_ids = set()
                for variant_data in product_data["variants"]:
                    all_option_value_ids.update(variant_data["option_values"])

                # Get option type IDs for these option values
                if all_option_value_ids:
                    option_type_records = await db_client.fetch(
                        """
                        SELECT DISTINCT ot.id, ot.name
                        FROM spree_option_types ot
                        JOIN spree_option_values ov ON ot.id = ov.option_type_id
                        WHERE ov.id = ANY($1::int[])
                        """,
                        list(all_option_value_ids),
                    )

                    # Insert product-option-type associations
                    for idx, option_type_record in enumerate(option_type_records, 1):
                        await db_client.execute(
                            """
                            INSERT INTO spree_product_option_types (product_id, option_type_id, position, created_at, updated_at)
                            VALUES ($1, $2, $3, $4, $5)
                            """,
                            product_id,
                            option_type_record["id"],
                            idx,
                            current_time,
                            current_time,
                        )

                # Insert master variant
                master_variant = await db_client.fetchrow(
                    """
                    INSERT INTO spree_variants (product_id, sku, created_at, updated_at, is_master, track_inventory, position)
                    VALUES ($1, $2, $3, $4, $5, $6, $7)
                    RETURNING id
                    """,
                    product_id,
                    product_data["sku"],
                    current_time,
                    current_time,
                    True,
                    True,
                    1,  # Master variant is always position 1
                )

                if not master_variant:
                    logger.error(f"Failed to insert master variant for product: {product_data['name']}")
                    continue

                master_variant_id = master_variant["id"]

                # Insert master variant price
                await db_client.execute(
                    """
                    INSERT INTO spree_prices (variant_id, amount, currency, created_at, updated_at)
                    VALUES ($1, $2, $3, $4, $5)
                    """,
                    master_variant_id,
                    product_data["master_price"],
                    "USD",
                    current_time,
                    current_time,
                )

                # Insert product variants (only if variants exist)
                if product_data["variants"]:  # Check if variants list is not empty
                    for position, variant_data in enumerate(product_data["variants"], 2):  # Start at 2 (master is 1)
                        variant_sku = f"{product_data['sku']}-{variant_data['sku_suffix']}"

                        variant_record = await db_client.fetchrow(
                            """
                            INSERT INTO spree_variants (product_id, sku, created_at, updated_at, is_master, track_inventory, position)
                            VALUES ($1, $2, $3, $4, $5, $6, $7)
                            RETURNING id
                            """,
                            product_id,
                            variant_sku,
                            current_time,
                            current_time,
                            False,
                            True,
                            position,
                        )

                        if not variant_record:
                            logger.error(f"Failed to insert variant {variant_sku}")
                            continue

                        variant_id = variant_record["id"]
                        total_variants += 1

                        # Insert variant price
                        await db_client.execute(
                            """
                            INSERT INTO spree_prices (variant_id, amount, currency, created_at, updated_at)
                            VALUES ($1, $2, $3, $4, $5)
                            """,
                            variant_id,
                            variant_data["price"],
                            "USD",
                            current_time,
                            current_time,
                        )

                        # Insert variant option values (avoid duplicates)
                        for option_value_id in variant_data["option_values"]:
                            # Check if this association already exists
                            existing = await db_client.fetchval(
                                """
                                SELECT 1 FROM spree_option_value_variants 
                                WHERE variant_id = $1 AND option_value_id = $2
                                """,
                                variant_id,
                                option_value_id,
                            )

                            if existing:
                                logger.warning(f"Option value {option_value_id} already associated with variant {variant_id}, skipping")
                                continue

                            try:
                                await db_client.execute(
                                    """
                                    INSERT INTO spree_option_value_variants (variant_id, option_value_id, created_at, updated_at)
                                    VALUES ($1, $2, $3, $4)
                                    """,
                                    variant_id,
                                    option_value_id,
                                    current_time,
                                    current_time,
                                )
                            except Exception as e:
                                if "duplicate key value violates unique constraint" in str(e):
                                    logger.warning(f"Option value {option_value_id} already associated with variant {variant_id}, skipping")
                                else:
                                    raise e

                        # Insert stock item for variant
                        await db_client.execute(
                            """
                            INSERT INTO spree_stock_items (variant_id, stock_location_id, count_on_hand, created_at, updated_at)
                            VALUES ($1, (SELECT id FROM spree_stock_locations LIMIT 1), $2, $3, $4)
                            """,
                            variant_id,
                            variant_data["stock_quantity"],
                            current_time,
                            current_time,
                        )

                # Note: Product properties insertion removed since property_values is not being generated

            except Exception as e:
                logger.error(f"Failed to process product {product_data['name']}: {e}")
                continue

        # Reset PostgreSQL sequences to prevent primary key conflicts
        if inserted_products > 0:
            logger.info("Resetting PostgreSQL sequences after manual ID insertions...")

            # Reset spree_products sequence
            await db_client.execute("SELECT setval('spree_products_id_seq', (SELECT COALESCE(MAX(id), 1) FROM spree_products))")

            # Reset spree_variants sequence
            await db_client.execute("SELECT setval('spree_variants_id_seq', (SELECT COALESCE(MAX(id), 1) FROM spree_variants))")

            # Reset spree_prices sequence
            await db_client.execute("SELECT setval('spree_prices_id_seq', (SELECT COALESCE(MAX(id), 1) FROM spree_prices))")

            # Reset spree_stock_items sequence
            await db_client.execute("SELECT setval('spree_stock_items_id_seq', (SELECT COALESCE(MAX(id), 1) FROM spree_stock_items))")

            logger.info("PostgreSQL sequences reset successfully")

        # Log summary
        total_products = await db_client.fetchval("SELECT COUNT(*) FROM spree_products")
        total_variants_db = await db_client.fetchval("SELECT COUNT(*) FROM spree_variants WHERE is_master = false")

        logger.succeed("Successfully processed products:")
        logger.succeed(f"  - {inserted_products} new products inserted")
        logger.succeed(f"  - {existing_products} existing products found")
        logger.succeed(f"  - {total_variants} new variants inserted")
        logger.succeed(f"  - {total_products} total products in database")
        logger.succeed(f"  - {total_variants_db} total variants in database")

    except Exception as e:
        logger.error(f"Error seeding products in database: {e}")
        raise
