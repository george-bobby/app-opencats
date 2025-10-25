import random
import time

from faker import Faker

from apps.odooinventory.config.constants import MrpModelName, ProductModelName, StockModelName
from apps.odooinventory.config.settings import settings
from apps.odooinventory.utils.odoo import OdooClient
from common.load_json import load_json
from common.logger import logger


faker = Faker("en_US")


async def insert_bill_of_materials():
    bill_of_materials = load_json(settings.DATA_PATH.joinpath("bill_of_materials.json"))

    logger.start("Creating Bill of Materials (BOM) for products...")
    async with OdooClient() as client:
        products = await client.search_read(
            model=ProductModelName.PRODUCT_TEMPLATE.value,
            domain=[("type", "=", "consu"), ("default_code", "ilike", "FIN-%")],
            fields=["id", "name"],
        )
        categories = await client.search_read(
            model=ProductModelName.PRODUCT_CATEGORY.value,
            domain=[("parent_id.name", "=", "Manufacturing")],
            fields=["id", "name"],
        )
        work_centers = await client.search_read(
            model=MrpModelName.MRP_WORK_CENTER.value,
            fields=["id", "name", "code"],
        )
        locations = await client.search_read(
            model=StockModelName.STOCK_LOCATION.value,
            domain=[("usage", "=", "internal"), ("name", "=", "Stock")],
            fields=["id", "name", "complete_name"],
        )

        products_lookup = {product["name"]: product for product in products}
        work_centers_lookup = {wc["name"]: wc for wc in work_centers}
        categories_lookup = {category["name"]: category for category in categories}

        for bom in bill_of_materials:
            product_id = products_lookup.get(bom["product"], {}).get("id")

            if not product_id:
                logger.warning(f"Product {bom['product']} not found in Odoo.")
                continue

            components = bom["components"]
            operations = bom["operations"]

            bom_data = {
                "product_qty": 1,
                "product_tmpl_id": product_id,
                "code": faker.numerify(text="BOM-####"),
                "produce_delay": random.randint(0, 3),
                "days_to_prepare_mo": random.randint(0, 2),
                "consumption": "warning",
                "ready_to_produce": "all_available",
            }
            bom_id = await client.create(MrpModelName.MRP_BOM.value, bom_data)

            for operation in operations:
                work_center_id = work_centers_lookup.get(operation["work_center"], {}).get("id")
                if not work_center_id:
                    logger.warning(f"Work center {operation['work_center']} not found for BOM ID {bom_id}.")
                    continue
                operation_data = {
                    "name": operation["name"],
                    "workcenter_id": work_center_id,
                    "bom_id": bom_id,
                    "note": operation["description"],
                    "time_mode": "manual",
                    "time_cycle": operation["duration"],
                    "time_cycle_manual": operation["duration"],
                    "worksheet_type": "text",
                }
                await client.create(MrpModelName.MRP_OPERATION.value, operation_data)

            component_ids = []
            for component in components:
                category_id = categories_lookup.get(component["category"], {}).get("id")
                if not category_id:
                    category_id = random.choice(categories)["id"]
                val = {
                    "name": component["name"],
                    "categ_id": category_id,
                    "type": "consu",
                    "is_storable": True,
                    "list_price": 0,
                    "standard_price": 0,
                    # "sale_ok": False,
                    # "purchase_ok": True,
                    # "taxes_id": [],
                    "barcode": faker.numerify(text="##-####-####"),
                    "default_code": faker.numerify(text="COMP-####"),
                    # "route_ids": [routes[0]["id"]],
                }
                try:
                    component_id = await client.create(ProductModelName.PRODUCT_TEMPLATE.value, val)
                    component_ids.append(component_id)

                    time.sleep(0.1)  # To avoid hitting API rate limits

                    await client.create(
                        StockModelName.STOCK_QUANT.value,
                        {
                            "product_id": component_id,
                            "location_id": random.choice(locations)["id"],
                            "quantity": random.randint(200, 400),
                            "available_quantity": random.randint(200, 400),
                        },
                    )
                except Exception as e:
                    logger.fail(f"Failed to create component {component['name']}: {e}")
                    raise RuntimeError(f"Failed to create component {component['name']}: {e}")

            for comp_id in component_ids:
                bom_line_data = {
                    "bom_id": bom_id,
                    "product_id": comp_id,
                    "product_qty": random.randint(5, 10),
                }
                try:
                    await client.create(MrpModelName.MRP_BOM_LINE.value, bom_line_data)
                except Exception as e:
                    logger.fail(f"Failed to create BOM lines for product ID {comp_id}: {e}")
                    raise RuntimeError(f"Failed to create BOM lines for product ID {comp_id}: {e}")

    logger.succeed(f"Created {len(bill_of_materials)} Bill of Materials (BOMs) successfully.")
