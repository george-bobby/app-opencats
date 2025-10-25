from apps.odooinventory.config.settings import settings
from apps.odooinventory.utils.odoo import OdooClient
from common.load_json import load_json
from common.logger import logger


async def insert_locations():
    locations = load_json(settings.DATA_PATH.joinpath("locations.json"))

    async with OdooClient() as client:
        warehouses = await client.search_read("stock.warehouse", [], ["id", "code"])

        warehouses_lookup = {wh["code"]: wh["id"] for wh in warehouses}

        for location in locations:
            wh_id = warehouses_lookup.get(location["wh_code"])

            try:
                await client.create(
                    "stock.location",
                    {
                        "name": location["name"],
                        "usage": location["usage"],
                        "scrap_location": location.get("scrap_location", False),
                        "replenish_location": location.get("replenish_location", False),
                        "warehouse_id": wh_id,
                        "complete_name": location["name"],
                    },
                )

            except Exception as e:
                raise ValueError(f"Error creating location {location['name']}: {e}")

        logger.succeed(f"Inserted {len(locations)} locations for warehouses: {', '.join([w['code'] for w in warehouses])}")
