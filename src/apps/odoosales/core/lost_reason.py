import contextlib

from apps.odoosales.config.settings import settings
from apps.odoosales.utils.odoo import OdooClient
from common.load_json import load_json
from common.logger import logger


async def insert_lost_reasons():
    await delete_default_lost_reasons()

    lost_reasons = load_json(settings.DATA_PATH.joinpath("lost_reasons.json"))

    data = []
    logger.start("Inserting lost reasons into Odoo...")
    async with OdooClient() as client:
        for reason in lost_reasons:
            data.append({"name": reason["name"]})

        await client.create("crm.lost.reason", [data])
        logger.succeed("Inserted lost reasons successfully.")


async def delete_default_lost_reasons():
    logger.start("Deleting default lost reasons...")
    async with OdooClient() as client:
        with contextlib.suppress(Exception):
            lost_reasons = await client.search_read("crm.lost.reason", [], ["id", "name"])

            default_lost_reasons = ["No longer interested", "Found a better price"]
            to_delete = [lr["id"] for lr in lost_reasons if lr["name"] in default_lost_reasons]

            if to_delete:
                await client.unlink("crm.lost.reason", to_delete)
