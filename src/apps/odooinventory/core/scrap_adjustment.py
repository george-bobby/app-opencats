import random

from faker import Faker

from apps.odooinventory.config.constants import SCRAP_REASONS
from apps.odooinventory.utils.odoo import OdooClient
from common.logger import logger


faker = Faker("en_US")


async def insert_scrap_adjustments():
    async with OdooClient() as client:
        # Get products
        products = await client.search_read(
            "product.product",
            fields=["id", "name", "product_tmpl_id"],
        )
        if not products:
            raise ValueError("No products found.")

        # Get product template UOMs
        tmpl_ids = list({prod["product_tmpl_id"][0] for prod in products if prod["product_tmpl_id"]})
        tmpl_data = await client.search_read(
            "product.template",
            domain=[["id", "in", tmpl_ids]],
            fields=["id", "uom_id"],
        )
        tmpl_uom_map = {t["id"]: t["uom_id"] for t in tmpl_data}

        # Get internal warehouse locations (source)
        locations = await client.search_read(
            "stock.location",
            domain=[("usage", "=", "internal")],
            fields=["id", "name", "complete_name"],
        )
        if not locations:
            raise ValueError("No warehouse locations found.")
            return

        # Get scrap location
        scrap_locs = await client.search_read(
            "stock.location",
            domain=[("scrap_location", "=", True)],
            fields=["id", "name"],
            limit=1,
        )
        if not scrap_locs:
            raise ValueError("No scrap location found.")
            return
        scrap_location_id = scrap_locs[0]["id"]

        random.shuffle(products)  # Shuffle products for randomness
        products_count = int(len(products) * 0.3)

        for _ in range(products_count):
            # 1 or 2 products per adjustment
            n_products = random.randint(1, 2)
            adj_products = random.sample(products, n_products)
            source_loc = random.choice(locations)
            scheduled_date = faker.date_time_between(start_date="-3M", end_date="now")

            for prod in adj_products:
                qty = random.randint(5, 20)  # Random quantity between 5 and 20
                reason = random.choice(SCRAP_REASONS)
                tmpl_id = prod["product_tmpl_id"][0] if prod["product_tmpl_id"] else None
                uom_id = tmpl_uom_map.get(tmpl_id)
                if isinstance(uom_id, list):
                    uom_id = uom_id[0]
                if not uom_id:
                    raise ValueError(f"No UOM found for product {prod['id']} (template {tmpl_id})")
                    continue
                vals = {
                    "product_id": prod["id"],
                    "product_uom_id": uom_id,
                    "scrap_qty": qty,
                    "location_id": source_loc["id"],
                    "scrap_location_id": scrap_location_id,
                    "date_done": scheduled_date.strftime("%Y-%m-%d %H:%M:%S"),
                    "origin": "",  # Source Document left blank
                    "name": reason,  # Store the scrap reason in the name field
                }
                try:
                    await client.create("stock.scrap", vals)
                except Exception as e:
                    raise ValueError(f"Error creating scrap adjustment: {e}")
    logger.succeed(f"Inserted {products_count} scrap adjustments.")


async def diversify_scrap_statuses():
    async with OdooClient() as client:
        # Fetch the latest 50 scrap orders
        scraps = await client.search_read(
            "stock.scrap",
            fields=["id", "state"],
            order="id desc",
        )
        count = len(scraps)
        draft_count = int(count * 0.4)
        if not scraps or len(scraps) < count:
            logger.warning(f"Only found {len(scraps)} scrap orders. Adjusting distribution.")
        ids = [s["id"] for s in scraps]
        # Shuffle for randomness
        random.shuffle(ids)
        done_ids = ids[draft_count:count]

        for scrap_id in done_ids:
            try:
                await client.write("stock.scrap", scrap_id, {"state": "done"})
            except Exception as e:
                raise ValueError(f"Error setting scrap {scrap_id} to Done: {e}")

        logger.succeed(f"Updated {len(done_ids)} scrap orders to Done status out of {count} total scraps.")
