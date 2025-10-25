import asyncio
from typing import Any

from apps.medusa.config.constants import PRODUCTS_FILEPATH
from apps.medusa.utils.api_utils import MedusaAPIUtils
from apps.medusa.utils.data_utils import load_json_file
from common.logger import logger


def extract_inventory_item_id(variant: dict[str, Any]) -> str | None:
    inventory_items = variant.get("inventory_items", [])
    if inventory_items:
        first_item = inventory_items[0]
        if isinstance(first_item, dict):
            return first_item.get("inventory_item_id") or first_item.get("id")
        if isinstance(first_item, str):
            return first_item

    if inventory_item_id := variant.get("inventory_item_id"):
        return inventory_item_id

    if variant_id := variant.get("id"):
        return variant_id

    inventory_quantity = variant.get("inventory_quantity")
    if isinstance(inventory_quantity, dict):
        return inventory_quantity.get("inventory_item_id")

    return None


def extract_variant_attributes(variant: dict[str, Any]) -> dict[str, Any] | None:
    required_fields = ["material", "hs_code", "origin_country", "length", "width", "height", "weight", "mid_code"]

    if not all(field in variant for field in required_fields):
        return None

    return {
        "material": variant["material"],
        "hs_code": variant["hs_code"],
        "origin_country": variant["origin_country"],
        "length": variant["length"],
        "width": variant["width"],
        "height": variant["height"],
        "weight": variant["weight"],
        "mid_code": variant["mid_code"],
    }


def extract_product_attributes(product: dict[str, Any]) -> dict[str, Any] | None:
    variants = product.get("variants", [])
    if not variants:
        return None

    first_variant = variants[0]
    required_fields = ["material", "hs_code", "origin_country", "length", "width", "height", "weight", "mid_code"]

    if not all(field in first_variant for field in required_fields):
        return None

    return {
        "material": first_variant["material"],
        "hs_code": first_variant["hs_code"],
        "origin_country": first_variant["origin_country"],
        "length": first_variant["length"],
        "width": first_variant["width"],
        "height": first_variant["height"],
        "weight": first_variant["weight"],
        "mid_code": first_variant["mid_code"],
    }


def validate_products_data(products: list[dict[str, Any]]) -> dict[str, Any]:
    logger.info("Validating products data for attribute completeness...")

    required_attributes = ["material", "hs_code", "origin_country", "length", "width", "height", "weight", "mid_code"]

    total_variants = 0
    variants_with_attributes = 0
    variants_missing_attributes = 0

    for product in products:
        variants = product.get("variants", [])
        for variant in variants:
            total_variants += 1
            missing_fields = [field for field in required_attributes if field not in variant or variant[field] is None]

            if missing_fields:
                variants_missing_attributes += 1
            else:
                variants_with_attributes += 1

    logger.info(f"Validation complete - Total variants: {total_variants}, Complete: {variants_with_attributes}, Incomplete: {variants_missing_attributes}")

    return {
        "total_variants": total_variants,
        "complete": variants_with_attributes,
        "incomplete": variants_missing_attributes,
        "valid": variants_missing_attributes == 0,
    }


