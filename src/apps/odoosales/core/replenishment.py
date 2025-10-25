import random

from faker import Faker

from apps.odoosales.utils.odoo import OdooClient
from common.logger import logger


faker = Faker("en_US")


async def insert_replenishment():
    async with OdooClient() as client:
        products = await client.search_read("product.product", [], ["id", "name"])
        warehouses = await client.search_read("stock.warehouse", [], ["id", "code", "lot_stock_id"])

        if not products or not warehouses:
            raise ValueError("No products or warehouses found.")

        warehouse_map = {w["code"]: w for w in warehouses if w.get("code")}
        warehouse_codes = list(warehouse_map.keys())

        random.shuffle(products)
        products_count = int(len(products) * 0.3)

        for product in products[:products_count]:
            warehouse_code = random.choice(warehouse_codes)
            warehouse = warehouse_map[warehouse_code]
            location_id = warehouse["lot_stock_id"][0] if isinstance(warehouse["lot_stock_id"], list | tuple) else warehouse["lot_stock_id"]

            min_qty = random.randint(5, 30)
            max_qty = random.randint(min_qty + 20, min_qty + 200)

            replenishment = {
                "product_id": product["id"],
                "location_id": location_id,
                "product_min_qty": min_qty,
                "product_max_qty": max_qty,
                "warehouse_id": warehouse["id"],
            }

            existing = await client.search_read(
                "stock.warehouse.orderpoint",
                domain=[
                    ("product_id", "=", product["id"]),
                    ("location_id", "=", location_id),
                ],
                fields=["id"],
                limit=1,
            )
            if existing:
                logger.info(f"Replenishment rule already exists for {product['name']} at {warehouse_code}, skipping.")
                continue

            try:
                await client.create("stock.warehouse.orderpoint", replenishment)

            except Exception as e:
                raise ValueError(f"Failed to create replenishment for {product['name']} at {warehouse_code}: {e}")

    logger.succeed(f"Inserted replenishment rules for {products_count} products.")
