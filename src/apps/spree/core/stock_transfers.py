"""Stock transfer generation and seeding for Spree."""

import json
import random
from datetime import datetime
from pathlib import Path

from faker import Faker
from pydantic import BaseModel, Field

from apps.spree.config.settings import settings
from apps.spree.utils.constants import PRODUCTS_FILE, STOCK_LOCATIONS_FILE, STOCK_TRANSFERS_FILE
from apps.spree.utils.database import db_client
from common.logger import Logger


logger = Logger()
fake = Faker()


class StockMovement(BaseModel):
    """Individual stock movement model."""

    stock_item_id: int = Field(description="Stock item ID that this movement affects")
    quantity: int = Field(description="Quantity being transferred (negative for source, positive for destination)")
    action: str | None = Field(description="Action type", default=None)
    originator_type: str = Field(description="Type of the originator", default="Spree::StockTransfer")
    originator_id: int = Field(description="ID of the originator")


class StockTransfer(BaseModel):
    """Individual stock transfer model."""

    id: int = Field(description="Unique identifier for the stock transfer")  # noqa: A003, RUF100
    reference: str | None = Field(description="Optional reference code for the stock transfer")
    internal_name: str = Field(description="Internal name/description of the transfer")
    source_location_id: int | None = Field(description="Source stock location ID", default=None)
    destination_location_id: int = Field(description="Destination stock location ID")
    number: str = Field(description="Unique transfer number")
    stock_movements: list[StockMovement] = Field(description="Stock movements associated with this transfer", default_factory=list)


class StockTransferResponse(BaseModel):
    """Response format for generated stock transfers."""

    stock_transfers: list[StockTransfer]


