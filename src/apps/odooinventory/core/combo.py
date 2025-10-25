from faker import Faker

from apps.odooinventory.config.constants import ProductModelName
from apps.odooinventory.config.settings import settings
from apps.odooinventory.utils.odoo import OdooClient
from common.load_json import load_json
from common.logger import logger


faker = Faker("en_US")


async def insert_combo_choices():
    """
    Inserts combo choices into the Odoo database based on combo.json.
    Creates product.combo and product.combo.item records.
    Then creates a sellable product.template of type 'combo' linked to the product.combo.
    """
    logger.start("Inserting combo choices...")

    # Load combos from JSON file
    combos = load_json(str(settings.DATA_PATH.joinpath("combo.json")))

    if not combos:
        logger.fail("No combos found in combo.json")
        return

    async with OdooClient() as client:
        try:
            # Get all available product templates with their names for matching
            available_templates = await client.search_read(
                "product.template",
                [("sale_ok", "=", True)],
                [
                    "id",
                    "name",
                    "list_price",
                ],
                limit=500,
            )

            if not available_templates:
                logger.fail("No available product.template records found to create combos from.")
                return

            # Get product.product records for each template
            template_to_all_variants = {}
            template_name_to_id = {}

            for template in available_templates:
                template_name_to_id[template["name"]] = template["id"]

                # Get all product.product variants for this template
                products = await client.search_read(
                    ProductModelName.PRODUCT_PRODUCT.value,
                    [("product_tmpl_id", "=", template["id"]), ("sale_ok", "=", True)],
                    [
                        "id",
                        "display_name",
                        "list_price",
                        "standard_price",
                    ],
                    limit=10,  # Limit variants per template
                )

                if products:
                    # Store ALL variants for this template
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

            created_combos = 0
            skipped_combos = 0

            for combo_data in combos:
                combo_name = combo_data.get("name", "").strip()
                product_names = combo_data.get("products", [])

                if not combo_name or not product_names:
                    skipped_combos += 1
                    continue

                # Collect all variants from matched templates
                all_available_variants = []
                matched_template_names = []

                for product_name in product_names:
                    product_name = product_name.strip()
                    if product_name in template_to_all_variants:
                        variants = template_to_all_variants[product_name]
                        all_available_variants.extend(variants)
                        matched_template_names.append(product_name)
                    else:
                        logger.warning(f"Product template not found for combo '{combo_name}': {product_name}")

                # Select 3-5 variants randomly from all available variants
                import random

                if len(all_available_variants) >= 3:
                    num_variants_to_select = min(5, len(all_available_variants))
                    num_variants_to_select = max(3, num_variants_to_select)
                    matched_products = random.sample(all_available_variants, num_variants_to_select)
                else:
                    matched_products = all_available_variants

                # Skip combos with insufficient products
                if len(matched_products) < 2:
                    skipped_combos += 1
                    continue

                try:
                    # Create product.combo record
                    product_combo_data = {"name": combo_name}
                    product_combo_id = await client.create("product.combo", product_combo_data)

                    # Create product.combo.item records for each product
                    for product_detail in matched_products:
                        await client.create(
                            "product.combo.item",
                            {
                                "combo_id": product_combo_id,
                                "product_id": product_detail["id"],
                            },
                        )

                    # Calculate combo price (5% discount from sum of component prices)
                    combo_list_price = sum(p["list_price"] for p in matched_products)
                    combo_list_price_with_discount = round(combo_list_price * 0.95, 2)

                    # Create corresponding product.template
                    base_code_name = "".join(filter(str.isalnum, combo_name))[:10].upper()
                    combo_default_code = f"CMB-TPL-{base_code_name}-{faker.numerify('##')}"

                    combo_template_data = {
                        "name": combo_name,
                        "type": "combo",
                        "list_price": combo_list_price_with_discount,
                        "default_code": combo_default_code,
                        "sale_ok": True,
                        "is_storable": False,  # Typically False for kits/combos
                        "combo_ids": [(6, 0, [product_combo_id])],  # Link to the product.combo
                    }

                    await client.create("product.template", combo_template_data)
                    created_combos += 1

                except Exception as e:
                    logger.warning(f"Failed to create combo '{combo_name}': {e}")
                    skipped_combos += 1
                    continue

            if created_combos > 0:
                logger.succeed(f"Inserted {created_combos} combo choices successfully.")
            if skipped_combos > 0:
                logger.warning(f"Skipped {skipped_combos} combos due to errors or missing products.")

        except Exception as e:
            raise ValueError(f"An error occurred while processing combos: {e}")
