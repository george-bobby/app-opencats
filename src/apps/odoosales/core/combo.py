import random

from apps.odoosales.config.constants import ProductModelName
from apps.odoosales.config.settings import settings
from apps.odoosales.utils.faker import faker
from apps.odoosales.utils.odoo import OdooClient
from common.load_json import load_json
from common.logger import logger


async def insert_combo_choices():
    """
    Inserts combo choices into the Odoo database based on combo.json.
    Creates product.combo and product.combo.item records.
    Then creates a sellable product.template of type 'combo' linked to the product.combo.
    """
    logger.start("Inserting combo choices...")

    combos = load_json(str(settings.DATA_PATH.joinpath("combo.json")))
    if not combos:
        logger.fail("No combos found in combo.json")
        return

    async with OdooClient() as client:
        available_templates = await client.search_read(
            "product.template",
            [("sale_ok", "=", True)],
            ["id", "name", "list_price"],
            limit=500,
        )
        if not available_templates:
            logger.fail("No available product.template records found to create combos from.")
            return

        template_to_all_variants = {}
        for template in available_templates:
            products = await client.search_read(
                ProductModelName.PRODUCT_PRODUCT.value,
                [("product_tmpl_id", "=", template["id"]), ("sale_ok", "=", True)],
                ["id", "display_name", "list_price", "standard_price"],
                limit=10,
            )
            if products:
                template_to_all_variants[template["name"]] = [
                    {
                        "id": p["id"],
                        "name": template["name"],
                        "variant_name": p["display_name"],
                        "template_id": template["id"],
                        "list_price": p.get("list_price", 0.0),
                        "standard_price": p.get("standard_price", 0.0),
                    }
                    for p in products
                ]

        items_to_process = [(combo, template_to_all_variants) for combo in combos]

        async with OdooClient() as client:
            for combo_data, _ in items_to_process:
                combo_name = combo_data.get("name", "").strip()
                product_names = combo_data.get("products", [])

                if not combo_name or not product_names:
                    continue

                all_available_variants = []
                for product_name in product_names:
                    product_name = product_name.strip()
                    if product_name in template_to_all_variants:
                        variants = template_to_all_variants[product_name]
                        all_available_variants.extend(variants)

                if len(all_available_variants) >= 3:
                    num_variants_to_select = min(5, len(all_available_variants))
                    num_variants_to_select = max(3, num_variants_to_select)
                    matched_products = random.sample(all_available_variants, num_variants_to_select)
                else:
                    matched_products = all_available_variants

                if len(matched_products) < 2:
                    continue

                try:
                    product_combo_data = {"name": combo_name, "company_id": 1}
                    product_combo_id = await client.create("product.combo", product_combo_data)

                    for product_detail in matched_products:
                        await client.create(
                            "product.combo.item",
                            {
                                "combo_id": product_combo_id,
                                "company_id": 1,
                                "product_id": product_detail["id"],
                            },
                        )

                    combo_list_price = sum(p["list_price"] for p in matched_products)
                    combo_list_price_with_discount = round(combo_list_price * 0.95, 2)

                    base_code_name = "".join(filter(str.isalnum, combo_name))[:10].upper()
                    combo_default_code = f"CMB-TPL-{base_code_name}-{faker.numerify('##')}"

                    combo_template_data = {
                        "name": combo_name,
                        "type": "combo",
                        "list_price": combo_list_price_with_discount,
                        "default_code": combo_default_code,
                        "sale_ok": True,
                        "is_storable": False,
                        "company_id": 1,
                        "combo_ids": [(6, 0, [product_combo_id])],
                    }

                    await client.create("product.template", combo_template_data)

                except Exception as e:
                    logger.warning(f"Skip creating combo '{combo_name}': {e}")
                    continue
        logger.succeed("Successfully created combo choices.")
