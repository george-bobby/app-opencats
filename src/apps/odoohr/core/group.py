"""Creates user groups with inheritance relationships."""

from apps.odoohr.config.constants import MiscEnum, ResModelName
from apps.odoohr.config.settings import settings
from apps.odoohr.utils.load_json import load_json
from apps.odoohr.utils.odoo import OdooClient
from common.logger import logger


async def insert_groups():
    groups = load_json(settings.DATA_PATH.joinpath("groups.json"))

    data = []

    logger.start("Inserting groups")
    async with OdooClient() as client:
        for group in groups:
            inherits = group.get("inherits", [])
            group_ids = []
            for inherit in inherits:
                [category, group_name] = inherit.split(" / ")
                categories = await client.search_read(
                    MiscEnum.IR_MODULE_CATEGORY.value,
                    [("name", "=", category), ("parent_id", "!=", None)],
                    ["id", "name"],
                )
                groups = await client.search_read(
                    ResModelName.GROUP.value,
                    [("category_id", "in", [c["id"] for c in categories]), ("name", "=", group_name)],
                    ["id", "name"],
                )
                if groups:
                    group_ids += [g["id"] for g in groups]
            data.append(
                {
                    "name": group["name"],
                    "implied_ids": group_ids,
                }
            )
        await client.create(ResModelName.GROUP.value, [data])
    logger.succeed(f"Inserted {len(groups)} groups")
