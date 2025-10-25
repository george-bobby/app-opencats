import json
import time
from datetime import datetime

from apps.frappehrms.config.settings import settings
from apps.frappehrms.utils import frappe_client
from common.logger import logger


async def setup_site():
    client = frappe_client.create_client()

    companies = client.get_list("Company")
    if not companies:
        current_year = datetime.now().year
        try:
            client.session.post(
                client.url + "/api/method/frappe.desk.page.setup_wizard.setup_wizard.setup_complete",
                data={
                    "args": json.dumps(
                        {
                            "currency": "USD",
                            "country": "United States",
                            "timezone": "America/Adak",
                            "language": "English",
                            "company_name": "Acme Inc.",
                            "company_abbr": "AI",
                            "chart_of_accounts": "Standard",
                            "fy_start_date": f"{current_year}-01-01",
                            "fy_end_date": f"{current_year}-12-31",
                            "setup_demo": 0,
                        }
                    ),
                },
            )
            logger.info("Setting up HRMS site...")
            time.sleep(25)
        except Exception as e:
            logger.warning(f"Site already setup? {e!s}")

    client.login(settings.ADMIN_USERNAME, settings.ADMIN_PASSWORD)

    client.update(
        {
            "name": "System Settings",
            "doctype": "System Settings",
            "default_app": "hrms",
        }
    )

    try:
        client.insert(
            {
                "name": "Serial No Warranty Expiry",
                "report_name": "Serial No Warranty Expiry",
                "ref_doctype": "Report",
                "is_standard": "No",
                "module": "Core",
                "report_type": "Report Builder",
                "doctype": "Report",
            }
        )
    except Exception as e:
        logger.error(f"Error inserting report: {e!s}")

    pages_to_hide = [
        "Home",
        "Accounting",
        "Buying",
        "Selling",
        "Stock",
        "Assets",
        "Manufacturing",
        "Quality",
        "Support",
        "CRM",
    ]
    for page in pages_to_hide:
        try:
            client.session.post(
                client.url + "/api/method/frappe.desk.doctype.workspace.workspace.hide_page",
                data={
                    "page_name": page,
                },
            )
        except Exception as e:
            logger.error(f"Error hiding page {page}: {e!s}")

    try:
        client.session.post(
            client.url + "/api/method/frappe.desk.doctype.workspace.workspace.add_item",
            data={
                "is_private": None,
                "folder": "Home",
                "file_url": client.url + "/assets/hrms/images/frappe-hr-logo.svg",
                "doctype": "Navbar Settings",
                "docname": "Navbar Settings",
                "fieldname": "app_logo",
            },
        )
        client.update(
            {
                "name": "Navbar Settings",
                "app_logo": client.url + "/assets/hrms/images/frappe-hr-logo.svg",
                "doctype": "Navbar Settings",
            }
        )
    except Exception:
        pass

    logger.info("HRMS site setup complete. You can now login into the app.")
