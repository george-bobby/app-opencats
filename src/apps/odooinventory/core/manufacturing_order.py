import random
import time

from faker import Faker

from apps.odooinventory.config.constants import MrpModelName, ResModelName
from apps.odooinventory.utils.odoo import OdooClient
from common.logger import logger


faker = Faker("en_US")


async def insert_responsible_users(count: int = 5):
    logger.start("Inserting responsible users for Manufacturing department...")
    responsible_user_ids = []  # Initialize the list here

    async with OdooClient() as client:
        manufacturing_group_categories = await client.search_read("ir.module.category", [("name", "=", "Manufacturing"), ("parent_id", "!=", None)], ["id"])

        # Ensure categories are found
        if not manufacturing_group_categories:
            logger.warn("Manufacturing group categories not found. Exiting.")
            return []

        manufacturing_admin_groups = await client.search_read(
            ResModelName.RES_GROUP.value,
            [("category_id", "in", [c["id"] for c in manufacturing_group_categories]), ("name", "=", "Administrator")],
            ["id"],
        )

        # Ensure admin groups are found
        if not manufacturing_admin_groups:
            logger.warn("Manufacturing Administrator group not found. Exiting.")
            return []

        # Extract the IDs of the admin groups to assign
        admin_group_ids_to_assign = [g["id"] for g in manufacturing_admin_groups]

        for _ in range(count):
            first_name = faker.first_name()
            last_name = faker.last_name()
            full_name = f"{first_name} {last_name}"
            email = f"{first_name.lower()}.{last_name.lower()}@example.com"
            try:
                user_id = await client.create(
                    ResModelName.RES_USERS.value,
                    {
                        "name": full_name,
                        "login": email,
                        "email": email,
                        "phone": faker.phone_number(),
                        "mobile": faker.phone_number(),
                        "groups_id": [(6, 0, admin_group_ids_to_assign)],
                    },
                )

                responsible_user_ids.append(user_id)
            except Exception as e:
                logger.warn(f"Failed to update (Odoo User ID: {user_id}): {e}")

        logger.succeed(f"Inserted {len(responsible_user_ids)} responsible users for Manufacturing department.")

        return responsible_user_ids


async def insert_manufacturing_orders():
    responsible_user_ids = await insert_responsible_users()

    logger.start("Inserting Manufacturing Orders...")
    async with OdooClient() as client:
        bill_of_materials = await client.search_read(MrpModelName.MRP_BOM.value, [], ["id"])
        picking_types = await client.search_read(
            "stock.picking.type",
            [("code", "=", "mrp_operation")],
            ["id"],
        )

        data = []
        for picking_type in picking_types:
            for bom in bill_of_materials:
                date_start = faker.date_between(start_date="-90d", end_date="+90d")
                date_end = faker.date_between(start_date=date_start, end_date="+90d")
                mo_data = {
                    "picking_type_id": picking_type["id"],
                    "bom_id": bom["id"],
                    "product_qty": random.randint(5, 50),
                    "user_id": random.choice(responsible_user_ids),
                    "date_start": date_start.strftime("%Y-%m-%d %H:%M:%S"),
                    "date_finished": date_end.strftime("%Y-%m-%d %H:%M:%S"),
                    "origin": faker.numerify(text="MO-####"),
                }
                data.append(mo_data)

        await client.create(MrpModelName.MRP_ORDER.value, [data])
        logger.succeed(f"Inserted {len(data)} Manufacturing Orders")


async def diversify_mo_status():
    logger.start("Diversifying Manufacturing Order statuses...")
    async with OdooClient() as client:
        try:
            manufacturing_orders = await client.search_read(MrpModelName.MRP_ORDER.value, [("state", "=", "draft")], ["id", "state"])

            draft_count = len(manufacturing_orders) * 0.2
            confirmed_count = len(manufacturing_orders) * 0.5

            confirmed_mo = manufacturing_orders[int(draft_count) :]

            for mo in confirmed_mo:
                await client.execute_kw(MrpModelName.MRP_ORDER.value, "action_confirm", [mo["id"]])

            time.sleep(0.1)

            done_mo = manufacturing_orders[int(draft_count + confirmed_count) :]

            for mo in done_mo:
                await client.execute_kw(MrpModelName.MRP_ORDER.value, "button_mark_done", [mo["id"]])

            logger.succeed(f"Diversified Manufacturing Order statuses: {len(manufacturing_orders)} total orders")
        except Exception as e:
            logger.fail(f"Failed to diversify MO statuses: {e}")
