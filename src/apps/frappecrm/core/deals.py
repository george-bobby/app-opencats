from collections import OrderedDict

from faker import Faker

from apps.frappecrm.config.settings import settings
from apps.frappecrm.utils import frappe_client
from apps.frappecrm.utils.constants import LOST_REASONS, OTHER_LOST_REASONS
from common.logger import logger


fake = Faker()


async def randomize_deal_status(number_of_deals: int):
    client = frappe_client.create_client()
    logger.start(f"Randomizing {number_of_deals} deal statuses")

    deals = client.get_list(
        "CRM Deal",
        fields=["name"],
        limit_page_length=settings.LIST_LIMIT,
    )

    number_of_deals = len(deals) if number_of_deals > len(deals) else number_of_deals
    deals = fake.random_elements(elements=deals, length=number_of_deals, unique=True)

    for deal in deals:
        status = fake.random_element(
            OrderedDict(
                [
                    ("Qualification", 0.1),
                    ("Demo/Making", 0.15),
                    ("Proposal/Quotation", 0.15),
                    ("Negotiation", 0.15),
                    ("Ready to Close", 0.1),
                    ("Won", 0.35),
                    ("Lost", 0.1),
                ]
            )
        )

        update_data = {
            "doctype": "CRM Deal",
            "name": deal["name"],
            "status": status,
        }

        # If status is Lost, add a random lost reason
        if status == "Lost":
            lost_reason = fake.random_element(LOST_REASONS)
            if lost_reason == "Other":
                update_data["lost_notes"] = fake.random_element(OTHER_LOST_REASONS)
            update_data["lost_reason"] = lost_reason

        try:
            client.update(update_data)
        except Exception as e:
            logger.error(f"Error updating deal {deal['name']} status to {status}: {e}")
            continue

    logger.succeed(f"Successfully randomized {len(deals)} deal statuses")
