"""Shipping rate model and related functionality."""

import json
import random
from datetime import datetime

from pydantic import BaseModel

from apps.spree.utils.constants import SHIPMENTS_FILE, SHIPPING_METHODS_FILE, SHIPPING_RATES_FILE, TAX_RATES_FILE
from apps.spree.utils.database import db_client
from common.logger import Logger


logger = Logger()


class ShippingRate(BaseModel):
    """Shipping rate model for shipments."""

    id: int  # noqa: A003, RUF100
    shipment_id: int
    shipping_method_id: int
    selected: bool
    cost: float
    tax_rate_id: int | None = None
    created_at: str
    updated_at: str


async def generate_shipping_rates():
    """Generate shipping rates for existing shipments and save to JSON file."""
    logger.info("Generating shipping rates for shipments...")

    try:
        # Load shipments from JSON file
        if not SHIPMENTS_FILE.exists():
            logger.error(f"Shipments file not found at {SHIPMENTS_FILE}. Run generate orders command first.")
            return

        with SHIPMENTS_FILE.open(encoding="utf-8") as f:
            shipments_data = json.load(f)
            shipments = shipments_data.get("shipments", [])

        if not shipments:
            logger.error("No shipments found for shipping rate generation.")
            return

        logger.info(f"Loaded {len(shipments)} shipments for shipping rate generation")

        # Get available shipping methods from JSON file
        if not SHIPPING_METHODS_FILE.exists():
            logger.error(f"Shipping methods file not found at {SHIPPING_METHODS_FILE}. Run generate shipping methods command first.")
            return

        with SHIPPING_METHODS_FILE.open(encoding="utf-8") as f:
            shipping_methods_data = json.load(f)
            shipping_methods = shipping_methods_data.get("shipping_methods", [])

        if not shipping_methods:
            logger.error("No shipping methods found in shipping methods file.")
            return

        logger.info(f"Found {len(shipping_methods)} shipping methods in shipping methods file")

        # Get available tax rates from JSON file
        tax_rates = []
        if not TAX_RATES_FILE.exists():
            logger.warning(f"Tax rates file not found at {TAX_RATES_FILE}. Shipping rates will not have tax rates.")
        else:
            with TAX_RATES_FILE.open(encoding="utf-8") as f:
                tax_rates_data = json.load(f)
                tax_rates = tax_rates_data.get("tax_rates", [])

            if not tax_rates:
                logger.warning("No tax rates found in tax rates file.")
            else:
                logger.info(f"Found {len(tax_rates)} tax rates in tax rates file")

        # Create shipping rates for each shipment
        shipping_rates_list = []
        shipping_rate_id = 1

        for shipment in shipments:
            shipment_id = shipment["id"]
            shipment_state = shipment["state"]
            shipment_cost = shipment["cost"]

            # Skip canceled shipments
            if shipment_state == "canceled":
                continue

            # Get 2-4 random shipping methods for this shipment
            num_methods = random.randint(2, min(4, len(shipping_methods)))
            selected_methods = random.sample(shipping_methods, num_methods)

            # Sort by shipping method id to ensure consistent order
            selected_methods.sort(key=lambda x: x["id"])

            # Choose a random shipping method as the selected one
            selected_index = random.randint(0, num_methods - 1)

            # Generate creation and update timestamps
            created_at = datetime.fromisoformat(shipment["created_at"].replace(" ", "T")) if isinstance(shipment["created_at"], str) else shipment["created_at"]
            updated_at = datetime.fromisoformat(shipment["updated_at"].replace(" ", "T")) if isinstance(shipment["updated_at"], str) else shipment["updated_at"]

            for i, method in enumerate(selected_methods):
                # Use shipment cost for the selected method
                if i == selected_index:
                    cost = shipment_cost
                else:
                    # Generate a different cost for non-selected methods
                    # (between 80% and 150% of the shipment cost)
                    min_cost = max(3.99, shipment_cost * 0.8)
                    max_cost = shipment_cost * 1.5
                    cost = round(random.uniform(min_cost, max_cost), 2)

                # Get a random tax rate (if available)
                tax_rate_id = None
                if tax_rates and random.random() < 0.3:  # 30% chance to have a tax rate
                    # For now, we'll set tax_rate_id to None
                    # During seeding, we can optionally match tax rates by name/category if needed
                    tax_rate_id = None

                # Create the shipping rate
                shipping_rate = ShippingRate(
                    id=shipping_rate_id,
                    shipment_id=shipment_id,
                    shipping_method_id=method["id"],
                    selected=(i == selected_index),
                    cost=cost,
                    tax_rate_id=tax_rate_id,
                    created_at=created_at.isoformat() if isinstance(created_at, datetime) else created_at,
                    updated_at=updated_at.isoformat() if isinstance(updated_at, datetime) else updated_at,
                )

                shipping_rates_list.append(shipping_rate.model_dump())
                shipping_rate_id += 1

        logger.succeed(f"Successfully generated {len(shipping_rates_list)} shipping rates for {len(shipments)} shipments")

        # Save to JSON file
        shipping_rates_data = {"shipping_rates": shipping_rates_list}
        with SHIPPING_RATES_FILE.open("w", encoding="utf-8") as f:
            json.dump(shipping_rates_data, f, indent=2, ensure_ascii=False)

        logger.info(f"Shipping rates saved to {SHIPPING_RATES_FILE}")

    except Exception as e:
        logger.error(f"Error generating shipping rates: {e}")
        raise


