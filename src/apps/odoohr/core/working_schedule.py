"""Manages working schedules and time attendance rules."""

from apps.odoohr.config.constants import HRModelName
from apps.odoohr.config.settings import settings
from apps.odoohr.utils.load_json import load_json
from apps.odoohr.utils.odoo import OdooClient
from common.logger import logger


async def insert_working_times(calendar_id):
    working_times = load_json(settings.DATA_PATH.joinpath("working_times.json"))

    logger.start(f"Inserting {len(working_times)} working times for calendar ID {calendar_id}")
    async with OdooClient() as client:
        existing_working_times = await client.search_read(HRModelName.RESOURCE_CALENDAR_ATTENDANCE.value, [("calendar_id", "=", calendar_id)], ["id"])
        if existing_working_times:
            await client.unlink(HRModelName.RESOURCE_CALENDAR_ATTENDANCE.value, [e["id"] for e in existing_working_times])

        for wdt in working_times:
            wdt["calendar_id"] = calendar_id
            await client.create(HRModelName.RESOURCE_CALENDAR_ATTENDANCE.value, wdt)
    logger.succeed(f"Inserted {len(working_times)} working times for calendar ID {calendar_id}")


async def insert_working_schedules():
    working_schedules = load_json(settings.DATA_PATH.joinpath("working_schedules.json"))

    logger.start(f"Inserting {len(working_schedules)} working schedules...")
    async with OdooClient() as client:
        for ws in working_schedules:
            schedule_id = await client.create(HRModelName.RESOURCE_CALENDAR.value, ws)
            await insert_working_times(schedule_id)
    logger.succeed(f"Inserted {len(working_schedules)} working schedules")
