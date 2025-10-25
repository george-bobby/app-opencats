import asyncio
import random
from typing import Any

from apps.medusa.config.constants import CUSTOMER_GROUPS_FILEPATH
from apps.medusa.config.settings import settings
from apps.medusa.utils.data_utils import load_json_file
from common.logger import logger
from common.save_to_json import save_to_json


def load_existing_customers() -> list[dict[str, Any]]:
    """Load existing customers from file."""
    customers_filepath = settings.DATA_PATH / "customers.json"
    return load_json_file(customers_filepath, [])


def get_customer_groups_templates() -> list[dict[str, Any]]:
    """Get predefined customer group templates."""
    return [
        {"name": "Diamond Group", "description": "Premium tier customers", "customer_count_range": (15, 20)},
        {"name": "Platinum Group", "description": "High-value customers", "customer_count_range": (12, 18)},
        {"name": "Gold Group", "description": "Valued customers", "customer_count_range": (10, 15)},
        {"name": "Silver Group", "description": "Standard customers", "customer_count_range": (12, 20)},
    ]


def get_random_customer_emails(customers_data: list[dict[str, Any]], count: int) -> list[str]:
    """Get random customer emails from customers data."""
    if not customers_data:
        return []

    customer_emails: list[str] = []
    for customer in customers_data:
        email = customer.get("email")
        if email and isinstance(email, str):
            customer_emails.append(email)

    if not customer_emails:
        return []

    actual_count = min(count, len(customer_emails))
    return random.sample(customer_emails, actual_count)


def generate_customer_groups(customers_data: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Generate customer groups with assigned customers."""
    if not customers_data:
        logger.warning("No customers available to assign to groups")
        return []

    customer_groups_templates = get_customer_groups_templates()
    generated_groups: list[dict[str, Any]] = []

    for group_template in customer_groups_templates:
        min_count, max_count = group_template["customer_count_range"]
        customer_count = random.randint(min_count, max_count)
        random_customer_emails = get_random_customer_emails(customers_data, customer_count)

        group = {
            "name": group_template["name"],
            "description": group_template["description"],
            "customer_emails": random_customer_emails,
            "customer_count": len(random_customer_emails),
        }

        generated_groups.append(group)

    logger.info(f"Generated {len(generated_groups)} customer groups")
    return generated_groups


async def customer_groups() -> dict[str, Any]:
    """Main function to generate customer groups."""
    logger.info("Starting customer groups generation")

    settings.DATA_PATH.mkdir(parents=True, exist_ok=True)

    customers_data = load_existing_customers()
    generated_groups: list[dict[str, Any]] = []

    try:
        generated_groups = generate_customer_groups(customers_data)

        if generated_groups:
            save_to_json(generated_groups, CUSTOMER_GROUPS_FILEPATH)
            logger.info(f"Saved {len(generated_groups)} customer groups to {CUSTOMER_GROUPS_FILEPATH}")

        return {
            "total_processed": len(generated_groups),
            "groups": generated_groups,
        }

    except Exception as error:
        logger.error(f"Fatal error during generation: {error}")
        if generated_groups:
            save_to_json(generated_groups, CUSTOMER_GROUPS_FILEPATH)
        raise


if __name__ == "__main__":
    asyncio.run(customer_groups())
