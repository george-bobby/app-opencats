from faker import Faker

from apps.odoosales.config.settings import settings
from apps.odoosales.core.warehouse import get_warehouse_ids
from apps.odoosales.utils.odoo import OdooClient
from common.load_json import load_json
from common.logger import logger


faker = Faker("en_US")


async def get_operation_types():
    """
    Get all inventory operation types from Odoo.
    """
    async with OdooClient() as client:
        response = await client.search_read(
            "stock.picking.type",
        )
        # logger.info(f"Inventory operation types: {response}")
        return response


async def insert_operation_types():
    operation_types = load_json(settings.DATA_PATH.joinpath("operation_types.json"))

    created_types = {}
    warehouse_ids = await get_warehouse_ids()

    async with OdooClient() as client:
        # First pass: create all operation types
        for op_type in operation_types:
            # Create a copy of the operation type without the return_type field
            op_data = {k: v for k, v in op_type.items() if k != "return_type"}
            op_data["warehouse_id"] = faker.random_element(warehouse_ids)

            try:
                type_id = await client.create("stock.picking.type", op_data)
                created_types[op_type["name"]] = type_id
            except Exception as e:
                logger.error(f"Failed to create operation type {op_type['name']}: {e}")
                raise
        logger.succeed(f"Created {len(created_types)} operation types: {', '.join(created_types.keys())}")

        # Second pass: update return picking type references
        for op_type in operation_types:
            return_type_name = op_type.get("return_type")
            if return_type_name and return_type_name in created_types:
                try:
                    await client.write(
                        "stock.picking.type",
                        created_types[op_type["name"]],
                        {"return_picking_type_id": created_types[return_type_name]},
                    )
                    logger.info(f"Updated {op_type['name']} with {return_type_name} as return type")
                except Exception as e:
                    logger.error(f"Failed to update return type for {op_type['name']}: {e}")

    return created_types
