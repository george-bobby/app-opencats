"""Stock item model and related functionality."""

import json
import random
from datetime import datetime

from faker import Faker
from pydantic import BaseModel, Field

from apps.spree.config.settings import settings
from apps.spree.utils.constants import PRODUCTS_FILE, STOCK_ITEMS_FILE, STOCK_LOCATIONS_FILE
from apps.spree.utils.database import db_client
from common.logger import Logger


logger = Logger()
fake = Faker()


class StockItem(BaseModel):
    """Stock item model for inventory tracking."""

    id: int = Field(description="Unique identifier for the stock item")  # noqa: A003, RUF100
    stock_location_id: int = Field(description="ID of the stock location")
    variant_id: int = Field(description="ID of the variant")
    count_on_hand: int = Field(description="Current quantity on hand")
    backorderable: bool = Field(description="Whether this item can be backordered", default=False)
    created_at: str = Field(description="Creation timestamp")
    updated_at: str = Field(description="Last update timestamp")
    deleted_at: str | None = Field(description="Deletion timestamp", default=None)
    position: int | None = Field(description="Position in the stock location", default=None)
    public_metadata: dict | None = Field(description="Public metadata", default=None)
    private_metadata: dict | None = Field(description="Private metadata", default=None)


async def generate_stock_items(stock_multiplier: int = 1):
    """Generate stock items for products across all stock locations."""
    logger.info("Generating stock items...")

    try:
        # Load stock locations data
        if not STOCK_LOCATIONS_FILE.exists():
            logger.error(f"Stock locations file not found at {STOCK_LOCATIONS_FILE}. Run generate stock locations command first.")
            return None

        with STOCK_LOCATIONS_FILE.open(encoding="utf-8") as f:
            stock_locations_data = json.load(f)
            stock_locations = stock_locations_data.get("stock_locations", [])

        if not stock_locations:
            logger.error("No stock locations found for stock item generation.")
            return None

        # Load products data to get variants
        if not PRODUCTS_FILE.exists():
            logger.error(f"Products file not found at {PRODUCTS_FILE}. Run generate products command first.")
            return None

        with PRODUCTS_FILE.open(encoding="utf-8") as f:
            products_data = json.load(f)
            products = products_data.get("products", [])

        if not products:
            logger.error("No products found for stock item generation.")
            return None

        # Extract all variant IDs from products
        variants = []
        for product in products:
            # Create a master variant entry using the product ID as variant ID
            # In Spree, the master variant typically has the same ID as the product
            variants.append({"id": product["id"], "product_id": product["id"], "is_master": True})

            # Add other variants if they exist
            if "variants" in product:
                for i, variant in enumerate(product["variants"]):
                    # Generate a variant ID if not present
                    # In Spree, variant IDs are typically product_id + offset
                    variant_id = variant.get("id", product["id"] + 1000 + i)
                    variants.append(
                        {"id": variant_id, "product_id": product["id"], "is_master": False, "position": variant.get("position", i + 1), "stock_quantity": variant.get("stock_quantity")}
                    )

        logger.info(f"Loaded {len(stock_locations)} stock locations and {len(variants)} variants for stock item generation.")

        # Generate stock items
        stock_items_list = []
        stock_item_id = 1

        # For each stock location
        for stock_location in stock_locations:
            location_id = stock_location["id"]
            is_default = stock_location.get("default", False)
            backorderable_default = stock_location.get("backorderable_default", False)

            # For each variant
            for variant in variants:
                variant_id = variant["id"]

                # Get stock quantity directly from the variant if available
                stock_quantity = variant.get("stock_quantity")

                # If stock quantity wasn't found in products.json, or for non-default locations,
                # distribute stock based on location type
                if stock_quantity is None or not is_default:
                    # For the default location, use higher base values if no stock_quantity was found
                    if is_default:
                        base_stock = random.randint(100, 500) * stock_multiplier
                    elif "Distribution" in stock_location["name"] or "Warehouse" in stock_location["name"]:
                        # Distribution centers and warehouses have good stock
                        base_stock = random.randint(80, 300) * stock_multiplier
                    elif "Fulfillment" in stock_location["name"]:
                        # Fulfillment centers have moderate stock
                        base_stock = random.randint(50, 200) * stock_multiplier
                    else:
                        # Other locations have minimal stock
                        base_stock = random.randint(25, 100) * stock_multiplier

                    # If we have a stock_quantity from products.json and this isn't the default location,
                    # use it as a reference to distribute stock proportionally
                    if stock_quantity is not None and not is_default:
                        # Distribute 10-50% of the default location's stock to other locations
                        distribution_factor = random.uniform(0.1, 0.5)
                        count_on_hand = int(stock_quantity * distribution_factor * stock_multiplier)
                    else:
                        count_on_hand = base_stock
                else:
                    # Use the stock quantity from products.json for the default location
                    count_on_hand = stock_quantity * stock_multiplier

                # Determine backorderable status
                # Master variants are more likely to be backorderable
                backorderable = backorderable_default or random.random() < 0.7 if variant["is_master"] else backorderable_default or random.random() < 0.4

                # Create timestamps
                created_dt = fake.date_time_between(start_date="-1y", end_date="-6m")
                created_at = created_dt.isoformat()  # Store as ISO string for JSON serialization
                updated_at = fake.date_time_between(start_date=created_dt, end_date="now").isoformat()  # Store as ISO string for JSON serialization

                # Create the stock item
                stock_item = StockItem(
                    id=stock_item_id,
                    stock_location_id=location_id,
                    variant_id=variant_id,
                    count_on_hand=count_on_hand,
                    backorderable=backorderable,
                    created_at=created_at,
                    updated_at=updated_at,
                    deleted_at=None,
                    position=None,
                    public_metadata=None,
                    private_metadata=None,
                )

                stock_items_list.append(stock_item.model_dump())
                stock_item_id += 1

        # Save to file
        stock_items_dict = {"stock_items": stock_items_list}

        settings.DATA_PATH.mkdir(parents=True, exist_ok=True)
        STOCK_ITEMS_FILE.parent.mkdir(parents=True, exist_ok=True)
        with STOCK_ITEMS_FILE.open("w", encoding="utf-8") as f:
            json.dump(stock_items_dict, f, indent=2, ensure_ascii=False)

        logger.succeed(f"Successfully generated and saved {len(stock_items_list)} stock items to {STOCK_ITEMS_FILE}")

        # Log some statistics
        items_by_location = {}
        for item in stock_items_list:
            location_id = item["stock_location_id"]
            items_by_location[location_id] = items_by_location.get(location_id, 0) + 1

        logger.info("Stock items by location:")
        for location in stock_locations:
            location_id = location["id"]
            item_count = items_by_location.get(location_id, 0)
            logger.info(f"  {location['name']}: {item_count} items")

        return stock_items_dict

    except Exception as e:
        logger.error(f"Error generating stock items: {e}")
        raise


