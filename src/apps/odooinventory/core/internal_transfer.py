import datetime
import random
from collections import OrderedDict

from faker import Faker

from apps.odooinventory.config.constants import StockModelName
from apps.odooinventory.utils.odoo import OdooClient
from common.logger import logger


faker = Faker("en_US")


async def _create_transfer(client, picking_type_id, src, dest, products, wf_code):
    """Create a single internal transfer."""
    n_products = random.randint(1, 3)
    transfer_products = random.sample(products, n_products)
    today = datetime.date.today()
    yesterday = today - datetime.timedelta(days=1)
    tomorrow = today + datetime.timedelta(days=1)
    day_after_tomorrow = today + datetime.timedelta(days=2)
    past = faker.date_between(start_date="-1y", end_date="-2d")
    future = faker.date_between(start_date="+2d", end_date="+1y")

    moves = []
    for prod in transfer_products:
        qty = random.randint(1, 100)
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
        moves.append(
            [
                0,
                0,
                {
                    "name": prod["name"],
                    "product_id": prod["id"],
                    "product_uom_qty": qty,
                },
            ]
        )

    ref = faker.numerify(f"{wf_code}/{datetime.date.today().strftime('%Y/%m/%d')}/INT/######")
    args = {
        "picking_type_id": picking_type_id,
        "location_id": src["id"],
        "location_dest_id": dest["id"],
        "scheduled_date": scheduled_date.strftime("%Y-%m-%d %H:%M:%S"),
        "move_ids_without_package": moves,
        "move_type": "direct",
        "company_id": 1,
        "origin": ref,
        "name": ref,
    }

    try:
        picking_id = await client.create("stock.picking", args)

        return picking_id
    except Exception as e:
        logger.warning(f"Failed to create internal transfer from {src['name']} to {dest['name']}: {e}")
        return None


async def insert_internal_transfer():
    """Backfill internal transfers (stock.picking, Internal Transfers) for simulation."""
    async with OdooClient() as client:
        picking_types = await client.search_read(
            StockModelName.STOCK_PICKING_TYPE.value,
            domain=[("code", "=", "internal")],
            fields=["id", "warehouse_id"],
        )

        products = await client.search_read(
            "product.product",
            fields=["id", "name"],
        )

        locations = await client.search_read(
            StockModelName.STOCK_LOCATION.value,
            [],
            fields=[
                "id",
                "name",
                "warehouse_id",
            ],
        )
        warehouses = await client.search_read(
            StockModelName.STOCK_WAREHOUSE.value,
            [],
            fields=["id", "code"],
        )
        warehouses_lookup = {w["id"]: w["code"] for w in warehouses}

        warehouses_groups = {}
        for loc in locations:
            wh_id = loc["warehouse_id"][0] if isinstance(loc["warehouse_id"], list | tuple) else loc["warehouse_id"]
            if wh_id not in warehouses_groups:
                warehouses_groups[wh_id] = []
            warehouses_groups[wh_id].append(loc)

        random.shuffle(products)
        products_count = int(len(products) * 0.3)

        for picking_type in picking_types:
            for _ in range(products_count):
                src, dest = random.sample(warehouses_groups.get(picking_type["warehouse_id"][0]), 2)
                while src["id"] == dest["id"]:
                    src, dest = random.sample(warehouses_groups.get(picking_type["warehouse_id"][0]), 2)

                wh_code = warehouses_lookup.get(picking_type["warehouse_id"][0], "WH")

                await _create_transfer(client, picking_type["id"], src, dest, products, wh_code)
        logger.succeed(f"Inserted {products_count * len(picking_types)} internal transfers.")


async def delete_internal_transfer():
    async with OdooClient() as client:
        pickings = await client.search_read("stock.picking", domain=[("name", "ilike", "INT-%")], fields=["id"])
        if pickings:
            await client.delete("stock.picking", [picking["id"] for picking in pickings])
            logger.info("Deleted all internal transfers.")


async def diversify_internal_transfer_statuses():
    """
    Diversify the status of internal transfers to create a realistic mix of statuses.
    Progresses transfers through the workflow: Draft -> Waiting -> Ready -> Done.
    """
    async with OdooClient() as client:
        # Fetch the latest internal transfers
        transfers = await client.search_read(
            "stock.picking",
            domain=[("picking_type_id.name", "ilike", "Internal Transfers")],
            fields=["id", "state"],
            order="id desc",
        )

        transfer_ids = [t["id"] for t in transfers]
        random.shuffle(transfer_ids)  # Randomize the order

        for transfer_id in transfer_ids:
            status = faker.random_element(
                OrderedDict(
                    draft=0.2,
                    waiting=0.2,
                    ready=0.3,
                    done=0.3,
                )
            )

            try:
                match status:
                    case "waiting":
                        await client.execute_kw("stock.picking", "action_confirm", [transfer_id])
                    case "ready":
                        await client.execute_kw("stock.picking", "action_assign", [transfer_id])
                    case "done":
                        # Ensure picking is assigned (Ready)
                        await client.execute_kw("stock.picking", "action_assign", [transfer_id])

                        # Get the stock moves for this picking
                        moves = await client.search_read(
                            "stock.move",
                            domain=[("picking_id", "=", transfer_id)],
                            fields=["id", "product_id", "product_uom_qty", "state", "product_packaging_qty"],
                        )

                        # Check if we need to force quantities (no quantities reserved)
                        needs_force = any(m["state"] == "assigned" and float(m["product_packaging_qty"]) == 0 for m in moves)

                        if needs_force:
                            # Immediate Transfer wizard approach
                            wizard_id = await client.execute_kw("stock.immediate.transfer", "create", [{"pick_ids": [(4, transfer_id)]}])
                            await client.execute_kw("stock.immediate.transfer", "process", [wizard_id])
                        else:
                            # Get existing stock.move.line records
                            move_lines = await client.search_read(
                                "stock.move.line",
                                domain=[("picking_id", "=", transfer_id)],
                                fields=["id", "move_id", "quantity", "product_uom_qty"],
                            )

                            # If we have move lines with zero quantities, update them
                            if move_lines:
                                # Build mapping of move_id to product_uom_qty
                                move_qty_map = {m["id"]: m["product_uom_qty"] for m in moves}

                                for move_line in move_lines:
                                    move_id = move_line["move_id"][0] if isinstance(move_line["move_id"], list | tuple) else move_line["move_id"]
                                    planned_qty = move_qty_map.get(move_id, 1)

                                    # Only update if quantity is not already set
                                    if move_line.get("quantity", 0) == 0:
                                        await client.write(
                                            "stock.move.line",
                                            move_line["id"],
                                            {"quantity": planned_qty},
                                        )

                            # Try normal validation approach
                            await client.execute_kw("stock.picking", "button_validate", [transfer_id])
            except Exception:
                continue

    logger.succeed(f"Diversified internal transfer statuses for {len(transfers)} transfers.")
