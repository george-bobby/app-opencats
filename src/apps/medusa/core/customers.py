import asyncio
from typing import Any

import aiohttp
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from apps.medusa.config.constants import CUSTOMERS_FILEPATH
from apps.medusa.config.settings import settings
from apps.medusa.utils.api_auth import authenticate_async
from apps.medusa.utils.data_utils import load_json_file
from common.logger import logger


def prepare_customer_payload(customer_data: dict[str, Any]) -> dict[str, Any] | None:
    """Prepare customer payload for Medusa API."""
    excluded_fields = {"id", "created_at", "updated_at"}
    payload = {key: value for key, value in customer_data.items() if key not in excluded_fields}

    if not payload.get("email"):
        logger.warning("Skipping customer with missing email")
        return None

    return payload


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=10),
    retry=retry_if_exception_type((aiohttp.ClientError, asyncio.TimeoutError)),
    reraise=True,
)
async def create_customer(customer_data: dict[str, Any], session: aiohttp.ClientSession, auth, base_url: str) -> bool:
    """Create a single customer via Medusa API."""
    payload = prepare_customer_payload(customer_data)
    if not payload:
        return False

    email = payload.get("email", "unknown")

    try:
        url = f"{base_url}/admin/customers"
        headers = auth.get_auth_headers()

        async with session.post(url, json=payload, headers=headers) as response:
            if response.status in (200, 201):
                logger.info(f"Created customer: {email}")
                return True
            else:
                logger.error(f"Failed to create customer: {email}")
                return False

    except Exception as e:
        logger.error(f"Error creating customer '{email}': {e}")
        return False


async def process_customers(customers_data: list[dict[str, Any]], session: aiohttp.ClientSession, auth, base_url: str) -> dict[str, int]:
    """Create all customers from the customers data."""
    if not isinstance(customers_data, list) or not customers_data:
        logger.warning("No customers data found")
        return {"total": 0, "successful": 0, "failed": 0}

    logger.info(f"Seeding {len(customers_data)} customers...")

    successful = 0
    failed = 0

    for customer_data in customers_data:
        result = await create_customer(customer_data, session, auth, base_url)
        if result:
            successful += 1
        else:
            failed += 1

    logger.info(f"Customers seeded: {successful} successful, {failed} failed")

    return {"total": len(customers_data), "successful": successful, "failed": failed}


async def seed_customers():
    """Create customers from file."""
    auth = await authenticate_async()
    base_url = settings.MEDUSA_API_URL

    async with aiohttp.ClientSession() as session:
        customers_data = load_json_file(CUSTOMERS_FILEPATH, default=[])
        return await process_customers(customers_data, session, auth, base_url)


if __name__ == "__main__":
    asyncio.run(seed_customers())
