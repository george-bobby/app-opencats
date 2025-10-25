import json
from pathlib import Path

from faker import Faker

from apps.frappecrm.config.settings import settings
from apps.frappecrm.core import contacts
from apps.frappecrm.utils import frappe_client
from common.logger import logger


fake = Faker()


async def generate_organizations(number_of_organizations: int):
    """Generate organizations data and save to JSON file"""
    # Define the path to the JSON file
    json_file_path = Path(__file__).parent.parent.joinpath("data/generated/organizations.json")

    # Ensure the directory exists
    json_file_path.parent.mkdir(parents=True, exist_ok=True)

    logger.info("Generating new organizations data")
    organizations_data = await generate_organizations_data(number_of_organizations)

    # Save the generated organizations to the JSON file
    try:
        with json_file_path.open("w", encoding="utf-8") as f:
            json.dump(organizations_data, f, indent=2, ensure_ascii=False)
        logger.info(f"Saved {len(organizations_data)} organizations to {json_file_path}")
    except Exception as e:
        logger.error(f"Error saving organizations to file: {e}")


async def insert_organizations(number_of_organizations: int):
    # Define the path to the JSON file
    json_file_path = Path(__file__).parent.parent.joinpath("data/generated/organizations.json")
    client = frappe_client.create_client()

    logger.start(f"Inserting {number_of_organizations} organizations")

    # Check if the JSON file exists and read from it
    if not json_file_path.exists():
        logger.error(f"Organizations data file not found at {json_file_path}. Please run generate command first.")
        return

    try:
        with json_file_path.open(encoding="utf-8") as f:
            organizations_data = json.load(f)
        logger.info(f"Loaded {len(organizations_data)} organizations from file")
    except Exception as e:
        logger.error(f"Error reading organizations from file: {e}")
        return

    # Extract all unique address names from organizations data
    address_titles = list({org.get("address") for org in organizations_data if org.get("address")})

    # When using cached organization data, we need to ensure the address cache includes all referenced addresses
    if address_titles:
        # Create/ensure all required addresses exist
        await contacts.insert_addresses(address_titles=address_titles)

        # Get the actual address IDs for mapping
        existing_addresses = client.get_list(
            "Address",
            fields=["name", "address_title"],
            limit_page_length=settings.LIST_LIMIT,
        )
        address_title_to_id = {addr["address_title"]: addr["name"] for addr in existing_addresses}

        # Update organization data to use address IDs instead of titles
        for org in organizations_data:
            if org.get("address") and org["address"] in address_title_to_id:
                org["address"] = address_title_to_id[org["address"]]
            else:
                org["address"] = None

    # Insert organizations from the data
    existing_organizations = client.get_list(
        "CRM Organization",
        fields=["organization_name"],
        limit_page_length=settings.LIST_LIMIT,
    )
    existing_org_names = [org.get("organization_name", "") for org in existing_organizations]

    organizations_to_insert = []
    for org_data in organizations_data[:number_of_organizations]:
        # Skip if organization already exists
        if org_data["organization_name"] in existing_org_names:
            logger.info(f"Organization '{org_data['organization_name']}' already exists, skipping")
            continue
        organizations_to_insert.append(org_data)

    if not organizations_to_insert:
        logger.info("No new organizations to insert")
        return

    inserted_count = 0
    for organization in organizations_to_insert:
        try:
            client.insert(organization)
            inserted_count += 1
        except Exception as e:
            logger.error(f"Error inserting organization {organization['organization_name']}: {e}")
            logger.error(json.dumps(organization, indent=4))

    logger.succeed(f"Successfully inserted {inserted_count} organizations")


async def generate_organizations_data(number_of_organizations: int):
    """Generate organizations data and return them as a list of dictionaries"""

    client = frappe_client.create_client()

    industries = client.get_list(
        "CRM Industry",
        fields=["name"],
        limit_page_length=settings.LIST_LIMIT,
    )
    industry_names = [industry["name"] for industry in industries]

    organizations = []

    for _ in range(number_of_organizations):
        organization_name = fake.company().replace("-", " ").replace(",", "")

        # Create website from organization name
        website_name = organization_name.lower()
        # Remove special characters and spaces
        website_name = "".join(c for c in website_name if c.isalnum() or c.isspace())
        website_name = website_name.replace(" ", "").replace("and", "")

        organization = {
            "doctype": "CRM Organization",
            "organization_name": organization_name,
            "industry": fake.random_element(industry_names) if industry_names else None,
            "no_of_employees": fake.random_element(["1-10", "11-50", "51-200", "201-500", "501-1000", "1000+"]),
            "currency": "USD",
            "annual_revenue": round(fake.random_number(digits=6) * 15, 2) if fake.boolean(chance_of_getting_true=70) else 1000000,
            "website": f"{website_name}.com",
            "address": organization_name,  # Reference the address title, not the address ID
        }
        organizations.append(organization)

    return organizations


async def delete_organizations():
    client = frappe_client.create_client()

    organizations = client.get_list(
        "CRM Organization",
        fields=["name"],
        limit_page_length=settings.LIST_LIMIT,
    )
    for organization in organizations:
        try:
            client.delete("CRM Organization", organization["name"])
            logger.info(f"Deleted organization: {organization['name']}")
        except Exception as e:
            logger.error(f"Error deleting organization: {e}")
            logger.error(json.dumps(organization, indent=4))
