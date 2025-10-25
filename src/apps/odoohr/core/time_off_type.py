"""Manages time off types and leave categories."""

from apps.odoohr.config.constants import HRModelName
from apps.odoohr.config.settings import settings
from apps.odoohr.utils.load_json import load_json
from apps.odoohr.utils.odoo import OdooClient
from common.logger import logger


async def insert_time_off_types():
    await delete_default_time_off_types()

    time_off_config = load_json(settings.DATA_PATH.joinpath("time_off.json"))
    time_off_types = time_off_config.get("types", [])

    logger.start("Inserting time off types")
    async with OdooClient() as client:
        await client.create(HRModelName.HR_LEAVE_TYPE.value, [time_off_types])
    logger.succeed(f"Inserted {len(time_off_types)} time off types")


async def delete_default_time_off_types():
    logger.start("Deleting default time off types")
    async with OdooClient() as client:
        time_off_types = await client.search_read(HRModelName.HR_LEAVE_TYPE.value, [], ["id", "name"])

        if time_off_types:
            await client.unlink(HRModelName.HR_LEAVE_TYPE.value, [t["id"] for t in time_off_types])
    logger.succeed(f"Deleted {len(time_off_types)} default time off types")
