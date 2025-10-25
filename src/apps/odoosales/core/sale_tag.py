import random

from apps.odoosales.config.constants import CrmModelName
from apps.odoosales.config.settings import settings
from apps.odoosales.utils.odoo import OdooClient
from common.load_json import load_json
from common.logger import logger


async def insert_sale_tags():
    crm_tags = load_json(settings.DATA_PATH.joinpath("sale_tags.json"))

    crm_tag_records = []
    for tag in crm_tags:
        tag_data = {"name": tag["name"], "color": random.randint(1, 11)}
        crm_tag_records.append(tag_data)

    logger.start(f"Inserting {len(crm_tags)} sale tags...")
    async with OdooClient() as client:
        try:
            await client.create(CrmModelName.CRM_TAG.value, [crm_tag_records])
            logger.succeed(f"Inserted {len(crm_tags)} sale tags successfully")
        except Exception as e:
            raise ValueError(f"Error inserting sale tags: {e}") from e
