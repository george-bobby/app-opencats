import json
import time
from datetime import datetime

from apps.frappecrm.config.settings import settings
from apps.frappecrm.utils import frappe_client
from common.logger import logger


async def setup_site():
    logger.start("Setting up site...")

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
            time.sleep(5)
        except Exception as e:
            logger.warning(f"Site already setup? {e!s}")

    client.login(settings.ADMIN_USERNAME, settings.ADMIN_PASSWORD)

    client.update(
        {
            "name": "System Settings",
            "doctype": "System Settings",
            "default_app": "crm",
        }
    )

    try:
        client.insert(
            {
                "name": "CRM App Users",
                "role_profile": "CRM App Users",
                "doctype": "Role Profile",
                "roles": [
                    {
                        "role": "Accounts Manager",
                        "parent": "Admin",
                        "parentfield": "roles",
                        "parenttype": "Role Profile",
                        "doctype": "Has Role",
                    },
                    {
                        "role": "Accounts User",
                        "parent": "Admin",
                        "parentfield": "roles",
                        "parenttype": "Role Profile",
                        "doctype": "Has Role",
                    },
                    {
                        "role": "Blogger",
                        "parent": "Admin",
                        "parentfield": "roles",
                        "parenttype": "Role Profile",
                        "doctype": "Has Role",
                    },
                    {
                        "role": "Dashboard Manager",
                        "parent": "Admin",
                        "parentfield": "roles",
                        "parenttype": "Role Profile",
                        "doctype": "Has Role",
                    },
                    {
                        "role": "Inbox User",
                        "parent": "Admin",
                        "parentfield": "roles",
                        "parenttype": "Role Profile",
                        "doctype": "Has Role",
                    },
                    {
                        "role": "Knowledge Base Contributor",
                        "parent": "Admin",
                        "parentfield": "roles",
                        "parenttype": "Role Profile",
                        "doctype": "Has Role",
                    },
                    {
                        "role": "Knowledge Base Editor",
                        "parent": "Admin",
                        "parentfield": "roles",
                        "parenttype": "Role Profile",
                        "doctype": "Has Role",
                    },
                    {
                        "role": "Maintenance Manager",
                        "parent": "Admin",
                        "parentfield": "roles",
                        "parenttype": "Role Profile",
                        "doctype": "Has Role",
                    },
                    {
                        "role": "Maintenance User",
                        "parent": "Admin",
                        "parentfield": "roles",
                        "parenttype": "Role Profile",
                        "doctype": "Has Role",
                    },
                    {
                        "role": "Newsletter Manager",
                        "parent": "Admin",
                        "parentfield": "roles",
                        "parenttype": "Role Profile",
                        "doctype": "Has Role",
                    },
                    {
                        "role": "Prepared Report User",
                        "parent": "Admin",
                        "parentfield": "roles",
                        "parenttype": "Role Profile",
                        "doctype": "Has Role",
                    },
                    {
                        "role": "Purchase Manager",
                        "parent": "Admin",
                        "parentfield": "roles",
                        "parenttype": "Role Profile",
                        "doctype": "Has Role",
                    },
                    {
                        "role": "Purchase Master Manager",
                        "parent": "Admin",
                        "parentfield": "roles",
                        "parenttype": "Role Profile",
                        "doctype": "Has Role",
                    },
                    {
                        "role": "Purchase User",
                        "parent": "Admin",
                        "parentfield": "roles",
                        "parenttype": "Role Profile",
                        "doctype": "Has Role",
                    },
                    {
                        "role": "Report Manager",
                        "parent": "Admin",
                        "parentfield": "roles",
                        "parenttype": "Role Profile",
                        "doctype": "Has Role",
                    },
                    {
                        "role": "Sales Manager",
                        "parent": "Admin",
                        "parentfield": "roles",
                        "parenttype": "Role Profile",
                        "doctype": "Has Role",
                    },
                    {
                        "role": "Sales Master Manager",
                        "parent": "Admin",
                        "parentfield": "roles",
                        "parenttype": "Role Profile",
                        "doctype": "Has Role",
                    },
                    {
                        "role": "Sales User",
                        "parent": "Admin",
                        "parentfield": "roles",
                        "parenttype": "Role Profile",
                        "doctype": "Has Role",
                    },
                    {
                        "role": "Script Manager",
                        "parent": "Admin",
                        "parentfield": "roles",
                        "parenttype": "Role Profile",
                        "doctype": "Has Role",
                    },
                    {
                        "role": "System Manager",
                        "parent": "Admin",
                        "parentfield": "roles",
                        "parenttype": "Role Profile",
                        "doctype": "Has Role",
                    },
                    {
                        "role": "Translator",
                        "parent": "Admin",
                        "parentfield": "roles",
                        "parenttype": "Role Profile",
                        "doctype": "Has Role",
                    },
                    {
                        "role": "Website Manager",
                        "parent": "Admin",
                        "parentfield": "roles",
                        "parenttype": "Role Profile",
                        "doctype": "Has Role",
                    },
                    {
                        "role": "Workspace Manager",
                        "parent": "Admin",
                        "parentfield": "roles",
                        "parenttype": "Role Profile",
                        "doctype": "Has Role",
                    },
                ],
            }
        )
    except Exception:
        logger.warning("CRM App Users Role Profile already exists")

    try:
        c = frappe_client.create_client()
        c.session.post(
            url=f"{settings.API_URL}/api/method/frappe.desk.form.save.savedocs",
            data={
                "action": "Save",
                "doc": json.dumps(
                    {
                        "docstatus": 0,
                        "doctype": "Email Account",
                        "name": "new-email-account-nrmkcyhlnc",
                        "__islocal": 1,
                        "__unsaved": 1,
                        "owner": "Administrator",
                        "enable_incoming": 1,
                        "enable_outgoing": 1,
                        "service": "",
                        "frappe_mail_site": "https://frappemail.com",
                        "auth_method": "Basic",
                        "backend_app_flow": 0,
                        "awaiting_password": 1,
                        "ascii_encode_password": 0,
                        "login_id_is_different": 0,
                        "default_incoming": 0,
                        "use_imap": 0,
                        "use_ssl": 0,
                        "validate_ssl_certificate": 1,
                        "use_starttls": 0,
                        "email_sync_option": "UNSEEN",
                        "initial_sync_count": "250",
                        "imap_folder": [
                            {
                                "docstatus": 0,
                                "doctype": "IMAP Folder",
                                "name": "new-imap-folder-dcfdjaadve",
                                "__islocal": 1,
                                "__unsaved": 1,
                                "owner": "Administrator",
                                "parent": "new-email-account-nrmkcyhlnc",
                                "parentfield": "imap_folder",
                                "parenttype": "Email Account",
                                "idx": 1,
                                "folder_name": "INBOX",
                            }
                        ],
                        "append_emails_to_sent_folder": 0,
                        "create_contact": 1,
                        "enable_automatic_linking": 0,
                        "notify_if_unreplied": 0,
                        "unreplied_for_mins": 30,
                        "default_outgoing": 0,
                        "always_use_account_email_id_as_sender": 0,
                        "always_use_account_name_as_sender_name": 0,
                        "send_unsubscribe_message": 1,
                        "track_email_status": 1,
                        "use_tls": 0,
                        "use_ssl_for_outgoing": 0,
                        "no_smtp_authentication": 0,
                        "add_signature": 0,
                        "enable_auto_reply": 0,
                        "attachment_limit": 25,
                        "password": "admin",
                        "email_id": "replies@acme.inc",
                        "email_account_name": "Replies",
                    }
                ),
            },
        )
        logger.succeed("Replies Email Account updated")
    except Exception as e:
        logger.warning(f"Replies Email Account already exists: {e}")
