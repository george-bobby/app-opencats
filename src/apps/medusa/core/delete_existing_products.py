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
async def delete_product(product_id: str, product_title: str, session: aiohttp.ClientSession, auth, base_url: str) -> bool:
    """Delete a single product via Medusa API."""
    try:
        url = f"{base_url}/admin/products/{product_id}"
        headers = auth.get_auth_headers()

        async with session.delete(url, headers=headers) as response:
            if response.status == 200:
                logger.info(f"Deleted product: {product_title}")
                return True
            else:
                logger.error(f"Failed to delete product: {product_title}")
                return False

    except Exception as e:
        logger.error(f"Error deleting product '{product_title}': {e}")
        return False


async def delete_all_products() -> dict[str, int]:
    """Fetch and delete all products using MedusaAPIUtils."""
    logger.info("Starting products deletion...")

    # Use MedusaAPIUtils to fetch all products
    async with MedusaAPIUtils() as api_utils:
        # Fetch all products with pagination
        all_products = []
        offset = 0
        limit = 100

        while True:
            products = await api_utils.fetch_products(limit=limit, offset=offset)

            if not products:
                break

            all_products.extend(products)
            offset += limit

            if len(products) < limit:
                break

        if not all_products:
            logger.warning("No products found to delete")
            return {"total": 0, "successful": 0, "failed": 0}

        logger.info(f"Deleting {len(all_products)} products...")

        successful = 0
        failed = 0

        # Create a separate session for deletion operations
        async with aiohttp.ClientSession() as session:
            auth = api_utils.auth
            base_url = api_utils.base_url

            for product in all_products:
                product_id = product.get("id")
                product_title = product.get("title", "Unknown")

                if not product_id:
                    logger.warning(f"Skipping product with missing ID: {product_title}")
                    failed += 1
                    continue

                result = await delete_product(product_id, product_title, session, auth, base_url)
                if result:
                    successful += 1
                else:
                    failed += 1

        logger.info(f"Products deleted: {successful} successful, {failed} failed")

        return {"total": len(all_products), "successful": successful, "failed": failed}


async def delete_existing_products():
    """Delete all existing products from Medusa."""
    return await delete_all_products()


if __name__ == "__main__":
    asyncio.run(delete_existing_products())
