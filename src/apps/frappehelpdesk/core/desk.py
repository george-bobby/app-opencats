import contextlib
import json
from datetime import datetime

from apps.frappehelpdesk.config.settings import settings
from apps.frappehelpdesk.utils.frappe_client import FrappeClient
from common.logger import logger


async def setup_site():
    logger.start("Setting up Helpdesk site...")

    async with FrappeClient() as client:
        # Check if site is already set up by trying to get companies
        companies = []
        with contextlib.suppress(Exception):
            companies = await client.get_list("Company")

        if not companies:
            current_year = datetime.now().year
            try:
                async with client.session.post(
                    f"{client.url}/api/method/frappe.desk.page.setup_wizard.setup_wizard.setup_complete",
                    data={
                        "args": json.dumps(
                            {
                                "language": "english",
                                "country": "United States",
                                "timezone": "America/New_York",
                                "currency": "USD",
                                "company_name": settings.COMPANY_NAME,
                                "company_abbr": settings.COMPANY_ABBR,
                                "domains": ["Support"],
                                "company_tagline": f"Your {settings.COMPANY_NAME} Support",
                                "bank_account": f"{settings.COMPANY_NAME} - USD",
                                "chart_of_accounts": "Standard",
                                "fy_start_date": f"{current_year}-01-01",
                                "fy_end_date": f"{current_year}-12-31",
                            }
                        )
                    },
                ) as response:
                    if response.status == 200:
                        logger.info("Setup wizard completed successfully")
                    else:
                        logger.warning(f"Setup wizard failed with status {response.status}")
            except Exception as e:
                logger.warning(f"Error running setup wizard: {e}")

        try:
            await client.update(
                {
                    "name": "System Settings",
                    "doctype": "System Settings",
                    "default_app": "helpdesk",
                }
            )
        except Exception as e:
            logger.warning(f"Error updating system settings: {e}")

        try:
            await client.delete("HD Ticket", "1")
            await client.delete("Contact", "John Doe")
        except Exception as e:
            logger.warning(f"Error deleting default contact: {e}")

        # Create default email account for replies
        try:
            await client.insert(
                {
                    "name": "Replies",
                    "email_id": f"replies@{settings.COMPANY_DOMAIN}",
                    "email_account_name": "Replies",
                    "enable_incoming": 1,
                    "enable_outgoing": 1,
                    "awaiting_password": 1,
                    "ascii_encode_password": 0,
                    "default_incoming": 1,
                    "default_outgoing": 1,
                    "doctype": "Email Account",
                    "imap_folder": [
                        {
                            "docstatus": 0,
                            "doctype": "IMAP Folder",
                            "parent": "Replies",
                            "parentfield": "imap_folder",
                            "parenttype": "Email Account",
                            "folder_name": "Replies",
                        }
                    ],
                }
            )
            logger.info("Created default email account: Replies")
        except Exception as e:
            logger.warning(f"Failed to create email account: {e}")

        # Update onboarding status to complete all steps
        try:
            onboarding_steps = [
                {"name": "setup_email_account", "completed": True},
                {"name": "invite_agents", "completed": True},
                {"name": "setup_sla", "completed": True},
                {"name": "create_first_ticket", "completed": True},
                {"name": "assign_to_agent", "completed": True},
                {"name": "reply_on_ticket", "completed": True},
                {"name": "comment_on_ticket", "completed": True},
                {"name": "first_article", "completed": True},
                {"name": "add_invite_contact", "completed": True},
                {"name": "explore_customer_portal", "completed": True},
            ]

            await client.post_api("frappe.onboarding.update_user_onboarding_status", {"steps": json.dumps(onboarding_steps), "appName": "helpdesk"})
            logger.info("Updated onboarding status")
        except Exception as e:
            logger.warning(f"Failed to update onboarding status: {e}")

    logger.succeed("Helpdesk site setup complete")
