"""Creates HR departments from JSON data."""

from apps.odoohr.config.constants import HRModelName
from apps.odoohr.config.settings import settings
from apps.odoohr.utils.load_json import load_json
from apps.odoohr.utils.odoo import OdooClient
from common.logger import logger


async def insert_departments():
    org = load_json(settings.DATA_PATH.joinpath("org.json"))

    departments = org["departments"] or []

    data = []
    for dept in departments:
        data.append({"name": dept["name"].strip()})

    logger.start(f"Inserting {len(departments)} departments")
    async with OdooClient() as client:
        await client.create(HRModelName.HR_DEPARTMENT.value, [data])

    logger.succeed(f"Inserted {len(departments)} departments")
