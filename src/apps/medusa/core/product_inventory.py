import asyncio
import random
from typing import Any

from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from apps.medusa.utils.api_auth import BaseMedusaAPI
from apps.medusa.utils.api_utils import MedusaAPIUtils
from common.logger import logger


async def fetch_catalog_data(api_utils: MedusaAPIUtils) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Fetch products and stock locations."""
    logger.info("Fetching catalog data from Medusa API...")

    products = await api_utils._fetch_with_pagination("/admin/products", "products", initial_limit=1000)
    stock_locations = await api_utils.fetch_stock_locations()

    logger.info(f"Successfully fetched catalog data - Products: {len(products)}, Stock Locations: {len(stock_locations)}")

    return products, stock_locations


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=10), retry=retry_if_exception_type(Exception))
async def get_product_variants(session, auth, base_url: str, product_id: str) -> list[dict[str, Any]]:
    """Get variants for a specific product."""
    if not session or not auth:
        return []

    url = f"{base_url}/admin/products/{product_id}/variants"
    headers = auth.get_auth_headers()
    params = {
        "order": "variant_rank",
        "fields": "title,sku,*options,created_at,updated_at,*inventory_items.inventory.location_levels,inventory_quantity,manage_inventory",
    }

    async with session.get(url, headers=headers, params=params) as response:
        if response.status == 200:
            result = await response.json()
            return result.get("variants", [])
        return []


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=10), retry=retry_if_exception_type(Exception))
async def update_location_level(session, auth, base_url: str, inventory_item_id: str, location_level_id: str, quantity: int | None = None) -> bool:
    """Update inventory quantity for an existing location level."""
    if not session or not auth:
        return False

    if quantity is None:
        quantity = random.randint(100, 500)

    url = f"{base_url}/admin/inventory-items/{inventory_item_id}/location-levels/{location_level_id}"
    headers = auth.get_auth_headers()
    payload = {"stocked_quantity": quantity}

    async with session.post(url, headers=headers, json=payload) as response:
        return response.status in (200, 201)


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=10), retry=retry_if_exception_type(Exception))
async def create_location_level(session, auth, base_url: str, inventory_item_id: str, location_id: str, quantity: int | None = None) -> bool:
    """Create a new location level for an inventory item."""
    if not session or not auth:
        return False

    if quantity is None:
        quantity = random.randint(100, 500)

    url = f"{base_url}/admin/inventory-items/{inventory_item_id}/location-levels"
    headers = auth.get_auth_headers()
    payload = {"location_id": location_id, "stocked_quantity": quantity}

    async with session.post(url, headers=headers, json=payload) as response:
        return response.status in (200, 201)


async def update_inventory(session, auth, base_url: str, product: dict[str, Any], stock_locations: list[dict[str, Any]]) -> bool:
    """Update inventory for a single product and its variants."""
    if not session or not auth:
        return False

    product_id = product.get("id")
    if not product_id:
        return False

    try:
        variants = await get_product_variants(session, auth, base_url, product_id)
        if not variants:
            return False

        valid_location_ids = {loc.get("id") for loc in stock_locations}
        success_count = 0

        for variant in variants:
            inventory_items = variant.get("inventory_items", [])
            if not inventory_items:
                continue

            for inventory_item in inventory_items:
                inventory_item_id = inventory_item.get("inventory_item_id") or inventory_item.get("id")
                if not inventory_item_id:
                    continue

                inventory_details = inventory_item.get("inventory", {})
                location_levels = inventory_details.get("location_levels", [])

                if location_levels:
                    updated_any = False
                    for location_level in location_levels:
                        location_id = location_level.get("location_id")
                        location_level_id = location_level.get("id")

                        if location_id in valid_location_ids and location_level_id:
                            result = await update_location_level(session, auth, base_url, inventory_item_id, location_level_id)
                            if result:
                                success_count += 1
                                updated_any = True

                    if not updated_any and stock_locations:
                        first_location = stock_locations[0]
                        location_id = first_location.get("id")
                        if location_id:
                            result = await create_location_level(session, auth, base_url, inventory_item_id, location_id)
                            if result:
                                success_count += 1
                else:
                    if stock_locations:
                        first_location = stock_locations[0]
                        location_id = first_location.get("id")
                        if location_id:
                            result = await create_location_level(session, auth, base_url, inventory_item_id, location_id)
                            if result:
                                success_count += 1

        return success_count > 0

    except Exception:
        return False


async def update_product_inventory() -> dict[str, int]:
    """Main function to update inventory for all products."""
    async with MedusaAPIUtils() as api_utils:
        products, stock_locations = await fetch_catalog_data(api_utils)

        if not products:
            logger.warning("No products found. Exiting inventory update.")
            return {"total": 0, "successful": 0, "failed": 0}

        if not stock_locations:
            logger.warning("No stock locations found. Exiting inventory update.")
            return {"total": 0, "successful": 0, "failed": 0}

        total = len(products)
        logger.info(f"Starting inventory update process - Total products: {total}")

        successful = 0
        failed = 0

        # Use BaseMedusaAPI context for session and auth
        async with BaseMedusaAPI() as medusa_api:
            for idx, product in enumerate(products, 1):
                product_title = product.get("title", "Unknown")
                product_id = product.get("id", "N/A")

                logger.info(f"[{idx}/{total}] Updating inventory for product: '{product_title}' (ID: {product_id})")

                result = await update_inventory(medusa_api.session, medusa_api.auth, medusa_api.base_url, product, stock_locations)

                if result:
                    successful += 1
                    logger.info(f"[{idx}/{total}] ✓ Successfully updated inventory for: '{product_title}'")
                else:
                    failed += 1
                    logger.error(f"[{idx}/{total}] ✗ Failed to update inventory for: '{product_title}'")

        logger.info(f"Inventory update completed - Total: {total}, Successful: {successful}, Failed: {failed}, Success Rate: {(successful / total * 100):.1f}%")

        return {"total": total, "successful": successful, "failed": failed}


async def seed_product_inventory():
    """Entry point for seeding product inventory."""
    logger.info("=" * 60)
    logger.info("Starting Product Inventory Seeding Script")
    logger.info("=" * 60)

    result = await update_product_inventory()

    logger.info("=" * 60)
    logger.info("Product Inventory Seeding Script Completed")
    logger.info("=" * 60)

    return result


if __name__ == "__main__":
    asyncio.run(seed_product_inventory())
