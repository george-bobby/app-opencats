import datetime
import random
from collections import OrderedDict
from typing import Any

from faker import Faker

from apps.odooinventory.config.constants import StockModelName
from apps.odooinventory.utils.odoo import OdooClient
from common.logger import logger
from common.threading import process_in_parallel


faker = Faker("en_US")


async def _process_delivery_chunk(
    items_chunk: list[tuple[dict[str, Any], dict[str, Any], int, int, list[dict[str, Any]]]],
):
    """Processes a chunk of deliveries."""

    today = datetime.date.today()
    yesterday = today - datetime.timedelta(days=1)
    tomorrow = today + datetime.timedelta(days=1)
    day_after_tomorrow = today + datetime.timedelta(days=2)
    past = faker.date_between(start_date="-1y", end_date="-2d")
    future = faker.date_between(start_date="+2d", end_date="+1y")

    async with OdooClient() as client:
        for picking_type, product, delivery_picking_type_id, partners in items_chunk:
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
                    "picking_type_id": delivery_picking_type_id,
                    "partner_id": partner["id"],
                    "scheduled_date": scheduled_date.strftime("%Y-%m-%d %H:%M:%S"),
                    "location_id": picking_type["default_location_src_id"][0],
                    "location_dest_id": picking_type["default_location_dest_id"][0],
                    "move_ids_without_package": [
                        [
                            0,
                            0,
                            {
                                "name": product["name"],
                                "product_id": product["id"],
                                "product_uom_qty": faker.random_int(min=5, max=10),
                            },
                        ]
                    ],
                    "move_type": picking_type["move_type"],
                    "origin": ref,
                    "name": ref,
                }
                picking_id = await client.create(StockModelName.STOCK_PICKING.value, args)

                await client.execute_kw("stock.picking", "action_confirm", [picking_id])
            except Exception:
                continue


async def insert_deliveries():
    logger.start("Inserting deliveries...")

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
            domain=[("code", "=", "outgoing")],
            fields=[
                "id",
                "warehouse_id",
                "default_location_src_id",
                "default_location_dest_id",
                "move_type",
            ],
        )
        if not picking_types:
            logger.error("No delivery picking type found.")
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

    await process_in_parallel(items=items_to_process, async_processor=_process_delivery_chunk)

    logger.succeed(f"Finished inserting deliveries for warehouses: {', '.join([w['code'] for w in warehouses if w.get('code')])}")


async def diversify_delivery_statuses():
    logger.start("Diversifying delivery statuses...")
    async with OdooClient() as client:
        delivery_picking_type = await client.search_read(
            "stock.picking.type",
            domain=[("code", "=", "outgoing")],
            fields=["id"],
            limit=1,
        )
        deliveries = await client.search_read(
            "stock.picking",
            domain=[
                ("picking_type_id", "=", delivery_picking_type[0]["id"]),
                ("state", "=", "draft"),
            ],
            fields=["id", "state"],
        )

        random.shuffle(deliveries)
        deliveries = deliveries[: int(len(deliveries) * 0.4)]

        for delivery in deliveries:
            delivery_id = delivery["id"]
            status = faker.random_element(OrderedDict(draft=0.2, cancel=0.2, ready=0.3, done=0.3))

            match status:
                case "cancel":
                    await client.execute_kw("stock.picking", "action_cancel", [delivery_id])
                case "ready":
                    await client.execute_kw("stock.picking", "action_confirm", [delivery_id])
                case "done":
                    await client.execute_kw("stock.picking", "button_validate", [delivery_id])

        logger.succeed(f"Diversified delivery statuses for {len(deliveries)} deliveries.")
