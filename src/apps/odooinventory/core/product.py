import random
from typing import Any

import pandas as pd
from faker import Faker

from apps.odooinventory.config.constants import COMPONENT_CATEGORIES, PRODUCT_CATEGORIES, MrpModelName, ProductModelName, StockModelName
from apps.odooinventory.config.settings import settings
from apps.odooinventory.utils.odoo import OdooClient
from common.load_json import load_json
from common.logger import logger
from common.threading import process_in_parallel


faker = Faker("en_US")


async def insert_product_attributes():
    products = load_json(settings.DATA_PATH.joinpath("products.json"))

    attr_records = []
    variants_map = {}
    for product in products:
        for variant in product["variants"]:
            variants_map[variant["name"]] = variant

    for variant_name, variant in variants_map.items():
        attr_data = {
            "name": variant_name,
            "display_type": variant["display_type"],
            "create_variant": "always",
            "value_ids": [(0, 0, {"name": value}) for value in variant["values"]],
        }
        attr_records.append(attr_data)

    logger.start(f"Inserting {len(products)} product attributes in bulk...")
    async with OdooClient() as client:
        await client.create(ProductModelName.PRODUCT_ATTRIBUTE.value, [attr_records])
        logger.succeed(f"Bulk inserted {len(attr_records)} product attributes.")


async def insert_product_categories():
    logger.start("Creating product categories in bulk...")

    async with OdooClient() as client:
        saleable_category = await client.search_read(
            ProductModelName.PRODUCT_CATEGORY.value,
            [("name", "=", "Saleable")],
            ["id"],
            limit=1,
        )
        category_records = []
        for category in PRODUCT_CATEGORIES:
            category_records.append({"name": category, "parent_id": saleable_category[0]["id"]})
        try:
            await client.create(ProductModelName.PRODUCT_CATEGORY.value, [category_records])
            logger.succeed(f"Bulk inserted {len(PRODUCT_CATEGORIES)} categories")
        except Exception as e:
            raise ValueError(f"Error creating categories: {e}")


async def insert_components_categories():
    logger.start("Creating components categories in bulk...")

    async with OdooClient() as client:
        category_records = []
        for cat in COMPONENT_CATEGORIES:
            # 1. Check if parent category exists (by name, parent_id=1 or None)
            parent_domain = [
                ("name", "=", cat["parent_name"]),
                ("parent_id", "=", 1),  # Assuming 1 is the root category
            ]
            parent_category = await client.search_read(
                ProductModelName.PRODUCT_CATEGORY.value,
                parent_domain,
                ["id"],
                limit=1,
            )
            if not parent_category:
                parent_cat_id = await client.create(
                    ProductModelName.PRODUCT_CATEGORY.value,
                    {"name": cat["parent_name"], "parent_id": 1},
                )
            else:
                parent_cat_id = parent_category[0]["id"]

            # 2. Check if child category exists under this parent
            child_domain = [
                ("name", "=", cat["name"]),
                ("parent_id", "=", parent_cat_id),
            ]
            child_category = await client.search_read(
                ProductModelName.PRODUCT_CATEGORY.value,
                child_domain,
                ["id"],
                limit=1,
            )
            if not child_category:
                category_records.append({"name": cat["name"], "parent_id": parent_cat_id})

        try:
            if category_records:
                await client.create(ProductModelName.PRODUCT_CATEGORY.value, [category_records])
            logger.succeed(f"Bulk inserted {len(category_records)} new component categories")
        except Exception as e:
            raise ValueError(f"Error creating component categories: {e}")


