import random

from faker import Faker

from apps.odooinventory.config.constants import MrpModelName
from apps.odooinventory.utils.odoo import OdooClient
from common.logger import logger


fake = Faker("en_US")

SCRAP_REASONS = [
    "Defective input material",
    "Failed quality control",
    "Assembly damage",
    "Customer return",
    "Overproduction",
]


async def create_scrap_reasons():
    """
    Create realistic scrap reasons for simulation/testing.
    """
    reason_ids = []
    async with OdooClient() as client:
        scrap_reasons = await client.search_read("stock.scrap.reason.tag", [], ["id"])
        if scrap_reasons:
            return [reason["id"] for reason in scrap_reasons]
        for reason in SCRAP_REASONS:
            vals = {
                "name": reason,
            }
            try:
                reason_id = await client.create("stock.scrap.reason.tag", vals)
                reason_ids.append(reason_id)
            except Exception as e:
                logger.error(f"Error creating scrap reason: {e}")

        logger.succeed(f"Created {len(reason_ids)} scrap reasons")

    return reason_ids


async def insert_scrap_orders():
    async with OdooClient() as client:
        # Get internal warehouse locations (source)
        locations = await client.search_read(
            "stock.location",
            domain=[("usage", "=", "internal")],
            fields=["id", "name", "complete_name"],
        )

        scrap_locs = await client.search_read(
            "stock.location",
            domain=[("scrap_location", "=", True)],
            fields=["id", "name"],
        )

        quality_control_work_center = await client.search_read(
            MrpModelName.MRP_WORK_CENTER.value,
            domain=[("name", "ilike", "Quality Control")],
            fields=["id"],
            limit=1,
        )
        products_in_quality_control = await client.search_read(
            MrpModelName.MRP_CAPACITY.value,
            domain=[("workcenter_id", "in", [wc["id"] for wc in quality_control_work_center])],
            fields=["product_id"],
            limit=5,
        )

        reason_ids = await create_scrap_reasons()

        for prod in products_in_quality_control:
            source_loc = random.choice(locations)
            scheduled_date = fake.date_time_between(start_date="-1M", end_date="now")
            qty = random.randint(1, 10)

            scrap_data = {
                "product_id": prod["product_id"][0],
                "scrap_qty": qty,
                "location_id": source_loc["id"],
                "scrap_location_id": random.choice(scrap_locs)["id"],
                "date_done": scheduled_date.strftime("%Y-%m-%d %H:%M:%S"),
                "origin": "",  # Source Document left blank
                "name": fake.numerify("SCRAP-####"),
                "scrap_reason_tag_ids": [random.choice(reason_ids)],
            }
            try:
                await client.create("stock.scrap", scrap_data)
            except Exception as e:
                logger.error(f"Error creating scrap orders: {e}")

        positive_qty = await client.search_read(
            "stock.quant",
            domain=[("quantity", ">", 0)],
            fields=["product_id"],
        )
        components = await client.search_read(
            "product.product",
            domain=[
                ("type", "=", "consu"),
                ("default_code", "ilike", "COMP-%"),
                ("id", "in", [p["product_id"][0] for p in positive_qty]),
            ],
            fields=["id", "display_name"],
            limit=15,
        )

        manufacturing_orders = await client.search_read(
            MrpModelName.MRP_ORDER.value,
            domain=[],
            fields=["id", "name", "bom_id"],
        )
        mo_components_map = {}
        for mo in manufacturing_orders:
            bom = await client.search_read(MrpModelName.MRP_BOM.value, domain=[("id", "=", mo["bom_id"][0])], fields=["id"], limit=1)
            bom_lines = await client.search_read(
                MrpModelName.MRP_BOM_LINE.value,
                domain=[("bom_id", "=", [bom[0]["id"]])],
                fields=["product_id"],
            )
            mo_components_map[mo["name"]] = [line["product_id"][0] for line in bom_lines]

        source_loc = [loc["id"] for loc in locations if loc["complete_name"] == "WH/Stock"]

        for idx, component in enumerate(components):
            scheduled_date = fake.date_time_between(start_date="-1M", end_date="now")
            qty = random.randint(1, 10)

            scrap_data = {
                "product_id": component["id"],
                "scrap_qty": qty,
                "location_id": source_loc[0] if source_loc else random.choice(locations)["id"],
                "scrap_location_id": random.choice(scrap_locs)["id"],
                "date_done": scheduled_date.strftime("%Y-%m-%d %H:%M:%S"),
                "name": fake.numerify("SCRAP-####"),
                "scrap_reason_tag_ids": [random.choice(reason_ids)],
            }

            if idx <= len(components) * 0.4:
                for mo_name, component_ids in mo_components_map.items():
                    if component["id"] in component_ids:
                        scrap_data["origin"] = mo_name
                        break

            try:
                await client.create("stock.scrap", scrap_data)
            except Exception as e:
                logger.error(f"Error creating scrap orders: {e}")

        logger.succeed(f"Inserted {len(components)} Scrap Orders for components.")


async def diversify_scrap_statuses():
    async with OdooClient() as client:
        # Fetch the latest 50 scrap orders
        scraps = await client.search_read(
            "stock.scrap",
            fields=["id", "state"],
            order="id desc",
        )

        count = min(int(len(scraps) * 0.5), 50)

        draft_count = int(count * 0.5)

        if not scraps or len(scraps) < count:
            logger.warning(f"Only found {len(scraps)} scrap orders. Adjusting distribution.")
        ids = [s["id"] for s in scraps]
        # Shuffle for randomness
        random.shuffle(ids)
        done_ids = ids[draft_count:count]

        for scrap_id in done_ids:
            try:
                await client.execute_kw("stock.scrap", "action_validate", [scrap_id])
                logger.info(f"Scrap {scrap_id} set to Done (validated)")
            except Exception as e:
                logger.error(f"Error setting scrap {scrap_id} to Done: {e}")
