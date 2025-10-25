import asyncio
from typing import Any

import aiohttp

from apps.medusa.config.constants import COLLECTIONS_FILEPATH
from apps.medusa.config.settings import settings
from apps.medusa.utils.api_auth import authenticate_async
from apps.medusa.utils.data_utils import load_json_file
from common.logger import logger


def load_collections_data() -> list[dict[str, Any]]:
    """Load collections data from JSON file."""
    collections_data = load_json_file(COLLECTIONS_FILEPATH, default=[])
    if not isinstance(collections_data, list) or not collections_data:
        logger.warning("No collections data found")
        return []
    return collections_data


async def create_collection(collection_data: dict[str, Any], session: aiohttp.ClientSession, auth, base_url: str) -> bool:
    """Create a single collection via Medusa API."""
    title = collection_data.get("title")
    if not title:
        logger.warning("Collection missing title field")
        return False

    try:
        payload = {"title": title}

        if collection_data.get("handle"):
            payload["handle"] = collection_data["handle"]

        url = f"{base_url}/admin/collections"
        headers = auth.get_auth_headers()

        async with session.post(url, json=payload, headers=headers) as response:
            if response.status in (200, 201):
                logger.info(f"Created collection: {title}")
                return True
            else:
                logger.error(f"Failed to create collection: {title}")
                return False

    except Exception as e:
        logger.error(f"Error creating collection '{title}': {e}")
        return False


async def create_collections(collections_data: list[dict[str, Any]], session: aiohttp.ClientSession, auth, base_url: str) -> dict[str, int]:
    """Create all collections from the collections data."""
    if not collections_data:
        logger.warning("No collections to create")
        return {"total": 0, "successful": 0, "failed": 0}

    logger.info(f"Creating {len(collections_data)} collections...")

    successful = 0
    failed = 0

    for collection_data in collections_data:
        result = await create_collection(collection_data, session, auth, base_url)

        if result:
            successful += 1
        else:
            failed += 1

    logger.info(f"Collections created: {successful} successful, {failed} failed")

    return {"total": len(collections_data), "successful": successful, "failed": failed}


async def seed_collections():
    """Create collections from file."""
    auth = await authenticate_async()
    base_url = settings.MEDUSA_API_URL

    async with aiohttp.ClientSession() as session:
        collections_data = load_collections_data()
        return await create_collections(collections_data, session, auth, base_url)


if __name__ == "__main__":
    asyncio.run(seed_collections())
