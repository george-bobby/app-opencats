import datetime
import random
from collections import OrderedDict

from faker import Faker

from apps.odoosales.config.constants import StockModelName
from apps.odoosales.utils.odoo import OdooClient
from common.logger import logger


faker = Faker("en_US")


async def insert_receipts():
    logger.start("Inserting receipts...")

    today = datetime.date.today()
    yesterday = today - datetime.timedelta(days=1)
    tomorrow = today + datetime.timedelta(days=1)
    day_after_tomorrow = today + datetime.timedelta(days=2)
    past = faker.date_between(start_date="-1y", end_date="-2d")
    future = faker.date_between(start_date="+2d", end_date="+1y")

    async with OdooClient() as client:
        warehouses = await client.search_read(
            "stock.warehouse",
            fields=["id", "code"],
        )
        products = await client.search_read(
            "product.product",
            fields=["id", "name"],
        )
        partners = await client.search_read(
            "res.partner",
            domain=[("is_company", "=", True)],
            fields=["id", "name"],
        )
        picking_types = await client.search_read(
            "stock.picking.type",
            domain=[("code", "=", "incoming")],
            fields=["id", "warehouse_id", "default_location_dest_id"],
        )
        if not picking_types:
            logger.error("No receipt picking type found.")
            return

        warehouses_lookup = {wh["id"]: wh for wh in warehouses}

        items_to_process = []
        for picking_type in picking_types:
            wh_code = warehouses_lookup.get(picking_type["warehouse_id"][0], {}).get("code")
            if not wh_code:
                continue

            picking_type["wh_code"] = wh_code  # Add code to picking_type for easier reference

            for product in products:
                items_to_process.append((picking_type, product, picking_type["id"], partners))

        for picking_type, product, receipt_picking_type_id, partners in items_to_process:
            try:
                wh_code = picking_type.get("wh_code")
                partner = faker.random_element(partners)

                ref = faker.numerify(f"{wh_code}/{datetime.date.today().strftime('%Y/%m/%d')}/IN/######")

                scheduled_date = faker.random_element(
                    [
                        today,
                        yesterday,
                        tomorrow,
                        day_after_tomorrow,
                        past,
                        future,
                    ]
                )

                args = {
                    "picking_type_id": receipt_picking_type_id,
                    "partner_id": partner["id"],
                    "scheduled_date": scheduled_date.strftime("%Y-%m-%d %H:%M:%S"),
                    "location_dest_id": picking_type["default_location_dest_id"][0],
                    "move_ids_without_package": [
                        [
                            0,
                            0,
                            {
                                "name": product["name"],
                                "product_id": product["id"],
                                "product_uom_qty": faker.random_int(min=100, max=10000, step=100),
                            },
                        ]
                    ],
                    "move_type": "direct",
                    "origin": ref,
                    "name": ref,
                }
                await client.create(StockModelName.STOCK_PICKING.value, args)
            except Exception as e:
                logger.warning(f"Skip creating receipt for product {product.get('name')} in warehouse {picking_type.get('wh_code')}: {e}")
                continue

    logger.succeed(f"Inserted receipts for {len(items_to_process)} products in {len(picking_types)} warehouses.")


async def diversify_receipt_statuses():
    logger.start("Diversifying receipt statuses...")
    async with OdooClient() as client:
        pickings = await client.search_read(StockModelName.STOCK_PICKING.value, [], ["id"])

        if not pickings:
            logger.info("No receipts found to diversify.")
            return

        random.shuffle(pickings)
        pickings = pickings[: int(len(pickings) * 0.4)]  # Process only 40% of the receipts

        for picking in pickings:
            try:
                picking_id = picking["id"]
                status = faker.random_element(OrderedDict([("assigned", 0.5), ("done", 0.5)]))

                if status == "assigned":
                    await client.execute_kw(
                        StockModelName.STOCK_PICKING.value,
                        "action_confirm",
                        [picking_id],
                    )
                elif status == "done":
                    await client.execute_kw(
                        StockModelName.STOCK_PICKING.value,
                        "button_validate",
                        [picking_id],
                    )
            except Exception:
                continue

    logger.succeed(f"Finished diversifying statuses for {len(pickings)} receipts.")