async def generate_stock_transfers(number_of_stock_transfers: int):
    """Generate realistic stock transfers for a pet supplies eCommerce store."""

    logger.info(f"Generating {number_of_stock_transfers} stock transfers for pet supplies store...")

    try:
        # Load stock locations to use as sources and destinations
        if not STOCK_LOCATIONS_FILE.exists():
            logger.error(f"Stock locations file not found at {STOCK_LOCATIONS_FILE}")
            raise FileNotFoundError("Stock locations file not found")

        with Path.open(STOCK_LOCATIONS_FILE, encoding="utf-8") as f:
            stock_locations_data = json.load(f)

        stock_locations = stock_locations_data.get("stock_locations", [])
        if not stock_locations:
            logger.error("No stock locations found in stock locations file")
            raise ValueError("No stock locations available")

        logger.info(f"Loaded {len(stock_locations)} stock locations for transfers")

        # Load products to use for transfers
        if not PRODUCTS_FILE.exists():
            logger.error(f"Products file not found at {PRODUCTS_FILE}")
            raise FileNotFoundError("Products file not found")

        with Path.open(PRODUCTS_FILE, encoding="utf-8") as f:
            products_data = json.load(f)

        products = products_data.get("products", [])
        if not products:
            logger.error("No products found in products file")
            raise ValueError("No products available")

        logger.info(f"Loaded {len(products)} products for transfers")

        # Extract variants from products
        variants = []
        for product in products:
            # Add master variant
            variants.append({"id": product.get("id"), "sku": product.get("sku"), "product_name": product.get("name"), "is_master": True})

            # Add regular variants
            for variant in product.get("variants", []):
                variant_id = variant.get("id", 0)  # May need to generate IDs if not present
                variants.append(
                    {
                        "id": variant_id,
                        "sku": f"{product.get('sku')}-{variant.get('sku_suffix')}",
                        "product_name": f"{product.get('name')} ({variant.get('sku_suffix')})",
                        "is_master": False,
                        "stock_quantity": variant.get("stock_quantity", 100),
                    }
                )

        if not variants:
            logger.error("No variants found in products")
            raise ValueError("No variants available")

        logger.info(f"Extracted {len(variants)} variants for transfers")

        # Define operational reasons for stock transfers
        operational_reasons = [
            "Replenishment",
            "Rebalancing",
            "Testing new region",
            "Seasonal preparation",
            "Inventory adjustment",
            "New store opening",
            "Emergency resupply",
            "Overstock redistribution",
            "Returns processing",
            "Quality control check",
        ]

        # Generate stock transfers
        stock_transfers = []

        for i in range(1, number_of_stock_transfers + 1):
            # Pick a random destination location (not the default one)
            non_default_locations = [loc for loc in stock_locations if not loc.get("default", False)]
            destination_location = random.choice(non_default_locations if non_default_locations else stock_locations)

            # Determine if we'll use a source location (80% chance)
            use_source = random.random() < 0.8

            # If using a source, pick a different location than the destination
            source_location = None
            source_location_id = None
            if use_source:
                source_candidates = [loc for loc in stock_locations if loc != destination_location]
                if source_candidates:
                    source_location = random.choice(source_candidates)
                    source_location_id = source_location.get("id")  # Try to get the ID from the JSON
                    # If ID is missing in the JSON, use the index+1 as fallback
                    if source_location_id is None:
                        source_location_id = stock_locations.index(source_location) + 1

            # Generate a reference code (70% chance to have one)
            reference = None
            if random.random() < 0.7:
                # Create reference patterns based on operational reasons
                reason = random.choice(operational_reasons)
                reason_code = reason.split()[0]
                location_code = destination_location["name"].split()[-1][:3].upper()
                quarter = f"Q{random.randint(1, 4)}"
                reference = f"{reason_code}-{location_code}-{quarter}"

            # Generate an internal name
            city = destination_location["city"].lower()
            transfer_type = random.choice(["restock", "resupply", "transfer", "movement", "shift", "delivery", "adjustment", "relocation", "distribution", "allocation"])

            month = random.choice(["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"])

            product_focus = random.choice(["treats", "toys", "food", "accessories", "beds", "carriers", "supplies", "chews", "grooming", "training", "multi-sku"])

            internal_name = f"{city}-{product_focus}-{transfer_type}"
            if random.random() < 0.4:
                internal_name += f"-{month}"

            transfer_number = fake.numerify("T#####")

            # Determine how many different variants to include (usually 1-3)
            variant_count = 1
            if random.random() < 0.25:  # 25% chance for multiple variants
                variant_count = random.randint(2, 5)

            selected_variants = random.sample(variants, min(variant_count, len(variants)))

            # Create the stock movements for each variant
            stock_movements = []
            for j, variant in enumerate(selected_variants):
                # Generate a realistic quantity based on the variant type
                quantity = random.randint(10, 150)
                if "bulk" in variant.get("product_name", "").lower():
                    quantity = random.randint(50, 300)
                elif "pack" in variant.get("product_name", "").lower():
                    quantity = random.randint(20, 80)

                # For certain products, use specific quantities
                if "treats" in variant.get("product_name", "").lower():
                    quantity = random.randint(30, 70)
                elif "food" in variant.get("product_name", "").lower() or "kibble" in variant.get("product_name", "").lower():
                    quantity = random.randint(50, 120)

                # Create stock movements
                if use_source:
                    # Source movement (negative quantity)
                    stock_movements.append(
                        StockMovement(
                            stock_item_id=1000 + i * 10 + j * 2,  # Placeholder IDs, will be replaced during seeding
                            quantity=-quantity,
                            action=None,
                            originator_type="Spree::StockTransfer",
                            originator_id=i,
                        )
                    )

                # Destination movement (positive quantity)
                stock_movements.append(
                    StockMovement(
                        stock_item_id=1000 + i * 10 + j * 2 + 1,  # Placeholder IDs, will be replaced during seeding
                        quantity=quantity,
                        action=None,
                        originator_type="Spree::StockTransfer",
                        originator_id=i,
                    )
                )

            # Create the stock transfer - make sure we have valid IDs
            # If ID is missing in the JSON, use the index+1 as fallback
            dest_location_id = destination_location.get("id")
            if dest_location_id is None:
                dest_location_id = stock_locations.index(destination_location) + 1

            stock_transfer = StockTransfer(
                id=i,
                reference=reference,
                internal_name=internal_name,
                source_location_id=source_location_id,
                destination_location_id=dest_location_id,  # Ensure we always have a valid integer
                number=transfer_number,
                stock_movements=stock_movements,
            )

            stock_transfers.append(stock_transfer)
            logger.info(f"Generated stock transfer {i}/{number_of_stock_transfers}: {internal_name}")

        # Save to file
        stock_transfers_data = {"stock_transfers": [st.model_dump() for st in stock_transfers]}

        settings.DATA_PATH.mkdir(parents=True, exist_ok=True)
        STOCK_TRANSFERS_FILE.parent.mkdir(parents=True, exist_ok=True)
        with Path.open(STOCK_TRANSFERS_FILE, "w", encoding="utf-8") as f:
            json.dump(stock_transfers_data, f, indent=2, ensure_ascii=False)

        logger.succeed(f"Successfully generated and saved {len(stock_transfers)} stock transfers to {STOCK_TRANSFERS_FILE}")

        return stock_transfers_data

    except Exception as e:
        logger.error(f"Error generating stock transfers: {e}")
        raise


