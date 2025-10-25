import random
from typing import Any

from faker import Faker

from apps.odoosales.utils.odoo import OdooClient
from common.logger import logger


faker = Faker("en_US")


async def _process_adjustment_chunk(
    items_chunk: list[tuple[dict[str, Any], dict[str, Any]]],
    chunk_id: int,
):
    """Processes a chunk of physical adjustments."""
    async with OdooClient() as client:
        for prod, location in items_chunk:
            try:
                # scheduled_date = faker.date_time_between(start_date="-3M", end_date="now")

                # Get on-hand quantity
                quants = await client.search_read(
                    "stock.quant",
                    domain=[
                        ["product_id", "=", prod["id"]],
                        ["location_id", "=", location["id"]],
                    ],
                    fields=["available_quantity"],
                    limit=1,
                )
                on_hand = quants[0]["available_quantity"] if quants else random.randint(10, 200)

                # Simulate counted quantity (may differ)
                counted = max(0, on_hand + random.randint(-5, 5))

                # Find or create/update stock.quant for this product/location
                quant = await client.search_read(
                    "stock.quant",
                    domain=[
                        ("product_id", "=", prod["id"]),
                        ("location_id", "=", location["id"]),
                    ],
                    fields=["id", "quantity"],
                    limit=1,
                )
                if quant:
                    quant_id = quant[0]["id"]
                    await client.write(
                        "stock.quant",
                        quant_id,
                        {"inventory_quantity": counted},
                    )
                else:
                    await client.create(
                        "stock.quant",
                        {
                            "product_id": prod["id"],
                            "location_id": location["id"],
                            "inventory_quantity": counted,
                        },
                    )
            except Exception as e:
                logger.error(f"Thread {chunk_id}: Error processing adjustment for product {prod.get('name')} at location {location.get('name')}: {e}")


async def insert_physical_adjustments():
    """Inserts physical adjustments in parallel."""
    logger.start("Starting physical adjustments insertion...")
    async with OdooClient() as client:
        # Get storable products by joining with product.template
        tmpl_data = await client.search_read(
            "product.template",
            domain=[("type", "=", "consu"), ("id", ">", 2)],
            fields=["id", "uom_id"],
        )

        tmpl_data = tmpl_data[: int(len(tmpl_data) * 0.3)]  # Limit to 30% of templates

        storable_tmpl_ids = [t["id"] for t in tmpl_data]
        products = await client.search_read(
            "product.product",
            domain=[["product_tmpl_id", "in", storable_tmpl_ids]],
            fields=["id", "name", "product_tmpl_id"],
        )
        if not products:
            logger.error("No storable products found.")
            return

        # Get internal warehouse locations
        locations = await client.search_read(
            "stock.location",
            domain=[("usage", "=", "internal")],
            fields=["id", "name", "complete_name"],
        )
        if not locations:
            logger.error("No warehouse locations found.")
            return

        items_to_process = [(prod, loc) for prod in products for loc in locations]

        for prod, location in items_to_process:
            try:
                # scheduled_date = faker.date_time_between(start_date="-3M", end_date="now")

                # Get on-hand quantity
                quants = await client.search_read(
                    "stock.quant",
                    domain=[
                        ["product_id", "=", prod["id"]],
                        ["location_id", "=", location["id"]],
                    ],
                    fields=["available_quantity"],
                    limit=1,
                )
                on_hand = quants[0]["available_quantity"] if quants else random.randint(10, 200)

                # Simulate counted quantity (may differ)
                counted = max(0, on_hand + random.randint(-5, 5))

                # Find or create/update stock.quant for this product/location
                quant = await client.search_read(
                    "stock.quant",
                    domain=[
                        ("product_id", "=", prod["id"]),
                        ("location_id", "=", location["id"]),
                    ],
                    fields=["id", "quantity"],
                    limit=1,
                )
                if quant:
                    quant_id = quant[0]["id"]
                    await client.write(
                        "stock.quant",
                        quant_id,
                        {"inventory_quantity": counted},
                    )
                else:
                    await client.create(
                        "stock.quant",
                        {
                            "product_id": prod["id"],
                            "location_id": location["id"],
                            "inventory_quantity": counted,
                        },
                    )
            except Exception as e:
                logger.warning(f"Skip adjustment for product {prod.get('name')} at location {location.get('name')}: {e}")
                continue

    logger.succeed(f"Inserted physical adjustments for {len(products)} products in {len(locations)} locations.")
