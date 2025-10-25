import asyncio
from typing import Any

import aiohttp
from tenacity import retry, stop_after_attempt, wait_exponential

from apps.medusa.config.constants import RETURN_REASONS_DATA
from apps.medusa.utils.api_utils import MedusaAPIUtils
from common.logger import logger


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=10))
async def create_return_reason(reason_data: dict[str, Any], session: aiohttp.ClientSession, auth, base_url: str) -> bool:
    """Create a single return reason in Medusa."""
    value = reason_data.get("value")
    label = reason_data.get("label")

    if not value or not label:
        return False

    try:
        url = f"{base_url}/admin/return-reasons"
        headers = auth.get_auth_headers()

        payload = {"value": value, "label": label}

        if reason_data.get("description"):
            payload["description"] = reason_data["description"]

        async with session.post(url, json=payload, headers=headers) as response:
            return response.status in (200, 201)

    except Exception:
        raise


async def seed_return_reasons_internal(session: aiohttp.ClientSession, auth, base_url: str) -> dict[str, int]:
    """Internal function to seed return reasons."""
    logger.info(f"Seeding {len(RETURN_REASONS_DATA)} return reasons")

    successful = 0
    failed = 0

    for reason_data in RETURN_REASONS_DATA:
        try:
            result = await create_return_reason(reason_data, session, auth, base_url)

            if result:
                successful += 1
            else:
                failed += 1
        except Exception:
            failed += 1

    logger.info(f"Return reasons seeded: {successful} successful, {failed} failed")

    return {"total": len(RETURN_REASONS_DATA), "successful": successful, "failed": failed}


async def seed_return_reasons() -> dict[str, int]:
    """Seed return reasons into Medusa."""
    async with MedusaAPIUtils() as api_utils, aiohttp.ClientSession() as session:
        return await seed_return_reasons_internal(session, api_utils.auth, api_utils.base_url)


if __name__ == "__main__":
    asyncio.run(seed_return_reasons())
