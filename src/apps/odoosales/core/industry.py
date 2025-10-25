from apps.odoosales.config.constants import ResModelName
from apps.odoosales.config.settings import settings
from apps.odoosales.utils.odoo import OdooClient
from common.logger import logger


async def get_industries():
    async with OdooClient() as client:
        industries = await client.search_read(ResModelName.RES_PARTNER_INDUSTRY.value, [], ["id", "name"])
        return industries


async def insert_industry():
    logger.start("Inserting industry")
    async with OdooClient() as client:
        industries = await get_industries()
        if settings.DATA_THEME_SUBJECT in [i["name"] for i in industries]:
            return
        await client.create(ResModelName.RES_PARTNER_INDUSTRY.value, {"name": settings.DATA_THEME_SUBJECT})
    logger.succeed(f"Inserted {settings.DATA_THEME_SUBJECT} industry")
