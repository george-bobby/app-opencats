import asyncio
import random

from faker import Faker
from openai import AsyncOpenAI

from apps.odoosales.config.constants import AccountModelName, POSModelName, ProductModelName
from apps.odoosales.config.settings import settings
from apps.odoosales.utils.odoo import OdooClient
from common.load_json import load_json
from common.logger import logger


openai = AsyncOpenAI()  # Uses OPENAI_API_KEY from environment variable
faker = Faker()


async def insert_product_attributes():
    logger.start("Creating product attributes in bulk...")

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
            "value_ids": [(0, 0, {"name": value, "color": random.randint(1, 11)}) for value in variant["values"]],
        }
        attr_records.append(attr_data)

    logger.start(f"Inserting {len(products)} product attributes in bulk...")
    async with OdooClient() as client:
        await client.create(ProductModelName.PRODUCT_ATTRIBUTE.value, [attr_records])
        logger.succeed(f"Inserted {len(attr_records)} product attributes.")


async def insert_product_categories():
    logger.start("Creating product categories in bulk...")

    products = load_json(settings.DATA_PATH.joinpath("products.json"))

    categories = {product["category"] for product in products}

    category_records = []
    for category in categories:
        category_records.append(
            {
                "name": category,
                "parent_id": 1,  # Assuming 1 is the root category ID
            }
        )

    async with OdooClient() as client:
        try:
            await client.create(ProductModelName.PRODUCT_CATEGORY.value, [category_records])
            logger.succeed(f"Inserted {len(categories)} categories")
        except Exception as e:
            raise ValueError(f"Error creating categories: {e}")


async def insert_pos_categories():
    logger.start("Creating product categories...")

    products = load_json(settings.DATA_PATH.joinpath("products.json"))

    categories = {product["category"] for product in products}

    async with OdooClient() as client:
        for category in categories:
            try:
                await client.create(
                    POSModelName.POS_CATEGORY.value,
                    {"name": category},
                )
            except Exception as e:
                logger.warning(f"Failed to create category {category}: {e}")
        logger.succeed(f"Created {len(categories)} product categories for PoS.")


async def insert_product_tags():
    logger.start("Creating product tags in bulk...")

    products = load_json(settings.DATA_PATH.joinpath("products.json"))

    tags = set()
    for product in products:
        tags.update(product["tags"])

    tag_records = []
    for tag in tags:
        tag_records.append(
            {
                "name": tag,
            }
        )

    async with OdooClient() as client:
        try:
            await client.create(ProductModelName.PRODUCT_TAG.value, [tag_records])
            logger.succeed(f"Inserted {len(tags)} tags")
        except Exception as e:
            raise ValueError(f"Error creating tags: {e}")


