"""Product Categories API operations for Medusa."""

import asyncio
from typing import Any

import aiohttp

from apps.medusa.config.constants import CATEGORIES_FILEPATH
from apps.medusa.config.settings import settings
from apps.medusa.utils.api_auth import authenticate_async
from apps.medusa.utils.data_utils import load_json_file
from common.logger import logger


def load_categories_data() -> list[dict[str, Any]]:
    """Load categories data from JSON file."""
    categories_data = load_json_file(CATEGORIES_FILEPATH, default=[])
    if not isinstance(categories_data, list) or not categories_data:
        logger.warning("No categories data found")
        return []
    return categories_data


async def create_category(category_data: dict[str, Any], session: aiohttp.ClientSession, auth, base_url: str) -> bool:
    """Create a single category via Medusa API."""
    name = category_data.get("name")
    if not name:
        logger.warning("Category missing name field")
        return False

    try:
        payload = {"name": name, "is_active": category_data.get("is_active", True), "is_internal": category_data.get("is_internal", False)}

        if category_data.get("description"):
            payload["description"] = category_data["description"]

        if category_data.get("handle"):
            payload["handle"] = category_data["handle"]

        url = f"{base_url}/admin/product-categories"
        headers = auth.get_auth_headers()

        async with session.post(url, json=payload, headers=headers) as response:
            if response.status in (200, 201):
                logger.info(f"Created category: {name}")
                return True
            else:
                logger.error(f"Failed to create category: {name}")
                return False

    except Exception as e:
        logger.error(f"Error creating category '{name}': {e}")
        return False


async def create_categories(categories_data: list[dict[str, Any]], session: aiohttp.ClientSession, auth, base_url: str) -> dict[str, int]:
    """Create all categories from the categories data."""
    if not categories_data:
        logger.warning("No categories to create")
        return {"total": 0, "successful": 0, "failed": 0}

    logger.info(f"Creating {len(categories_data)} categories...")

    successful = 0
    failed = 0

    for category_data in categories_data:
        result = await create_category(category_data, session, auth, base_url)

        if result:
            successful += 1
        else:
            failed += 1

    logger.info(f"Categories created: {successful} successful, {failed} failed")

    return {"total": len(categories_data), "successful": successful, "failed": failed}


async def seed_categories():
    """Create categories from file."""
    auth = await authenticate_async()
    base_url = settings.MEDUSA_API_URL

    async with aiohttp.ClientSession() as session:
        categories_data = load_categories_data()
        return await create_categories(categories_data, session, auth, base_url)


if __name__ == "__main__":
    asyncio.run(seed_categories())
