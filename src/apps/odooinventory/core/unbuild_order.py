import random

from faker import Faker

from apps.odooinventory.config.constants import MrpModelName
from apps.odooinventory.utils.odoo import OdooClient
from common.logger import logger


faker = Faker("en_US")


REASONS = ["Mistaken production", "Defective products", "Excess production"]


async def insert_unbuild_orders():
    async with OdooClient() as client:
        manufacturing_orders = await client.search_read(MrpModelName.MRP_ORDER.value, [], ["id", "state"])

        ub_count = int(len(manufacturing_orders) * 0.6)

        done_mos = [mo for mo in manufacturing_orders if mo["state"] == "done"]

        random.shuffle(manufacturing_orders)

        mos = done_mos + manufacturing_orders[: ub_count - len(done_mos)]

        for mo in mos[:ub_count]:
            mo_id = mo["id"]
            unbuild_order_data = {
                "name": f"[{faker.numerify('UB/####')}] {random.choice(REASONS)}",
                "mo_id": mo_id,
                "state": "draft",
                "product_qty": random.randint(1, 5),  # Random quantity for unbuild order
            }
            try:
                await client.create(MrpModelName.MRP_UNBUILD_ORDER.value, unbuild_order_data)
            except Exception as e:
                raise ValueError(f"Failed to create unbuild order for Manufacturing Order ID: {mo_id}. Error: {e}")
        logger.succeed(f"Inserted {ub_count} Unbuild Orders for Manufacturing Orders.")


async def diversify_unbuild_orders():
    async with OdooClient() as client:
        done_mos = await client.search_read(MrpModelName.MRP_ORDER.value, [("state", "=", "done")], ["id"])

        unbuild_orders = await client.search_read(MrpModelName.MRP_UNBUILD_ORDER.value, [("mo_id", "in", [mo["id"] for mo in done_mos])], ["id"])

        for ub in unbuild_orders:
            try:
                await client.execute_kw(MrpModelName.MRP_UNBUILD_ORDER.value, "action_validate", [ub["id"]])
            except Exception as e:
                raise ValueError(f"Failed to validate unbuild order ID: {ub['id']}. Error: {e}")
        logger.succeed(f"Diversified Unbuild Orders for {len(unbuild_orders)} Manufacturing Orders.")
