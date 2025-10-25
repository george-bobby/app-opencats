from apps.odooinventory.config.constants import StockModelName
from apps.odooinventory.config.settings import settings
from apps.odooinventory.utils.odoo import OdooClient
from common.load_json import load_json
from common.logger import logger


async def get_warehouse_ids():
    """
    Get all warehouse ids from Odoo.
    """
    async with OdooClient() as client:
        warehouses = await client.search_read("stock.warehouse", fields=["id"])

        if not warehouses:
            return []

        warehouse_ids = [warehouse["id"] for warehouse in warehouses]

        return warehouse_ids


async def insert_warehouses():
    warehouses = load_json(settings.DATA_PATH.joinpath("warehouses.json"))

    async with OdooClient() as client:
        for idx, warehouse in enumerate(warehouses):
            warehouse["partner_id"] = 1
            try:
                if idx == 0:
                    await client.write(StockModelName.STOCK_WAREHOUSE.value, 1, warehouse)
                else:
                    await client.create("stock.warehouse", warehouse)

            except Exception as e:
                raise ValueError(f"Failed to create warehouse {warehouse['name']}: {e}") from e
        logger.succeed(f"Inserted {len(warehouses)} warehouses successfully.")
