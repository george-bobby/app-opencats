from faker import Faker

from apps.odooinventory.utils.odoo import OdooClient
from common.logger import logger


faker = Faker("en_US")


async def update_on_hand_quantity():
    """
    Update the on-hand quantity for a product at a specific location in Odoo.
    Args:
        product_id (int): The ID of the product to update.
        location_id (int): The ID of the location where the quantity should be updated.
        quantity (float): The new on-hand quantity to set.
    """

    async with OdooClient() as client:
        logger.start("Updating on-hand quantities for products...")

        templates = await client.search_read(
            "product.template",
            [("is_storable", "=", True), ("type", "=", "consu")],
            ["id", "name", "categ_id"],
        )
        products = await client.search_read(
            "product.product",
            [("product_tmpl_id", "in", [p["id"] for p in templates])],
            ["id", "name", "product_tmpl_id"],
        )
        locations = await client.search_read(
            "stock.location",
            [
                ("usage", "=", "internal"),
                ("name", "=", "Stock"),
                ("warehouse_id", "!=", None),
                ("location_id", "!=", None),
            ],
            ["id", "name"],
        )

        templates_lookup = {tmpl["id"]: tmpl for tmpl in templates}

        for product in products:
            product_id = product["id"]
            template = templates_lookup.get(product["product_tmpl_id"][0])
            product_category = template["categ_id"][1]

            for location in locations:
                quantity = faker.random_int(50, 100) if product_category in ["Home Essentials", "Electronics"] else faker.random_int(100, 300)

                # Update the on-hand quantity
                try:
                    await client.create(
                        "stock.quant",
                        {
                            "product_id": product_id,
                            "location_id": location["id"],
                            "quantity": quantity,
                            "available_quantity": quantity,
                        },
                    )
                except Exception as e:
                    logger.warning(f"Failed to update quantity for product {product['name']} at location {location['id']}: {e}")
                    continue

        logger.succeed(f"Updated on-hand quantities for {len(templates)} products at {len(locations)} locations.")
