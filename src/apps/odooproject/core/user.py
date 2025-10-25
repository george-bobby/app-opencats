from apps.odooproject.config.constants import ResModelName
from apps.odooproject.config.settings import settings
from apps.odooproject.utils.odoo import OdooClient
from common.load_json import load_json
from common.logger import logger


async def insert_users():
    users = load_json(settings.DATA_PATH.joinpath("users.json"))

    logger.start(f"Inserting {len(users)} users...")
    async with OdooClient() as client:
        user_records = []
        for user in users:
            user_data = {
                "name": user["name"],
                "login": user["email"],
                "email": user["email"],
                "active": True,
                "groups_id": [1],
            }
            user_records.append(user_data)

        await client.create(ResModelName.RES_USERS.value, [user_records])
    logger.succeed(f"Inserted {len(users)} users successfully!")