async def seed_stock_transfers():
    """Seed stock transfers into the database."""

    logger.start("Inserting stock transfers into spree_stock_transfers table...")

    try:
        # Load stock transfers from JSON file
        if not STOCK_TRANSFERS_FILE.exists():
            logger.error(f"Stock transfers file not found at {STOCK_TRANSFERS_FILE}. Run generate command first.")
            raise FileNotFoundError("Stock transfers file not found")

        with Path.open(STOCK_TRANSFERS_FILE, encoding="utf-8") as f:
            data = json.load(f)

        stock_transfers = data.get("stock_transfers", [])
        logger.info(f"Loaded {len(stock_transfers)} stock transfers from {STOCK_TRANSFERS_FILE}")

        current_time = datetime.now()

        # Get all stock locations from database
        stock_locations_data = await db_client.fetch("SELECT id, name FROM spree_stock_locations")
        stock_location_map = {loc["id"]: loc["name"] for loc in stock_locations_data}
        logger.info(f"Found {len(stock_location_map)} stock locations in database")

        # Load stock locations from JSON file for creating stock items
        stock_locations = []
        if STOCK_LOCATIONS_FILE.exists():
            try:
                with Path.open(STOCK_LOCATIONS_FILE, encoding="utf-8") as f:
                    stock_locations_json = json.load(f)
                stock_locations = stock_locations_json.get("stock_locations", [])
                logger.info(f"Loaded {len(stock_locations)} stock locations from {STOCK_LOCATIONS_FILE}")
            except Exception as e:
                logger.warning(f"Could not load stock locations from {STOCK_LOCATIONS_FILE}: {e}")
                logger.info("Using database stock locations as fallback")
                # Convert database records to format matching the JSON structure
                stock_locations = [{"id": loc["id"], "name": loc["name"]} for loc in stock_locations_data]

        # Get all variants and their stock items
        variants = await db_client.fetch(
            """
            SELECT v.id, v.sku, p.name as product_name, v.is_master
            FROM spree_variants v
            JOIN spree_products p ON v.product_id = p.id
        """
        )

        variant_map = {v["id"]: {"sku": v["sku"], "product_name": v["product_name"], "is_master": v["is_master"]} for v in variants}
        logger.info(f"Found {len(variant_map)} variants in database")

        # Get stock items (mapping variants to stock locations)
        # Note: Only get active stock items (where deleted_at IS NULL)
        stock_items = await db_client.fetch(
            """
            SELECT si.id, si.variant_id, si.stock_location_id, si.count_on_hand
            FROM spree_stock_items si
            WHERE si.deleted_at IS NULL
        """
        )

        stock_item_map = {}
        for si in stock_items:
            key = (si["variant_id"], si["stock_location_id"])
            stock_item_map[key] = {"id": si["id"], "count": si["count_on_hand"]}

        logger.info(f"Found {len(stock_item_map)} stock items in database")

        # If we have variants but not enough stock items (stock in different locations),
        # let's create them - one product should have stock in multiple locations
        if variants and stock_locations and len(stock_item_map) < len(variants) * len(stock_locations):
            logger.info("Ensuring all variants have stock items in all locations...")

            # Iterate through all variants and stock locations
            for variant in variants:
                variant_id = variant["id"]

                for stock_location in stock_locations:
                    stock_location_id = stock_location["id"]
                    key = (variant_id, stock_location_id)

                    # If this variant doesn't have a stock item in this location, create one
                    if key not in stock_item_map:
                        # Generate random initial stock (between 10-200)
                        initial_stock = random.randint(10, 200)

                        # Insert the stock item
                        stock_item = await db_client.fetchrow(
                            """
                            INSERT INTO spree_stock_items (
                                variant_id, stock_location_id, count_on_hand, 
                                created_at, updated_at, backorderable
                            )
                            VALUES ($1, $2, $3, $4, $5, $6)
                            RETURNING id, count_on_hand
                        """,
                            variant_id,
                            stock_location_id,
                            initial_stock,
                            current_time,
                            current_time,
                            False,  # backorderable = false by default
                        )

                        if stock_item:
                            # Add to our map
                            stock_item_map[key] = {"id": stock_item["id"], "count": stock_item["count_on_hand"]}
                            logger.info(f"Created stock item for variant {variant_id} in location {stock_location_id} with {initial_stock} units")

            # Update our count of stock items
            logger.info(f"Now have {len(stock_item_map)} stock items across all locations")

        # Process each stock transfer
        inserted_transfers = 0
        existing_transfers = 0
        skipped_transfers = 0

        for transfer_data in stock_transfers:
            try:
                # Check if transfer already exists by number
                existing_transfer = await db_client.fetchrow("SELECT id FROM spree_stock_transfers WHERE number = $1", transfer_data["number"])

                if existing_transfer:
                    existing_transfers += 1
                    logger.info(f"Found existing stock transfer: {transfer_data['number']}")
                    continue

                # Verify stock locations
                destination_id = transfer_data["destination_location_id"]
                source_id = transfer_data.get("source_location_id")

                if destination_id not in stock_location_map:
                    logger.warning(f"Destination location ID {destination_id} not found, skipping transfer {transfer_data['number']}")
                    skipped_transfers += 1
                    continue

                if source_id is not None and source_id not in stock_location_map:
                    logger.warning(f"Source location ID {source_id} not found, skipping transfer {transfer_data['number']}")
                    skipped_transfers += 1
                    continue

                # Insert stock transfer
                transfer_record = await db_client.fetchrow(
                    """
                    INSERT INTO spree_stock_transfers (
                        type, reference, source_location_id, destination_location_id,
                        created_at, updated_at, number
                    )
                    VALUES ($1, $2, $3, $4, $5, $6, $7)
                    RETURNING id
                    """,
                    None,  # type
                    transfer_data["reference"],
                    transfer_data.get("source_location_id"),
                    transfer_data["destination_location_id"],
                    current_time,
                    current_time,
                    transfer_data["number"],
                )

                if not transfer_record:
                    logger.error(f"Failed to insert stock transfer: {transfer_data['number']}")
                    skipped_transfers += 1
                    continue

                transfer_id = transfer_record["id"]
                inserted_transfers += 1

                # Process stock movements
                if transfer_data.get("stock_movements"):
                    # Use pre-generated stock movements but pair them with real variant IDs from the database
                    stock_movements = transfer_data.get("stock_movements", [])

                    # Get list of available variants
                    variant_ids = list(variant_map.keys())
                    if not variant_ids:
                        logger.warning(f"No variants available to create stock movements for transfer {transfer_data['number']}")
                        continue

                    # We need to pick random variants that have stock items in both locations
                    usable_variants = []
                    for variant_id in variant_ids:
                        # For transfers with source, check both source and destination
                        if source_id is not None:
                            source_key = (variant_id, source_id)
                            dest_key = (variant_id, destination_id)
                            if source_key in stock_item_map and dest_key in stock_item_map:
                                usable_variants.append(
                                    {"variant_id": variant_id, "source_stock_item_id": stock_item_map[source_key]["id"], "dest_stock_item_id": stock_item_map[dest_key]["id"]}
                                )
                        else:
                            # For transfers without source, just check destination
                            dest_key = (variant_id, destination_id)
                            if dest_key in stock_item_map:
                                usable_variants.append({"variant_id": variant_id, "source_stock_item_id": None, "dest_stock_item_id": stock_item_map[dest_key]["id"]})

                    if not usable_variants:
                        logger.warning(f"No usable variants with stock items in required locations for transfer {transfer_data['number']}")
                        continue

                    # Count how many variant-pairs we need to create (half the number of movements)
                    variant_pair_count = max(1, len(stock_movements) // 2)

                    # Make sure we don't exceed available variants
                    variant_pair_count = min(variant_pair_count, len(usable_variants))

                    # Create appropriate number of movements
                    selected_variants = random.sample(usable_variants, variant_pair_count)

                    for variant_info in selected_variants:
                        variant_id = variant_info["variant_id"]
                        source_stock_item_id = variant_info["source_stock_item_id"]
                        dest_stock_item_id = variant_info["dest_stock_item_id"]

                        # Use a realistic quantity (between 10-50)
                        quantity = random.randint(10, 50)

                        # First create source movement if applicable
                        if source_id is not None and source_stock_item_id is not None:
                            source_key = (variant_id, source_id)

                            # Insert source movement (negative quantity)
                            await db_client.execute(
                                """
                                INSERT INTO spree_stock_movements (
                                    stock_item_id, quantity, action, created_at, updated_at,
                                    originator_type, originator_id
                                )
                                VALUES ($1, $2, $3, $4, $5, $6, $7)
                                """,
                                source_stock_item_id,
                                -quantity,
                                None,  # action
                                current_time,
                                current_time,
                                "Spree::StockTransfer",
                                transfer_id,
                            )

                            # Update count_on_hand for source stock item
                            new_count = stock_item_map[source_key]["count"] - quantity
                            await db_client.execute(
                                "UPDATE spree_stock_items SET count_on_hand = $1, updated_at = $2 WHERE id = $3",
                                max(0, new_count),  # Ensure count doesn't go below 0
                                current_time,
                                source_stock_item_id,
                            )

                            # Update our local map
                            stock_item_map[source_key]["count"] = max(0, new_count)

                        # Then create destination movement
                        if dest_stock_item_id is not None:
                            dest_key = (variant_id, destination_id)

                            # Insert destination movement (positive quantity)
                            await db_client.execute(
                                """
                                INSERT INTO spree_stock_movements (
                                    stock_item_id, quantity, action, created_at, updated_at,
                                    originator_type, originator_id
                                )
                                VALUES ($1, $2, $3, $4, $5, $6, $7)
                                """,
                                dest_stock_item_id,
                                quantity,
                                None,  # action
                                current_time,
                                current_time,
                                "Spree::StockTransfer",
                                transfer_id,
                            )

                            # Update count_on_hand for destination stock item
                            new_count = stock_item_map[dest_key]["count"] + quantity
                            await db_client.execute(
                                "UPDATE spree_stock_items SET count_on_hand = $1, updated_at = $2 WHERE id = $3",
                                max(0, new_count),  # Ensure count doesn't go below 0
                                current_time,
                                dest_stock_item_id,
                            )

                            # Update our local map
                            stock_item_map[dest_key]["count"] = max(0, new_count)

                        # variant_name = variant_map[variant_id]["product_name"]
                        # if source_id is not None:
                        #     logger.info(f"Transferred {quantity} of {variant_name} from {stock_location_map.get(source_id)} to {stock_location_map.get(destination_id)}")
                        # else:
                        #     logger.info(f"Added {quantity} of {variant_name} to {stock_location_map.get(destination_id)}")
                else:
                    variant_count = random.randint(1, 3)
                    random_variants = random.sample(list(variant_map.keys()), min(variant_count, len(variant_map)))

                    for variant_id in random_variants:
                        quantity = random.randint(10, 100)

                        create_movements = True

                        source_stock_item_id = None
                        if source_id is not None:
                            source_stock_item_key = (variant_id, source_id)
                            if source_stock_item_key not in stock_item_map:
                                create_movements = False
                            else:
                                source_stock_item_id = stock_item_map[source_stock_item_key]["id"]

                        # Check for destination stock item
                        dest_stock_item_key = (variant_id, destination_id)
                        if dest_stock_item_key not in stock_item_map:
                            create_movements = False
                        else:
                            dest_stock_item_id = stock_item_map[dest_stock_item_key]["id"]

                        if not create_movements:
                            continue

                        if source_id is not None:
                            await db_client.execute(
                                """
                                INSERT INTO spree_stock_movements (
                                    stock_item_id, quantity, action, created_at, updated_at,
                                    originator_type, originator_id
                                )
                                VALUES ($1, $2, $3, $4, $5, $6, $7)
                                """,
                                source_stock_item_id,
                                -quantity,
                                None,  # action
                                current_time,
                                current_time,
                                "Spree::StockTransfer",
                                transfer_id,
                            )

                            new_count = stock_item_map[source_stock_item_key]["count"] - quantity
                            await db_client.execute(
                                "UPDATE spree_stock_items SET count_on_hand = $1, updated_at = $2 WHERE id = $3",
                                max(0, new_count),  # Ensure count doesn't go below 0
                                current_time,
                                source_stock_item_id,
                            )

                            # Update our local map
                            stock_item_map[source_stock_item_key]["count"] = max(0, new_count)

                        # Second, create destination movement (positive quantity)
                        await db_client.execute(
                            """
                            INSERT INTO spree_stock_movements (
                                stock_item_id, quantity, action, created_at, updated_at,
                                originator_type, originator_id
                            )
                            VALUES ($1, $2, $3, $4, $5, $6, $7)
                            """,
                            dest_stock_item_id,
                            quantity,
                            None,  # action
                            current_time,
                            current_time,
                            "Spree::StockTransfer",
                            transfer_id,
                        )

                        # Update count_on_hand for destination stock item
                        new_count = stock_item_map[dest_stock_item_key]["count"] + quantity
                        await db_client.execute("UPDATE spree_stock_items SET count_on_hand = $1, updated_at = $2 WHERE id = $3", new_count, current_time, dest_stock_item_id)

                        # Update our local map
                        stock_item_map[dest_stock_item_key]["count"] = new_count

                        # Log the transfer info
                        variant_info = variant_map[variant_id]
                        if source_id is not None:
                            logger.info(f"Transferred {quantity} of {variant_info['product_name']} from {stock_location_map.get(source_id)} to {stock_location_map.get(destination_id)}")
                        else:
                            logger.info(f"Added {quantity} of {variant_info['product_name']} to {stock_location_map.get(destination_id)}")

                # dest_name = stock_location_map.get(destination_id, f"Location ID: {destination_id}")
                # source_info = f" from {stock_location_map.get(source_id)}" if source_id is not None else ""
                # logger.info(f"Inserted stock transfer: {transfer_data['internal_name']} - {dest_name}{source_info}")

            except Exception as e:
                logger.error(f"Failed to process stock transfer {transfer_data.get('number')}: {e}")
                skipped_transfers += 1
                continue

        # Log summary
        total_transfers = await db_client.fetchval("SELECT COUNT(*) FROM spree_stock_transfers")

        logger.succeed("Successfully processed stock transfers:")
        logger.succeed(f"  - {inserted_transfers} new stock transfers inserted")
        logger.succeed(f"  - {existing_transfers} existing stock transfers found")
        logger.succeed(f"  - {skipped_transfers} stock transfers skipped due to errors")
        logger.succeed(f"  - {total_transfers} total stock transfers in database")

        # Log stock movement statistics
        total_movements = await db_client.fetchval("SELECT COUNT(*) FROM spree_stock_movements WHERE originator_type = 'Spree::StockTransfer'")
        logger.succeed(f"  - {total_movements} stock movements created")

    except Exception as e:
        logger.error(f"Error seeding stock transfers in database: {e}")
        raise
