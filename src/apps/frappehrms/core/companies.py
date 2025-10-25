import json
from pathlib import Path

from apps.frappehrms.utils import frappe_client
from common.logger import logger


async def insert_companies():
    # Read companies from JSON file
    json_path = Path(__file__).parent.parent.joinpath("data", "companies.json")

    try:
        companies_data = json.loads(json_path.read_text(encoding="utf-8"))
        logger.info(f"Loaded {len(companies_data)} companies from JSON file")
    except Exception as e:
        logger.error(f"Failed to read companies data: {e!s}")
        return

    # Create Frappe client
    client = frappe_client.create_client()

    company_docs = [
        {
            "doctype": "Company",
            "company_name": company["name"],
            "abbr": company["abbr"],
            "default_currency": company["default_currency"],
            "country": company["country"],
            "phone_no": company.get("phone", ""),
            "email": company.get("email", ""),
            "website": company.get("website", ""),
            "tax_id": company.get("tax_id", ""),
            "address": company.get("address", ""),
            "domain": company.get("domain", ""),
        }
        for company in companies_data
    ]

    # Batch insert all companies
    for company_doc in company_docs:
        try:
            client.insert(company_doc)
            logger.info(f"Successfully added company {company_doc['company_name']}")
        except Exception as e:
            logger.error(f"Failed to add company {company_doc['company_name']}: {e!s}")


def delete_generated_companies():
    client = frappe_client.create_client()

    # Read companies from JSON file to get the names
    json_path = Path(__file__).parent.parent.joinpath("data", "companies.json")

    try:
        companies_data = json.loads(json_path.read_text(encoding="utf-8"))
    except Exception as e:
        logger.error(f"Failed to read companies data for deletion: {e!s}")
        return

    # Delete each company by name
    for company in companies_data:
        try:
            client.delete("Company", company["name"])
        except Exception as e:
            logger.error(f"Failed to delete company {company['name']}: {e!s}")

    logger.info("Company deletion process completed")


def get_default_company():
    client = frappe_client.create_client()
    logger.info("Getting default company")
    list_company = client.get_list("Company")
    if not list_company or not list_company[0]:
        raise Exception("No companies found")

    return client.get_doc("Company", list_company[0]["name"])
