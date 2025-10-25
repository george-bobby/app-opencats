import json
import logging

from frappeclient import FrappeClient

from apps.frappehrms.config.settings import settings


def create_client(
    url=settings.API_URL,
    username=settings.ADMIN_USERNAME,
    password=settings.ADMIN_PASSWORD,
):
    """Create a Frappe client instance."""
    client = FrappeClient(url)
    client.login(username, password)

    # Add custom methods
    def insert_many_json(docs):
        """Custom insert_many that uses json.dumps instead of frappe.as_json."""
        try:
            return client.post_request({"cmd": "frappe.client.insert_many", "docs": json.dumps(docs)})
        except Exception as e:
            logging.error(f"Error inserting many documents: {e!s}")
            raise

    def assign(doctype: str, docs: list[str], assignees: list[str]):
        return client.post_request(
            {
                "cmd": "frappe.desk.form.assign_to.add_multiple",
                "doctype": doctype,
                "name": docs,
                "assign_to": assignees,
                "bulk_assign": True,
                "re_assign": True,
            }
        )

    client.insert_many = insert_many_json
    client.assign = assign

    return client
