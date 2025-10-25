import asyncio
from typing import Any

from tenacity import retry, stop_after_attempt, wait_exponential

from apps.medusa.config.constants import CATEGORIES_FILEPATH, PRODUCTS_FILEPATH
from apps.medusa.utils.api_utils import MedusaAPIUtils
from apps.medusa.utils.data_utils import load_json_file
from common.logger import logger


def load_categories_data() -> list[dict[str, Any]]:
    categories = load_json_file(CATEGORIES_FILEPATH, default=[])
    if not isinstance(categories, list) or not categories:
        logger.warning("No categories data found")
        return []
    return categories


def load_products_data() -> list[dict[str, Any]]:
    products = load_json_file(PRODUCTS_FILEPATH, default=[])
    if not isinstance(products, list) or not products:
        logger.warning("No products data found")
        return []
    return products


def get_categories_with_no_products(categories: list[dict[str, Any]], products: list[dict[str, Any]]) -> list[dict[str, Any]]:
    category_product_count = {}

    for category in categories:
        category_name = category.get("name")
        if category_name:
            category_product_count[category_name] = 0

    for product in products:
        product_category = product.get("category")
        if product_category and product_category in category_product_count:
            category_product_count[product_category] += 1

    empty_categories = []
    for category in categories:
        category_name = category.get("name")
        if category_name and category_product_count.get(category_name, 0) == 0 and category.get("is_active", True):
            empty_categories.append(category)
            logger.info(f"Found empty category: {category_name}")

    return empty_categories


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=10))
async def deactivate_category(category_data: dict[str, Any], category_id: str, api_utils: MedusaAPIUtils) -> bool:
    """Deactivate a single product category in Medusa."""
    try:
        payload = {
            "name": category_data.get("name"),
            "description": category_data.get("description", ""),
            "handle": category_data.get("handle"),
            "is_active": False,
            "is_internal": category_data.get("is_internal", False),
        }

        endpoint = f"/admin/product-categories/{category_id}"
        status, _ = await api_utils._make_post_request(endpoint, payload)

        if status in (200, 201):
            logger.info(f"✓ Deactivated category: {category_data.get('name')}")
            return True
        else:
            logger.error(f"✗ Failed to deactivate category: {category_data.get('name')} (Status: {status})")
            return False

    except Exception as e:
        logger.error(f"Error deactivating category {category_data.get('name')}: {e}")
        raise


async def deactivate_empty_categories_internal(api_utils: MedusaAPIUtils) -> dict[str, int]:
    categories_data = load_categories_data()
    products_data = load_products_data()

    if not categories_data or not products_data:
        logger.warning("Missing categories or products data")
        return {"total": 0, "successful": 0, "failed": 0}

    api_categories = await api_utils.fetch_categories()
    if not api_categories:
        logger.error("Could not fetch categories from API")
        return {"total": 0, "successful": 0, "failed": 0}

    category_id_map = {}
    for api_cat in api_categories:
        handle = api_cat.get("handle")
        category_id = api_cat.get("id")
        if handle and category_id:
            category_id_map[handle] = category_id

    empty_categories = get_categories_with_no_products(categories_data, products_data)

    if not empty_categories:
        logger.info("No empty categories found - all categories have products!")
        return {"total": 0, "successful": 0, "failed": 0}

    logger.info(f"Found {len(empty_categories)} empty categories to deactivate")

    successful = 0
    failed = 0

    for category_data in empty_categories:
        handle = category_data.get("handle")

        if not handle or handle not in category_id_map:
            logger.warning(f"Could not find category ID for: {category_data.get('name')}")
            failed += 1
            continue

        category_id = category_id_map[handle]

        try:
            result = await deactivate_category(category_data, category_id, api_utils)

            if result:
                successful += 1
            else:
                failed += 1
        except Exception:
            failed += 1

    logger.info(f"Categories deactivated: {successful} successful, {failed} failed")

    return {"total": len(empty_categories), "successful": successful, "failed": failed}


async def deactivate_empty_categories() -> dict[str, int]:
    async with MedusaAPIUtils() as api_utils:
        if not api_utils.auth:
            logger.error("Authentication failed")
            return {"total": 0, "successful": 0, "failed": 0}

        return await deactivate_empty_categories_internal(api_utils)


if __name__ == "__main__":
    asyncio.run(deactivate_empty_categories())