def build_sku_to_attributes_map(generated_products: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    logger.info("Building SKU to attributes mapping...")

    sku_to_attributes = {}

    for product in generated_products:
        variants = product.get("variants", [])
        for variant in variants:
            sku = variant.get("sku")
            if sku:
                attributes = extract_variant_attributes(variant)
                if attributes:
                    sku_to_attributes[sku] = attributes

    logger.info(f"SKU mapping built - {len(sku_to_attributes)} SKUs mapped to attributes")
    return sku_to_attributes


def build_product_attributes_map(generated_products: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    logger.info("Building product to attributes mapping...")

    product_to_attributes = {}

    for product in generated_products:
        title = product.get("title", "").lower()
        handle = product.get("handle", "").lower()

        if title or handle:
            attributes = extract_product_attributes(product)
            if attributes:
                if title:
                    product_to_attributes[title] = attributes
                if handle:
                    product_to_attributes[handle] = attributes

    logger.info(f"Product mapping built - {len(product_to_attributes)} products mapped to attributes")
    return product_to_attributes


async def get_product_variants_with_inventory(session, base_url: str, product_id: str) -> list[dict[str, Any]]:
    try:
        from apps.medusa.utils.api_auth import get_medusa_auth_headers

        url = f"{base_url}/admin/products/{product_id}/variants"
        headers = get_medusa_auth_headers()
        params = {
            "order": "variant_rank",
            "fields": "title,sku,*options,*inventory_items.inventory_item_id,*inventory_items.id",
        }

        async with session.get(url, headers=headers, params=params) as response:
            if response.status == 200:
                result = await response.json()
                return result.get("variants", [])
            return []
    except Exception as e:
        logger.error(f"Error fetching variants for product {product_id}: {e}")
        return []


async def get_all_products_with_variants(api_utils: MedusaAPIUtils) -> list[dict[str, Any]]:
    import aiohttp

    from apps.medusa.utils.api_auth import get_medusa_base_url

    logger.info("Fetching all products with variants from Medusa API...")

    all_products = []
    offset = 0
    limit = 100

    while True:
        products = await api_utils.fetch_products(limit=limit, offset=offset)
        if not products:
            break

        all_products.extend(products)
        logger.info(f"Fetched {len(all_products)} products so far...")

        if len(products) < limit:
            break

        offset += limit

    logger.info(f"Fetching detailed variant information for {len(all_products)} products...")

    base_url = get_medusa_base_url()
    async with aiohttp.ClientSession() as session:
        for idx, product in enumerate(all_products, 1):
            product_id = product.get("id")
            if product_id:
                variants = await get_product_variants_with_inventory(session, base_url, product_id)
                product["variants"] = variants
                if idx % 10 == 0:
                    logger.info(f"Processed {idx}/{len(all_products)} products for variant details")

    logger.info("Successfully fetched all product and variant information")
    return all_products


async def update_product_attributes(product_id: str, product_title: str, attributes: dict[str, Any], api_utils: MedusaAPIUtils) -> bool:  # noqa: ARG001
    try:
        status, _ = await api_utils._make_post_request(f"/admin/products/{product_id}", attributes)
        return status in (200, 201)
    except Exception:
        return False


async def update_variant_attributes(inventory_item_id: str, variant_title: str, attributes: dict[str, Any], api_utils: MedusaAPIUtils) -> bool:  # noqa: ARG001
    try:
        status, _ = await api_utils._make_post_request(f"/admin/inventory-items/{inventory_item_id}", attributes)

        if status in (200, 201):
            return True

        status, _ = await api_utils._make_post_request(f"/admin/variants/{inventory_item_id}", attributes)
        return status in (200, 201)
    except Exception:
        return False


async def process_all_variants(api_utils: MedusaAPIUtils) -> dict[str, int]:
    logger.info(f"Loading products data from: {PRODUCTS_FILEPATH}")

    generated_products = load_json_file(PRODUCTS_FILEPATH, default=[])

    if not generated_products:
        logger.error("No products found in products.json. Exiting.")
        return {"total": 0, "successful": 0, "failed": 0, "skipped": 0, "missing_attributes": 0}

    logger.info(f"Successfully loaded {len(generated_products)} products from file")

    validation = validate_products_data(generated_products)

    if not validation["valid"]:
        logger.warning(f"Warning: {validation['incomplete']} variants are missing required attributes")

    sku_to_attributes = build_sku_to_attributes_map(generated_products)
    product_to_attributes = build_product_attributes_map(generated_products)

    api_products = await get_all_products_with_variants(api_utils)

    if not api_products:
        logger.warning("No products found in Medusa API. Exiting.")
        return {"total": 0, "successful": 0, "failed": 0, "skipped": 0, "missing_attributes": 0}

    total_variants = sum(len(product.get("variants", [])) for product in api_products)
    total_products = len(api_products)

    logger.info(f"Starting attribute update process - Total products: {total_products}, Total variants: {total_variants}")
    logger.info("=" * 60)

    products_successful = 0
    products_failed = 0
    products_skipped = 0

    successful = 0
    failed = 0
    skipped = 0
    missing_attributes = 0
    no_inventory_id = 0
    no_sku = 0

    for idx, product in enumerate(api_products, 1):
        product_id = product.get("id")
        product_title = product.get("title", "Unknown")
        product_handle = product.get("handle", "").lower()

        logger.info(f"[Product {idx}/{total_products}] Processing: '{product_title}'")

        product_key = product_title.lower() if product_title != "Unknown" else product_handle
        product_attributes = product_to_attributes.get(product_key)

        if product_attributes and product_id:
            result = await update_product_attributes(product_id, product_title, product_attributes, api_utils)
            if result:
                products_successful += 1
                logger.info(f"[Product {idx}/{total_products}] ✓ Updated product-level attributes for: '{product_title}'")
            else:
                products_failed += 1
                logger.error(f"[Product {idx}/{total_products}] ✗ Failed to update product-level attributes for: '{product_title}'")
        else:
            products_skipped += 1
            logger.info(f"[Product {idx}/{total_products}] ⊘ Skipped (no attributes found) for: '{product_title}'")

        variants = product.get("variants", [])
        if not variants:
            continue

        variant_count = len(variants)
        logger.info(f"[Product {idx}/{total_products}] Processing {variant_count} variant(s) for: '{product_title}'")

        for v_idx, variant in enumerate(variants, 1):
            variant_title = variant.get("title", "Unknown Variant")
            sku = variant.get("sku")
            inventory_item_id = extract_inventory_item_id(variant)

            if not inventory_item_id:
                no_inventory_id += 1
                skipped += 1
                logger.warning(f"  [Variant {v_idx}/{variant_count}] ⊘ Skipped '{variant_title}' - No inventory item ID")
                continue

            if not sku:
                no_sku += 1
                skipped += 1
                logger.warning(f"  [Variant {v_idx}/{variant_count}] ⊘ Skipped '{variant_title}' - No SKU")
                continue

            attributes = sku_to_attributes.get(sku)

            if not attributes:
                missing_attributes += 1
                logger.warning(f"  [Variant {v_idx}/{variant_count}] ⊘ Skipped '{variant_title}' (SKU: {sku}) - Missing attributes")
                continue

            result = await update_variant_attributes(inventory_item_id, variant_title, attributes, api_utils)

            if result:
                successful += 1
                logger.info(f"  [Variant {v_idx}/{variant_count}] ✓ Updated '{variant_title}' (SKU: {sku})")
            else:
                failed += 1
                logger.error(f"  [Variant {v_idx}/{variant_count}] ✗ Failed to update '{variant_title}' (SKU: {sku})")

    logger.info("=" * 60)

    product_success_rate = (products_successful / total_products * 100) if total_products > 0 else 0
    variant_success_rate = (successful / total_variants * 100) if total_variants > 0 else 0

    logger.info(
        f"Product-level attributes update - "
        f"Total: {total_products}, "
        f"Successful: {products_successful}, "
        f"Failed: {products_failed}, "
        f"Skipped: {products_skipped}, "
        f"Success Rate: {product_success_rate:.1f}%"
    )

    logger.info(f"Variant-level attributes update - Total: {total_variants}, Successful: {successful}, Failed: {failed}, Skipped: {skipped}, Success Rate: {variant_success_rate:.1f}%")

    if missing_attributes > 0:
        logger.warning(f"Variants missing attributes in source data: {missing_attributes}")
    if no_inventory_id > 0:
        logger.warning(f"Variants without inventory item ID: {no_inventory_id}")
    if no_sku > 0:
        logger.warning(f"Variants without SKU: {no_sku}")

    return {
        "total_products": total_products,
        "products_successful": products_successful,
        "products_failed": products_failed,
        "products_skipped": products_skipped,
        "total_variants": total_variants,
        "variants_successful": successful,
        "variants_failed": failed,
        "variants_skipped": skipped,
        "missing_attributes": missing_attributes,
        "no_inventory_id": no_inventory_id,
        "no_sku": no_sku,
    }


async def seed_product_attributes():
    logger.info("=" * 60)
    logger.info("Starting Product Attributes Seeding Script")
    logger.info("=" * 60)

    async with MedusaAPIUtils() as api_utils:
        result = await process_all_variants(api_utils)

    logger.info("=" * 60)
    logger.info("Product Attributes Seeding Script Completed")
    logger.info("=" * 60)

    return result


if __name__ == "__main__":
    asyncio.run(seed_product_attributes())
