from apps.odooinventory.config.settings import settings
from apps.odooinventory.utils.odoo import OdooClient
from common.load_json import load_json
from common.logger import logger


async def insert_units_of_measure():
    units_of_measures = load_json(settings.DATA_PATH.joinpath("units_of_measures.json"))

    async with OdooClient() as client:
        for uom in units_of_measures:
            try:
                uom["category_id"] = 1

                await client.create("uom.uom", uom)
            except Exception as e:
                logger.error(f"Failed to create unit of measure {uom['name']}: {e}")
                raise
    logger.succeed(f"Inserted {len(units_of_measures)} units of measure")
