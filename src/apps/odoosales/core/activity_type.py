import contextlib

from apps.odoosales.config.settings import settings
from apps.odoosales.utils.odoo import OdooClient
from common.load_json import load_json
from common.logger import logger


async def insert_activity_types():
    await delete_default_activity_types()

    activity_model = "mail.activity.type"
    logger.start("Inserting activity types into Odoo...")

    activity_types = load_json(settings.DATA_PATH.joinpath("activity_types.json"))

    async with OdooClient() as client:
        data = []
        for activity in activity_types:
            data.append(
                {
                    "name": activity["name"],
                    "category": activity["category"],
                    "summary": activity["summary"],
                    "delay_count": activity["delay_count"],
                    "default_note": activity["default_note"],
                    "chaining_type": activity["chaining_type"],
                }
            )

        try:
            await client.create(activity_model, [data])
            logger.succeed(f"Inserted {len(activity_types)} activity types successfully.")
        except Exception as e:
            logger.fail(f"Failed to insert activity types: {e}")


async def delete_default_activity_types():
    """
    Deletes default activity types that are not needed.
    """
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
