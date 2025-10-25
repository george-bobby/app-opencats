"""Creates and manages system users with groups."""

import faker

from apps.odoohr.config.constants import HRModelName, ResModelName
from apps.odoohr.config.settings import settings
from apps.odoohr.utils.load_json import load_json
from apps.odoohr.utils.odoo import OdooClient
from common.logger import logger


async def get_admin_group_ids():
    async with OdooClient() as client:
        group_data = load_json(settings.DATA_PATH.joinpath("groups.json"))
        group_names = [g["name"] for g in group_data]
        groups = await client.search_read(
            ResModelName.GROUP.value,
            [("name", "in", group_names)],
            ["id"],
        )
        if not groups:
            return []
        return [g["id"] for g in groups]


async def insert_users(count=256):
    users = []
    admin_group_ids = await get_admin_group_ids()

    logger.start("Inserting users")
    async with OdooClient() as client:
        departments = await client.search_read(HRModelName.HR_DEPARTMENT.value, [], ["id"])

        if not departments:
            return

        for idx in range(count):
            contact = faker.contact()

            user_data = {
                "name": contact["full_name"],
                "login": contact["email"],
                "email": contact["email"],
                "tz": "America/New_York",
                "is_company": False,
                "groups_id": [1],
            }

            if idx == 0:
                user_data["groups_id"] = admin_group_ids

            users.append(user_data)

        await client.create(ResModelName.USER.value, [users])
        logger.succeed(f"Inserted {len(users)} users")


async def delete_users():
    async with OdooClient() as client:
        users = await client.search_read(ResModelName.USER.value, [("id", ">", 5)], ["id", "name"])
        await client.unlink(ResModelName.USER.value, [u["id"] for u in users])
