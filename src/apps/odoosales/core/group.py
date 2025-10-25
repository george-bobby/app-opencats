from apps.odoosales.config.constants import ResModelName
from apps.odoosales.utils.odoo import OdooClient
from common.logger import logger


GROUPS = [
    {"name": "Sales Manager", "category": "Sales"},
]


async def insert_groups():
    logger.start("Inserting groups into Odoo...")
    async with OdooClient() as client:
        data = []
        for group in GROUPS:
            category = await client.search_read(
                "ir.module.category",
                [("name", "=", group["category"])],
                ["id"],
                limit=1,
            )
            inherited_group = await client.search_read(
                ResModelName.RES_GROUP.value,
                [("category_id", "=", category[0]["id"])],
                ["id"],
                limit=1,
            )
            data.append({"name": group["name"], "implied_ids": [1, inherited_group[0]["id"]]})
        await client.create(ResModelName.RES_GROUP.value, [data])
        logger.succeed(f"Inserted {len(GROUPS)} groups successfully.")
