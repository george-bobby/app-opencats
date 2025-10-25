from faker import Faker

from apps.frappehelpdesk.config.settings import settings
from apps.frappehelpdesk.utils import frappe_client
from common.logger import logger


fake = Faker()


async def insert_agents():
    client = frappe_client.create_client()
    users = client.get_list(
        "User",
        fields=["name", "email", "full_name"],
        filters=[["name", "not in", ["Administrator", "Guest"]]],
        limit_page_length=settings.LIST_LIMIT,
    )

    for user in users:
        agent_doc = {
            "doctype": "HD Agent",
            "is_active": 1,
            "agent_name": user["full_name"],
            "user": user["email"],
        }

        try:
            client.insert(agent_doc)
            logger.info(f"Inserted agent: {user['full_name']}")
        except Exception as e:
            logger.warning(f"Error inserting agent: {e}")
