from apps.odoosales.config.constants import HRModelName
from apps.odoosales.config.settings import settings
from apps.odoosales.utils.odoo import OdooClient
from common.load_json import load_json
from common.logger import logger


async def insert_departments():
    departments = load_json(settings.DATA_PATH.joinpath("departments.json"))

    data = []
    for dept in departments:
        data.append({"name": dept["name"].strip()})

    logger.start(f"Inserting {len(departments)} departments")
    async with OdooClient() as client:
        await client.create(HRModelName.HR_DEPARTMENT.value, [data])

    logger.succeed(f"Inserted {len(departments)} departments")