async def insert_products():
    products = load_json(settings.DATA_PATH.joinpath("products.json"))

    logger.start(f"Bulk inserting {len(products)} products...")

    # Update tax configuration first
    async with OdooClient() as client:
        await client.write(
            AccountModelName.ACCOUNT_TAX.value,
            1,
            {
                "amount_type": "percent",
                "amount": 8.25,
                "name": "Texas Sales Tax",
                "description": "Standard sales tax for Texas",
                "country_id": 233,
            },
        )
        categories = await client.search_read(
            ProductModelName.PRODUCT_CATEGORY.value,
            [],
            ["id", "name"],
        )
        pos_categories = await client.search_read(
            POSModelName.POS_CATEGORY.value,
            [],
            ["id", "name"],
        )
        tags = await client.search_read(
            ProductModelName.PRODUCT_TAG.value,
            [],
            ["id", "name"],
        )
        uom = await client.search_read(
            "uom.uom",
            [],
            ["id", "name", "category_id"],
        )

        categories_lookup = {cat["name"]: cat["id"] for cat in categories}
        pos_categories_lookup = {pos_cat["name"]: pos_cat["id"] for pos_cat in pos_categories}
        tags_lookup = {tag["name"]: tag["id"] for tag in tags}
        uom_lookup = {uom["name"]: uom for uom in uom}

        for product in products:
            product["category_id"] = categories_lookup.get(product["category"], 1)  # Default to root category if not found
            product["tag_ids"] = [tags_lookup.get(tag) for tag in product["tags"]]
            product["uom_id"] = uom_lookup.get(product["uom"])["id"] if product["uom"] in uom_lookup else 1  # Default to unit of measure ID 1
            product["uom_category_id"] = uom_lookup.get(product["uom"])["category_id"][0] if product["uom"] in uom_lookup else 1  # Default to unit of measure category ID 1
            product["pos_categ_ids"] = [pos_categories_lookup.get(product["category"], 1)]

        # Process products using the threading utility
        try:
            product_records = []
            products_with_variants = []

            for product in products:
                try:
                    shortcode_category = product["category"][:3].upper()

                    product_data = {
                        "name": product["name"],
                        "description": product["description"],
                        "description_sale": product["description_sale"],
                        "list_price": product["list_price"],
                        "standard_price": product["cost"],
                        "categ_id": product["category_id"],
                        "pos_categ_ids": product.get("pos_categ_ids", []),  # Assuming category ID is provided
                        "product_tag_ids": product.get("tag_ids", []),  # Assuming tag IDs are provided
                        "type": product["type"] if "type" in product else product["product_type"],  # Default to 'consu' if not provided
                        "sale_ok": True,
                        "company_id": 1,  # Assuming company ID 1 is the default
                        "available_in_pos": True,
                        "cost_currency_id": 1,
                        "currency_id": 1,
                        "taxes_id": [(6, 0, [1])],
                        "color": random.randint(1, 11),  # Random color index between 1 and 11
                        "sale_delay": random.randint(1, 5),  # Random sale delay between 1 and 5 days
                        "default_code": faker.numerify(f"{shortcode_category}-####"),
                    }

                    if product_data["type"] == "consu":
                        product_data["is_storable"] = True  # Ensure consumable products are storable
                        product_data["purchase_ok"] = True  # Consumable products can be purchased
                        product_data["barcode"] = faker.numerify("############")
                        product_data["description_picking"] = product["description_picking"]
                        product_data["description_pickingin"] = product["description_pickingin"]
                        product_data["description_pickingout"] = product["description_pickingout"]
                        product_data["description_purchase"] = product["description_purchase"]
                        product_data["uom_id"] = product.get("uom_id")  # Default to unit of measure if not provided
                        product_data["uom_category_id"] = product.get("uom_category_id")  # Default to unit of measure category if not provided
                        product_data["weight"] = product.get("weight", 0.0)  # Default weight if not provided
                        product_data["volume"] = product.get("volume", 0.0)  #
                    else:
                        product_data["is_storable"] = False
                        product_data["purchase_ok"] = False

                    product_records.append(product_data)

                    # Keep track of products with variants for later processing
                    if product["variants"]:
                        products_with_variants.append(product)

                except Exception as e:
                    logger.warning(f"Skip product '{product.get('name', 'Unknown')}': {e}")
                    continue

            if product_records:
                await client.create(ProductModelName.PRODUCT_TEMPLATE.value, [product_records])
                logger.succeed(f"Inserted {len(product_records)} products.")
        except Exception as e:
            raise ValueError(f"Error processing products: {e}")


async def insert_optional_products():
    logger.start("Creating optional products in bulk...")
    async with OdooClient() as client:
        products = await client.search_read(
            ProductModelName.PRODUCT_TEMPLATE.value,
            [("type", "=", "consu"), ("company_id.id", "!=", None)],
            ["id"],
        )

        # Prepare all updates for bulk processing
        bulk_updates = []
        for product in products:
            optional_products = random.sample(products, 1)
            bulk_updates.append(
                {
                    "id": product["id"],
                    "optional_product_ids": [(6, 0, [p["id"] for p in optional_products])],
                }
            )

        # Execute bulk updates in batches
        batch_size = 20
        for i in range(0, len(bulk_updates), batch_size):
            batch = bulk_updates[i : i + batch_size]
            tasks = []

            for update in batch:
                task = client.write(
                    ProductModelName.PRODUCT_TEMPLATE.value,
                    update["id"],
                    {"optional_product_ids": update["optional_product_ids"]},
                )
                tasks.append(task)

            try:
                await asyncio.gather(*tasks)
            except Exception as e:
                logger.error(f"Failed to process optional products batch: {e}")

        logger.succeed(f"Inserted optional products for {len(products)} products.")