async def seed_stock_items():
    """Insert stock items into the database."""
    logger.start("Processing stock items...")

    try:
        # First check what's already in the database
        existing_stock_items = await db_client.fetch("SELECT id, variant_id, stock_location_id FROM spree_stock_items WHERE deleted_at IS NULL")

        # Create map for quick lookup
        existing_ids = {item["id"] for item in existing_stock_items}

        logger.info(f"Found {len(existing_ids)} existing stock items in the database")

        # Get all stock locations
        stock_location_records = await db_client.fetch("SELECT id FROM spree_stock_locations")
        stock_location_map = {location["id"]: location["id"] for location in stock_location_records}

        # Get all variants
        variant_records = await db_client.fetch("SELECT id FROM spree_variants")
        variant_map = {variant["id"]: variant["id"] for variant in variant_records}

        # Check if we have stock items that need to be created
        variant_location_coverage = set()
        for existing_item in existing_stock_items:
            variant_location_coverage.add((existing_item["variant_id"], existing_item["stock_location_id"]))

        # Find missing combinations (variant_id, stock_location_id)
        missing_combinations = []
        for variant_id in variant_map:
            for location_id in stock_location_map:
                if (variant_id, location_id) not in variant_location_coverage:
                    missing_combinations.append((variant_id, location_id))

        if missing_combinations:
            logger.info(f"Found {len(missing_combinations)} missing variant-location combinations to create")

            # Find the highest existing ID to start from
            next_id = 1
            if existing_ids:
                next_id = max(existing_ids) + 1

            # Generate a timestamp as a datetime object (not a string)
            now = datetime.now()

            # Create stock items for missing combinations
            inserted_count = 0
            for variant_id, location_id in missing_combinations:
                try:
                    # Get location name to determine appropriate stock level
                    location_name = ""
                    for loc in stock_location_records:
                        if loc["id"] == location_id:
                            location_name = await db_client.fetchval("SELECT name FROM spree_stock_locations WHERE id = $1", location_id)
                            break

                    # Set stock levels based on location type (similar to generate function)
                    stock_multiplier = 1
                    if location_id == stock_location_records[0]["id"]:  # Default location
                        count_on_hand = random.randint(100, 500) * stock_multiplier
                    elif location_name and ("Distribution" in location_name or "Warehouse" in location_name):
                        # Distribution centers and warehouses have good stock
                        count_on_hand = random.randint(80, 300) * stock_multiplier
                    elif location_name and "Fulfillment" in location_name:
                        # Fulfillment centers have moderate stock
                        count_on_hand = random.randint(50, 200) * stock_multiplier
                    else:
                        # Other locations have minimal stock
                        count_on_hand = random.randint(25, 100) * stock_multiplier

                    # Only insert if the combination doesn't already exist
                    await db_client.execute(
                        """
                        INSERT INTO spree_stock_items (
                            id, stock_location_id, variant_id, count_on_hand, backorderable,
                            created_at, updated_at, deleted_at, public_metadata, private_metadata
                        ) VALUES (
                            $1, $2, $3, $4, $5, $6, $7, $8, $9, $10
                        )
                        """,
                        next_id,
                        location_id,
                        variant_id,
                        count_on_hand,  # Variable stock based on location type
                        True,  # Default backorderable
                        now,  # created_at
                        now,  # updated_at
                        None,  # deleted_at
                        None,  # public_metadata
                        None,  # private_metadata
                    )

                    inserted_count += 1
                    next_id += 1

                except Exception as e:
                    logger.error(f"Failed to insert stock item for variant {variant_id} at location {location_id}: {e}")
                    continue

            # Update the sequence
            if inserted_count > 0:
                await db_client.execute(f"SELECT setval('spree_stock_items_id_seq', {next_id}, true)")
                logger.succeed(f"Successfully inserted {inserted_count} new stock items")
            else:
                logger.info("No new stock items were inserted")

        else:
            logger.info("All variants already have stock items at all locations")

        return True

    except Exception as e:
        logger.error(f"Error processing stock items: {e}")
        raise