async def _process_product_chunk(products_chunk: list[dict[str, Any]]) -> tuple[list[int], list[dict[str, Any]]]:
    """Process a chunk of products and return product IDs and products with variants"""

    async with OdooClient() as client:
        # Prepare product records for this chunk
        product_records = []
        products_with_variants = []

        for product in products_chunk:
            try:
                # Get category ID
                category = await client.search_read(
                    ProductModelName.PRODUCT_CATEGORY.value,
                    [("name", "=", product["category"])],
                    ["id"],
                )
                if not category:
                    continue

                category_id = category[0]["id"]

                product_data = {
                    "name": product["name"],
                    "description": product["description"],
                    "list_price": product["list_price"],
                    "standard_price": product["cost"],
                    "categ_id": category_id,
                    "type": "consu",
                    "is_storable": True,
                    # "sale_ok": True,
                    # "taxes_id": [(6, 0, [1])],
                    "default_code": faker.numerify("FIN-####"),
                    "barcode": faker.numerify("############"),
                }
                product_records.append(product_data)

                # Keep track of products with variants for later processing
                if product.get("variants"):
                    products_with_variants.append(product)

            except Exception:
                continue

        # Bulk insert products for this chunk
        product_ids = []
        if product_records:
            result = await client.create(ProductModelName.PRODUCT_TEMPLATE.value, [product_records])
            product_ids = result if isinstance(result, list) else [result]

        return product_ids, products_with_variants


async def insert_products():
    products = load_json(settings.DATA_PATH.joinpath("products.json"))

    logger.start(f"Bulk inserting {len(products)} products using threading...")

    # Update tax configuration first
    # async with OdooClient() as client:
    #     await client.write(
    #         AccountModelName.ACCOUNT_TAX.value,
    #         1,
    #         {
    #             "amount_type": "percent",
    #             "amount": 8.25,
    #             "name": "Texas Sales Tax",
    #             "description": "Standard sales tax for Texas",
    #             "country_id": 233,
    #         },
    #     )

    # Process products using the threading utility
    await process_in_parallel(items=products, async_processor=_process_product_chunk)

    logger.succeed(f"Bulk inserted {len(products)} products")


async def classify_manufacturing_products():
    logger.start("Classifying manufacturing products...")
    async with OdooClient() as client:
        try:
            products = await client.search_read(
                ProductModelName.PRODUCT_TEMPLATE.value,
                [("type", "=", "consu")],
                ["id", "name"],
            )
            routes = await client.search_read(
                model=StockModelName.STOCK_ROUTE.value,
                domain=[("name", "=", "Manufacture")],
                fields=["id"],
                limit=1,
            )
            for product in products:
                await client.write(
                    ProductModelName.PRODUCT_PRODUCT.value,
                    product["id"],
                    {"route_ids": [routes[0]["id"]]},
                )
            logger.succeed(f"Classified {len(products)} products as manufacturing")
        except Exception as e:
            raise ValueError(f"Failed to fetch products: {e}")


async def insert_product_lines():
    df_products = pd.read_json(settings.DATA_PATH.joinpath("products.json"))

    df_product_lines = df_products["product_lines"].explode().dropna().tolist()

    print(df_product_lines)

    logger.start("Inserting product lines for manufacturing products...")
    async with OdooClient() as client:
        try:
            work_centers = await client.search_read(
                MrpModelName.MRP_WORK_CENTER.value,
                [],
                ["id", "name"],
            )
            routes = await client.search_read(
                model=StockModelName.STOCK_ROUTE.value,
                domain=[("name", "=", "Manufacture")],
                fields=["id"],
                limit=1,
            )
            products = await client.search_read(
                ProductModelName.PRODUCT_TEMPLATE.value,
                [("type", "=", "consu"), ("default_code", "ilike", "FIN-%"), ("route_ids", "in", [routes[0]["id"]])],
                ["id", "name"],
            )

            work_centers_lookup = {wc["name"]: wc["id"] for wc in work_centers}
            products_lookup = {product["name"]: product["id"] for product in products}

            for line in df_product_lines:
                val = {
                    "product_id": products_lookup.get(line.product, None),
                    "capacity": random.randint(5, 10),
                    "time_start": random.randint(15, 30),
                    "time_stop": random.randint(15, 30),
                    "workcenter_id": work_centers_lookup.get(line.work_center, None),
                }
                await client.create(MrpModelName.MRP_CAPACITY.value, val)

            logger.succeed(f"Inserted {len(df_product_lines)} product lines for manufacturing products")

        except Exception as e:
            raise RuntimeError(f"Failed to insert product lines: {e}")
        finally:
            logger.stop()
