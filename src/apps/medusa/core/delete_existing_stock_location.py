"""Stock locations deletion API operations for Medusa."""

import asyncio

import aiohttp
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from apps.medusa.utils.api_utils import MedusaAPIUtils
from common.logger import logger


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=10),
    retry=retry_if_exception_type((aiohttp.ClientError, asyncio.TimeoutError)),
    reraise=True,
)
async def delete_stock_location(location_id: str, location_name: str, session: aiohttp.ClientSession, auth, base_url: str) -> bool:
    """Delete a single stock location via Medusa API."""
    try:
        url = f"{base_url}/admin/stock-locations/{location_id}"
        headers = auth.get_auth_headers()

        async with session.delete(url, headers=headers) as response:
            if response.status == 200:
                logger.info(f"Deleted stock location: {location_name}")
                return True
            else:
                logger.error(f"Failed to delete stock location: {location_name}")
                return False

    except Exception as e:
        logger.error(f"Error deleting stock location '{location_name}': {e}")
        return False


async def delete_all_stock_locations() -> dict[str, int]:
    """Fetch and delete all stock locations using MedusaAPIUtils."""
    logger.info("Starting stock locations deletion...")

    async with MedusaAPIUtils() as api_utils:
        # Fetch all stock locations using the utility method
        stock_locations = await api_utils.fetch_stock_locations()

        if not stock_locations:
            logger.warning("No stock locations found to delete")
            return {"total": 0, "successful": 0, "failed": 0}

        logger.info(f"Deleting {len(stock_locations)} stock locations...")

        successful = 0
        failed = 0

        # Create a separate session for deletion operations
        async with aiohttp.ClientSession() as session:
            auth = api_utils.auth
            base_url = api_utils.base_url

            for location in stock_locations:
                location_id = location.get("id")
                location_name = location.get("name", "Unknown")

                if not location_id:
                    logger.warning(f"Skipping stock location with missing ID: {location_name}")
                    failed += 1
                    continue

                result = await delete_stock_location(location_id, location_name, session, auth, base_url)
                if result:
                    successful += 1
                else:
                    failed += 1

        logger.info(f"Stock locations deleted: {successful} successful, {failed} failed")

        return {"total": len(stock_locations), "successful": successful, "failed": failed}


async def delete_existing_stock_location():
    """Main entry point for deleting all stock locations."""
    return await delete_all_stock_locations()


if __name__ == "__main__":
    asyncio.run(delete_existing_stock_location())
