import asyncio
from typing import Any

import aiohttp

from apps.medusa.config.constants import CUSTOMER_GROUPS_FILEPATH
from apps.medusa.config.settings import settings
from apps.medusa.utils.api_auth import authenticate_async
from apps.medusa.utils.data_utils import load_json_file
from common.logger import logger


def load_customer_groups_data() -> list[dict[str, Any]]:
    customer_groups_data = load_json_file(CUSTOMER_GROUPS_FILEPATH, default=[])
    if not isinstance(customer_groups_data, list) or not customer_groups_data:
        logger.warning("No customer groups data found")
        return []
    return customer_groups_data


async def fetch_all_customers(session: aiohttp.ClientSession, auth, base_url: str) -> dict[str, str]:
    """Fetch all customers and create email to ID mapping."""
    try:
        url = f"{base_url}/admin/customers"
        headers = auth.get_auth_headers()

        all_customers = []
        offset = 0
        limit = 100

        while True:
            params = {"offset": offset, "limit": limit}
            async with session.get(url, headers=headers, params=params) as response:
                if response.status == 200:
                    result = await response.json()
                    customers = result.get("customers", [])

                    if not customers:
                        break

                    all_customers.extend(customers)

                    if len(customers) < limit:
                        break

                    offset += limit
                else:
                    logger.error("Failed to fetch customers")
                    break

        email_to_id = {}
        for customer in all_customers:
            email = customer.get("email")
            customer_id = customer.get("id")
            if email and customer_id:
                email_to_id[email] = customer_id

        return email_to_id

    except Exception as e:
        logger.error(f"Error fetching customers: {e}")
        return {}


def get_customer_ids_from_emails(emails: list[str], email_to_id_map: dict[str, str]) -> list[str]:
    """Convert customer emails to customer IDs using the mapping."""
    customer_ids = []
    for email in emails:
        customer_id = email_to_id_map.get(email)
        if customer_id:
            customer_ids.append(customer_id)
    return customer_ids


async def add_customers_to_group(group_id: str, customer_ids: list[str], session: aiohttp.ClientSession, auth, base_url: str) -> bool:
    """Add customers to a customer group."""
    if not customer_ids:
        return False

    try:
        payload = {"add": customer_ids}
        url = f"{base_url}/admin/customer-groups/{group_id}/customers"
        headers = auth.get_auth_headers()

        async with session.post(url, json=payload, headers=headers) as response:
            return response.status == 200

    except Exception as e:
        logger.error(f"Error adding customers to group: {e}")
        return False


async def create_customer_group(group_data: dict[str, Any], email_to_id_map: dict[str, str], session: aiohttp.ClientSession, auth, base_url: str) -> bool:
    """Create a single customer group via Medusa API."""
    group_name = group_data.get("name")
    if not group_name:
        logger.warning("Customer group missing name field")
        return False

    try:
        payload = {"name": group_name, "metadata": {"description": group_data.get("description", ""), "generated_by": "medusa_generator"}}

        url = f"{base_url}/admin/customer-groups"
        headers = auth.get_auth_headers()

        async with session.post(url, json=payload, headers=headers) as response:
            if response.status == 200:
                result = await response.json()
                group_info = result.get("customer_group", {})
                group_id = group_info.get("id")

                if group_id:
                    customer_emails = group_data.get("customer_emails", [])
                    if customer_emails:
                        customer_ids = get_customer_ids_from_emails(customer_emails, email_to_id_map)
                        if customer_ids:
                            await add_customers_to_group(group_id, customer_ids, session, auth, base_url)

                logger.info(f"Created customer group: {group_name}")
                return True
            else:
                logger.error(f"Failed to create customer group: {group_name}")
                return False

    except Exception as e:
        logger.error(f"Error creating customer group '{group_name}': {e}")
        return False


async def create_customer_groups(customer_groups_data: list[dict[str, Any]], email_to_id_map: dict[str, str], session: aiohttp.ClientSession, auth, base_url: str) -> dict[str, int]:
    """Create all customer groups from the customer groups data."""
    if not customer_groups_data:
        logger.warning("No customer groups to create")
        return {"total": 0, "successful": 0, "failed": 0}

    if not email_to_id_map:
        logger.warning("No customers available")
        return {"total": 0, "successful": 0, "failed": 0}

    logger.info(f"Creating {len(customer_groups_data)} customer groups...")

    successful = 0
    failed = 0

    for group_data in customer_groups_data:
        result = await create_customer_group(group_data, email_to_id_map, session, auth, base_url)

        if result:
            successful += 1
        else:
            failed += 1

    logger.info(f"Customer groups created: {successful} successful, {failed} failed")

    return {"total": len(customer_groups_data), "successful": successful, "failed": failed}


async def seed_customer_groups():
    auth = await authenticate_async()
    base_url = settings.MEDUSA_API_URL

    async with aiohttp.ClientSession() as session:
        customer_groups_data = load_customer_groups_data()
        email_to_id_map = await fetch_all_customers(session, auth, base_url)
        return await create_customer_groups(customer_groups_data, email_to_id_map, session, auth, base_url)


if __name__ == "__main__":
    asyncio.run(seed_customer_groups())
