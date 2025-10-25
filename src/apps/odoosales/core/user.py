from faker import Faker

from apps.odoosales.config.constants import ResModelName
from apps.odoosales.config.settings import settings
from apps.odoosales.utils.odoo import OdooClient
from common.load_json import load_json
from common.logger import logger


faker = Faker()


async def insert_users():
    users = load_json(settings.DATA_PATH.joinpath("users.json"))

    user_records = []
    for user in users:
        user_records.append(
            {
                "name": user["name"],
                "login": user["email"],
                "email": user["email"],
                "active": True,
                "groups_id": [(6, 0, [1])],
            }
        )

    logger.start(f"Inserting {len(users)} users into Odoo...")
    async with OdooClient() as client:
        await client.create(ResModelName.RES_USERS.value, [user_records])
        logger.succeed(f"Inserted {len(users)} users")
