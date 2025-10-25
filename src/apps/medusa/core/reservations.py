"""Product inventory reservation management for Medusa."""

import asyncio
import random
from typing import Any

from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from apps.medusa.utils.api_auth import BaseMedusaAPI
from apps.medusa.utils.api_utils import MedusaAPIUtils
from common.logger import logger


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=10), retry=retry_if_exception_type(Exception))
async def get_all_products() -> list[dict[str, Any]]:
    """Fetch all products from the catalog."""
    async with MedusaAPIUtils() as api_utils:
        products = await api_utils._fetch_with_pagination("/admin/products", "products", initial_limit=1000)
        return products


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
async def create_reservation(session, auth, base_url: str, inventory_item_id: str, location_id: str, quantity: int, description: str = "Automated inventory reservation") -> bool:
    """Create a reservation for an inventory item at a specific location."""
    if not session or not auth:
        return False

    url = f"{base_url}/admin/reservations"
    headers = auth.get_auth_headers()
    payload = {"inventory_item_id": inventory_item_id, "location_id": location_id, "quantity": quantity, "description": description}

    async with session.post(url, headers=headers, json=payload) as response:
        return response.status in (200, 201)


async def process_product_reservations(
    session, auth, base_url: str, product: dict[str, Any], min_reservations: int = 15, max_reservations: int = 40, quantity_percentage: float = 0.10
) -> dict[str, int]:
    """Process reservations for a single product and its variants."""
    product_id = product.get("id")

    if not product_id:
        return {"variants_processed": 0, "successful": 0, "failed": 0}

    try:
        variants = await get_product_variants(session, auth, base_url, product_id)
    except Exception:
        return {"variants_processed": 0, "successful": 0, "failed": 0}

    if not variants:
        return {"variants_processed": 0, "successful": 0, "failed": 0}

    successful = 0
    failed = 0
    variants_processed = 0
    reservations_needed = random.randint(min_reservations, max_reservations)

    for variant in variants:
        if successful >= reservations_needed:
            break

        variants_processed += 1
        variant_title = variant.get("title", "Unknown")
        inventory_items = variant.get("inventory_items", [])

        if not inventory_items:
            continue

        for inventory_item in inventory_items:
            if successful >= reservations_needed:
                break

            inventory_item_id = inventory_item.get("inventory_item_id") or inventory_item.get("id")

            if not inventory_item_id:
                continue

            inventory_details = inventory_item.get("inventory", {})
            location_levels = inventory_details.get("location_levels", [])

            if not location_levels:
                continue

            for location_level in location_levels:
                if successful >= reservations_needed:
                    break

                location_id = location_level.get("location_id")
                stocked_quantity = location_level.get("stocked_quantity", 0)

                if not location_id:
                    continue

                reservation_qty = max(1, int(stocked_quantity * quantity_percentage))

                if stocked_quantity < reservation_qty:
                    continue

                description = f"Reserved for variant {variant_title}"

                try:
                    result = await create_reservation(session, auth, base_url, inventory_item_id, location_id, reservation_qty, description)
                    if result:
                        successful += 1
                    else:
                        failed += 1
                except Exception:
                    failed += 1

    return {"variants_processed": variants_processed, "successful": successful, "failed": failed}


async def create_reservations_for_all_products(min_reservations: int = 15, max_reservations: int = 40, quantity_percentage: float = 0.10) -> dict[str, int]:
    """Create reservations for all products in the catalog."""
    try:
        products = await get_all_products()
    except Exception:
        logger.info("No products found")
        return {"total_products": 0, "total_variants": 0, "successful": 0, "failed": 0}

    if not products:
        logger.info("No products found")
        return {"total_products": 0, "total_variants": 0, "successful": 0, "failed": 0}

    logger.info(f"Creating reservations for {len(products)} products")

    total_variants = 0
    total_successful = 0
    total_failed = 0

    async with BaseMedusaAPI() as medusa_api:
        for product in products:
            result = await process_product_reservations(medusa_api.session, medusa_api.auth, medusa_api.base_url, product, min_reservations, max_reservations, quantity_percentage)
            total_variants += result["variants_processed"]
            total_successful += result["successful"]
            total_failed += result["failed"]

    logger.info(f"Completed: {total_successful} successful, {total_failed} failed")

    return {"total_products": len(products), "total_variants": total_variants, "successful": total_successful, "failed": total_failed}


async def seed_reservations():
    """Entry point for seeding product reservations."""
    return await create_reservations_for_all_products()


if __name__ == "__main__":
    asyncio.run(seed_reservations())
