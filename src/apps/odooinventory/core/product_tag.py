import random

from apps.odooinventory.config.constants import ProductModelName
from apps.odooinventory.config.settings import settings
from apps.odooinventory.utils.odoo import OdooClient
from common.load_json import load_json
from common.logger import logger


async def insert_product_tags():
    tags = load_json(settings.DATA_PATH.joinpath("product_tags.json"))

    tag_records = []
    for tag in tags:
        tag_data = {"name": tag["name"], "color": random.randint(1, 11)}
        tag_records.append(tag_data)

    async with OdooClient() as client:
        try:
            await client.create(ProductModelName.PRODUCT_TAG.value, [tag_records])
            logger.succeed(f"Inserted {len(tags)} product tags successfully")
        except Exception as e:
            raise ValueError(f"Error inserting product tags: {e}") from e
