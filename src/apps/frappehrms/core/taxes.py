import json
from pathlib import Path

from apps.frappehrms.core import companies
from apps.frappehrms.utils import frappe_client
from common.logger import logger


async def insert_income_tax_slabs():
    """
    Insert income tax slabs from the taxes.json file into Frappe.
    """
    company = companies.get_default_company()
    company_name = company["name"]

    # Create Frappe client
    client = frappe_client.create_client()

    # Read tax slabs from JSON file
    json_path = Path(__file__).parent.parent.joinpath("data", "taxes.json")

    try:
        with json_path.open(encoding="utf-8") as file:
            tax_data = json.load(file)
    except Exception as e:
        logger.error(f"Failed to read tax data: {e!s}")
        return

    # Process each tax slab
    for tax_slab in tax_data.get("income_tax_slabs", []):
        # Create the main Income Tax Slab document
        tax_slab_doc = {
            "doctype": "Income Tax Slab",
            "name": tax_slab["name"],
            "owner": "Administrator",
            "docstatus": 1,
            "idx": 0,
            "disabled": 0,
            "effective_from": tax_slab.get("effective_date", ""),
            "company": company_name,
            "currency": "USD",
            "standard_tax_exemption_amount": 0,
            "allow_tax_exemption": 0,
            "amended_from": None,
            "slabs": [],
        }

        # Add individual tax slabs
        for idx, slab in enumerate(tax_slab.get("slabs", []), 1):
            tax_slab_doc["slabs"].append(
                {
                    "name": f"slab-{idx}",
                    "owner": "Administrator",
                    "modified_by": "Administrator",
                    "docstatus": 0,
                    "idx": idx,
                    "from_amount": slab["from_amount"],
                    "to_amount": slab["to_amount"] if slab["to_amount"] is not None else 9999999999,
                    "percent_deduction": slab["percent_deduction"],
                    "condition": slab.get("condition", ""),
                    "parent": tax_slab["name"],
                    "parentfield": "slabs",
                    "parenttype": "Income Tax Slab",
                    "doctype": "Taxable Salary Slab",
                    "__unsaved": 1,
                }
            )

        # Insert the tax slab document
        try:
            client.insert(tax_slab_doc)
            logger.info(f"Successfully added income tax slab: {tax_slab['name']}")
        except Exception as e:
            logger.error(f"Failed to add income tax slab {tax_slab['name']}: {e!s}")


def delete_all_taxes():
    """
    Delete all tax slabs from Frappe.
    """
    client = frappe_client.create_client()
    tax_slabs = client.get_list("Income Tax Slab")

    if not tax_slabs:
        logger.warning("No tax slabs to delete")
        return

    for slab in tax_slabs:
        logger.info(f"Deleting tax slab: {slab['name']}")
        try:
            client.delete("Income Tax Slab", slab["name"])
        except Exception as e:
            logger.error(f"Failed to delete tax slab: {slab['name']}")
            logger.error(f"Error message: {str(e).splitlines()[0]}")