async def seed_shipping_rates():
    """Insert shipping rates into the database."""
    logger.start("Inserting shipping rates into spree_shipping_rates table...")

    try:
        # Load shipping rates from JSON file
        if not SHIPPING_RATES_FILE.exists():
            logger.error(f"Shipping rates file not found at {SHIPPING_RATES_FILE}. Run generate shipping rates command first.")
            return

        with SHIPPING_RATES_FILE.open(encoding="utf-8") as f:
            shipping_rates_data = json.load(f)

        shipping_rates = shipping_rates_data.get("shipping_rates", [])
        if not shipping_rates:
            logger.error("No shipping rates generated")
            return

        logger.info(f"Generated {len(shipping_rates)} shipping rates to insert")

        # Get actual shipment IDs from database
        shipment_map = {}
        shipment_records = await db_client.fetch("SELECT id FROM spree_shipments")
        for shipment in shipment_records:
            shipment_map[shipment["id"]] = shipment["id"]

        # Get actual shipping method IDs from database
        method_map = {}
        method_records = await db_client.fetch("SELECT id FROM spree_shipping_methods")
        for method in method_records:
            method_map[method["id"]] = method["id"]

        # Insert shipping rates
        inserted_count = 0
        skipped_count = 0
        for shipping_rate in shipping_rates:
            try:
                # Verify shipment exists
                if shipping_rate["shipment_id"] not in shipment_map:
                    skipped_count += 1
                    continue

                # Verify shipping method exists
                if shipping_rate["shipping_method_id"] not in method_map:
                    skipped_count += 1
                    continue

                # Convert datetime strings to actual datetime objects
                if isinstance(shipping_rate["created_at"], str):
                    shipping_rate["created_at"] = datetime.fromisoformat(shipping_rate["created_at"].replace(" ", "T"))
                if isinstance(shipping_rate["updated_at"], str):
                    shipping_rate["updated_at"] = datetime.fromisoformat(shipping_rate["updated_at"].replace(" ", "T"))

                # Insert shipping rate with explicit ID, ignore duplicates
                await db_client.execute(
                    """
                    INSERT INTO spree_shipping_rates (
                        id, shipment_id, shipping_method_id, selected, cost, tax_rate_id,
                        created_at, updated_at
                    ) VALUES (
                        $1, $2, $3, $4, $5, $6, $7, $8
                    )
                    ON CONFLICT (id) DO NOTHING
                    """,
                    shipping_rate["id"],
                    shipping_rate["shipment_id"],
                    shipping_rate["shipping_method_id"],
                    shipping_rate["selected"],
                    shipping_rate["cost"],
                    shipping_rate["tax_rate_id"],
                    shipping_rate["created_at"],
                    shipping_rate["updated_at"],
                )

                inserted_count += 1

            except Exception as e:
                logger.error(f"Failed to insert shipping rate {shipping_rate['id']}: {e}")
                skipped_count += 1
                continue

        if skipped_count > 0:
            logger.succeed(f"Successfully inserted {inserted_count} shipping rates into the database (skipped {skipped_count} existing/duplicate records)")
        else:
            logger.succeed(f"Successfully inserted {inserted_count} shipping rates into the database")

        # Update the sequence to avoid future conflicts with auto-generated IDs
        if inserted_count > 0:
            max_id = max(shipping_rate["id"] for shipping_rate in shipping_rates)
            await db_client.execute(f"SELECT setval('spree_shipping_rates_id_seq', {max_id}, true)")

    except Exception as e:
        logger.error(f"Error seeding shipping rates in database: {e}")
        raise
