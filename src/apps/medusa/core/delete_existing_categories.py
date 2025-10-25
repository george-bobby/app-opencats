import asyncio
from typing import Any

import aiohttp
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from apps.medusa.config.settings import settings
from apps.medusa.utils.api_auth import authenticate_async
from common.logger import logger


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=10),
    retry=retry_if_exception_type((aiohttp.ClientError, asyncio.TimeoutError)),
    reraise=True,
)
async def fetch_all_categories(session: aiohttp.ClientSession, auth, base_url: str) -> list[dict[str, Any]]:
    """Fetch all categories from Medusa API."""
    try:
        logger.info("Fetching all categories...")
        url = f"{base_url}/admin/product-categories"
        headers = auth.get_auth_headers()

        all_categories = []
        offset = 0
        limit = 100

        while True:
            params = {"offset": offset, "limit": limit}

            async with session.get(url, headers=headers, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    categories = data.get("product_categories", [])

                    if not categories:
                        break

                    all_categories.extend(categories)
                    offset += limit

                    if len(categories) < limit:
                        break
                else:
                    logger.error(f"Failed to fetch categories: {response.status}")
                    break

        logger.info(f"Fetched {len(all_categories)} categories")
        return all_categories

    except Exception as e:
        logger.error(f"Error fetching categories: {e}")
        raise


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=10),
    retry=retry_if_exception_type((aiohttp.ClientError, asyncio.TimeoutError)),
    reraise=True,
)
async def delete_category(category_id: str, category_name: str, session: aiohttp.ClientSession, auth, base_url: str) -> bool:
    """Delete a single category via Medusa API."""
    try:
        url = f"{base_url}/admin/product-categories/{category_id}"
        headers = auth.get_auth_headers()

        async with session.delete(url, headers=headers) as response:
            if response.status == 200:
                logger.info(f"Deleted category: {category_name}")
                return True
            else:
                logger.error(f"Failed to delete category: {category_name}")
                return False

    except Exception as e:
        logger.error(f"Error deleting category '{category_name}': {e}")
        return False


async def delete_all_categories(session: aiohttp.ClientSession, auth, base_url: str) -> dict[str, int]:
    """Fetch and delete all categories."""
    logger.info("Starting categories deletion...")

    categories = await fetch_all_categories(session, auth, base_url)

    if not categories:
        logger.warning("No categories found to delete")
        return {"total": 0, "successful": 0, "failed": 0}

    logger.info(f"Deleting {len(categories)} categories...")

    successful = 0
    failed = 0

    for category in categories:
        category_id = category.get("id")
        category_name = category.get("name", "Unknown")

        if not category_id:
            logger.warning(f"Skipping category with missing ID: {category_name}")
            failed += 1
            continue

        result = await delete_category(category_id, category_name, session, auth, base_url)
        if result:
            successful += 1
        else:
            failed += 1

    logger.info(f"Categories deleted: {successful} successful, {failed} failed")

    return {"total": len(categories), "successful": successful, "failed": failed}


async def delete_existing_categories():
    """Delete all existing categories from Medusa."""
    auth = await authenticate_async()
    base_url = settings.MEDUSA_API_URL

    async with aiohttp.ClientSession() as session:
        return await delete_all_categories(session, auth, base_url)


if __name__ == "__main__":
    asyncio.run(delete_existing_categories())
