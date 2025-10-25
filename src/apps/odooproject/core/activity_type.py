import contextlib
import random

from apps.odooproject.config.constants import MailModelName
from apps.odooproject.config.settings import settings
from apps.odooproject.utils.odoo import OdooClient
from common.load_json import load_json
from common.logger import logger


async def insert_activity_types():
    await delete_default_activity_types()

    activity_types = load_json(settings.DATA_PATH.joinpath("activity_types.json"))

    logger.start(f"Inserting {len(activity_types)} activity types into Odoo...")
    async with OdooClient() as client:
        existing_types = await client.search_read("mail.activity.type", [], ["id", "name"])
        types_lookup = {at["name"]: at for at in existing_types}
        act_type_records = []
        for activity in activity_types:
            if activity["name"] not in types_lookup:
                act_type_records.append(
                    {
                        "name": activity["name"],
                        "category": activity["category"],
                        "delay_count": random.randint(1, 3),
                        "default_note": activity["default_note"],
                        "chaining_type": activity["chaining_type"],
                        "summary": activity["summary"],
                        "icon": activity["icon"],
                    }
                )
            else:
                await client.write(
                    "mail.activity.type",
                    types_lookup[activity["name"]]["id"],
                    {
                        "delay_count": random.randint(1, 3),
                        "default_note": activity["default_note"],
                        "chaining_type": activity["chaining_type"],
                        "summary": activity["summary"],
                        "icon": activity["icon"],
                    },
                )

        await client.create(MailModelName.MAIL_ACTIVITY_TYPE.value, [act_type_records])
        logger.succeed(f"Inserted {len(activity_types)} activity types successfully.")


async def delete_default_activity_types():
    logger.start("Deleting default activity types...")
    async with OdooClient() as client:
        with contextlib.suppress(Exception):
            # Fetch all activity types
            activity_types = await client.search_read("mail.activity.type", [], ["id", "name"])

            # Filter out the default activity types
            default_activity_names = ["Call", "Email", "Meeting"]
            to_delete = [at["id"] for at in activity_types if at["name"] in default_activity_names]

            if to_delete:
                await client.unlink("mail.activity.type", to_delete)
