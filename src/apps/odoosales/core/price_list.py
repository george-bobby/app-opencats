from apps.odoosales.config.constants import ProductModelName
from apps.odoosales.utils.odoo import OdooClient
from common.logger import logger


async def insert_price_list():
    logger.start("Creating price list...")
    async with OdooClient() as client:
        products = await client.search_read(
            ProductModelName.PRODUCT_TEMPLATE.value,
            [("type", "in", ("consu", "combo"))],
            ["id", "name", "list_price"],
        )
        try:
            price_list_id = await client.create(
                "product.pricelist",
                {
                    "name": "2025 Standard Retail",
                    "currency_id": 1,  # Assuming currency ID 1 is USD
                },
            )
            logger.succeed("Price list created successfully.")

            for product in products:
                await client.create(
                    ProductModelName.PRODUCT_PRICELIST_ITEM.value,
                    {
                        "pricelist_id": price_list_id,
                        "product_tmpl_id": product["id"],
                        "fixed_price": product["list_price"],
                        "compute_price": "fixed",
                        "min_quantity": 1,
                        "date_start": "2025-01-01 00:00:00",  # Example start date
                    },
                )
            logger.succeed(f"Inserted {len(products)} products into the price list.")

            return price_list_id
        except Exception as e:
            raise ValueError(f"Error creating price list: {e}")
