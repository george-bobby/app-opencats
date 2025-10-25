import asyncio
import json
import random
from pathlib import Path

from faker import Faker

from apps.frappecrm.config.settings import settings
from apps.frappecrm.utils import frappe_client
from common.logger import logger


# Define constants at the module level for reuse
COUNTRIES_JSON_FILE = Path(__file__).parent.parent.joinpath("data/countries.json")

fake = Faker()


async def generate_addresses(number_of_addresses: int = 0, address_titles: list[str] | None = None):
    """Generate addresses data and save to JSON file"""
    json_file_path = Path(__file__).parent.parent.joinpath("data/generated/addresses.json")

    # Ensure the directory exists
    json_file_path.parent.mkdir(parents=True, exist_ok=True)

    logger.info("Generating new addresses data")
    addresses_data = await generate_addresses_data(number_of_addresses, address_titles)

    # Save the generated addresses to the JSON file
    try:
        with json_file_path.open("w", encoding="utf-8") as f:
            json.dump(addresses_data, f, indent=2, ensure_ascii=False)
        logger.succeed(f"Saved {len(addresses_data)} addresses to {json_file_path}")
    except Exception as e:
        logger.error(f"Error saving addresses to file: {e}")

    return addresses_data


async def insert_addresses(number_of_addresses: int = 200, address_titles: list[str] | None = None):
    """
    Insert addresses from JSON file based on data from addresses.json

    Args:
        number_of_addresses: Number of address records to insert (default: 0)
        address_titles: Optional list of address titles to use instead of inserting random ones

    Returns:
        List of inserted address dictionaries
    """
    # Define the path to the JSON file
    json_file_path = Path(__file__).parent.parent.joinpath("data/generated/addresses.json")
    client = frappe_client.create_client()

    # Check if the JSON file exists and read from it
    if not json_file_path.exists():
        logger.error(f"Addresses data file not found at {json_file_path}. Please run generate command first.")
        return []

    try:
        with json_file_path.open(encoding="utf-8") as f:
            addresses_data = json.load(f)
        logger.info(f"Loaded {len(addresses_data)} addresses from file")
    except Exception as e:
        logger.error(f"Error reading addresses from file: {e}")
        return []

    # Insert addresses from the data
    existing_addresses = client.get_list(
        "Address",
        fields=["address_title"],
        limit_page_length=settings.LIST_LIMIT,
    )
    existing_address_titles = [addr["address_title"] for addr in existing_addresses]

    addresses_to_insert = []
    target_addresses = addresses_data

    # If address_titles is provided, filter to only those addresses
    if address_titles:
        target_addresses = [addr for addr in addresses_data if addr["address_title"] in address_titles]
    elif number_of_addresses > 0:
        target_addresses = addresses_data[:number_of_addresses]

    for addr_data in target_addresses:
        # Skip if address already exists
        if addr_data["address_title"] in existing_address_titles:
            logger.info(f"Address '{addr_data['address_title']}' already exists, skipping")
            continue
        addresses_to_insert.append(addr_data)

    if not addresses_to_insert:
        logger.info("No new addresses to insert")
        # Return existing addresses that match the requested titles
        if address_titles:
            return [addr for addr in addresses_data if addr["address_title"] in address_titles]
        else:
            return addresses_data[:number_of_addresses] if number_of_addresses > 0 else addresses_data

    # Insert addresses and track results
    inserted_addresses = []
    for address in addresses_to_insert:
        try:
            response = client.insert(address)
            inserted_addresses.append(response)
        except Exception as e:
            logger.info(json.dumps(address, indent=2))
            logger.warning(f"Error inserting address: {e}")

    # Return the requested addresses (both newly inserted and existing)
    all_target_addresses = []
    for addr_data in target_addresses:
        if addr_data["address_title"] in existing_address_titles:
            # Find existing address data
            existing_addr = next(
                (addr for addr in existing_addresses if addr["address_title"] == addr_data["address_title"]),
                None,
            )
            if existing_addr:
                all_target_addresses.append(existing_addr)
        else:
            # Find newly inserted address
            inserted_addr = next(
                (addr for addr in inserted_addresses if addr.get("address_title") == addr_data["address_title"]),
                None,
            )
            if inserted_addr:
                all_target_addresses.append(inserted_addr)

    logger.succeed(f"Successfully inserted {len(addresses_to_insert)} addresses")
    return all_target_addresses


async def delete_addresses():
    client = frappe_client.create_client()
    addresses = client.get_list(
        "Address",
        fields=["name"],
        limit_page_length=settings.LIST_LIMIT,
    )
    for address in addresses:
        try:
            client.delete("Address", address["name"])
            logger.info(f"Deleted address: {address['name']}")
        except Exception as e:
            logger.error(f"Error deleting address: {e}")
            logger.error(json.dumps(address, indent=4))


async def generate_contacts(contacts_per_org: tuple[int, int] = (1, 3)):
    """Generate contacts data and save to JSON file"""
    json_file_path = Path(__file__).parent.parent.joinpath("data/generated/contacts.json")

    # Ensure the directory exists
    json_file_path.parent.mkdir(parents=True, exist_ok=True)

    logger.info("Generating new contacts data")
    contacts_data = await generate_contacts_data(contacts_per_org)

    # Save the generated contacts to the JSON file
    try:
        with json_file_path.open("w", encoding="utf-8") as f:
            json.dump(contacts_data, f, indent=2, ensure_ascii=False)
        logger.info(f"Saved {len(contacts_data)} contacts to {json_file_path}")
    except Exception as e:
        logger.error(f"Error saving contacts to file: {e}")

    # Extract all unique address titles from contacts data
    address_titles = list({contact.get("address") for contact in contacts_data if contact.get("address")})

    # Generate addresses proportional to the number of contacts/organizations
    # Estimate 2-3 addresses per unique organization
    num_addresses = max(len(address_titles), len(contacts_data) // 2)

    # Generate addresses for the contacts if needed
    if address_titles:
        logger.info(f"Generating {num_addresses} addresses for contact references")
        await generate_addresses(num_addresses, address_titles)


async def insert_contacts(
    # number_of_orgs: int, contacts_per_org: tuple[int, int] = (1, 3)
):
    client = frappe_client.create_client()
    # Define the path to the JSON file
    json_file_path = Path(__file__).parent.parent.joinpath("data/generated/contacts.json")

    # Check if the JSON file exists and read from it
    if not json_file_path.exists():
        logger.error(f"Contacts data file not found at {json_file_path}. Please run generate command first.")
        return

    try:
        with json_file_path.open(encoding="utf-8") as f:
            contacts_data = json.load(f)
        logger.info(f"Loaded {len(contacts_data)} contacts from file")
    except Exception as e:
        logger.error(f"Error reading contacts from file: {e}")
        return

    logger.start(f"Inserting {len(contacts_data)} contacts")

    # Extract all unique address titles from contacts data
    address_titles = list({contact.get("address") for contact in contacts_data if contact.get("address")})

    # When using cached contact data, we need to ensure the address cache includes all referenced addresses
    if address_titles:
        # Load existing address cache
        address_json_path = Path(__file__).parent.parent.joinpath("data/generated/addresses.json")
        existing_address_data = []
        if address_json_path.exists():
            try:
                with address_json_path.open(encoding="utf-8") as f:
                    existing_address_data = json.load(f)
            except Exception as e:
                logger.error(f"Error reading address cache: {e}")

        # Check which addresses are missing from cache
        existing_address_titles = [addr["address_title"] for addr in existing_address_data]
        missing_address_titles = [title for title in address_titles if title not in existing_address_titles]

        if missing_address_titles:
            logger.info(f"Generating {len(missing_address_titles)} missing addresses for contact cache")
            # Generate missing addresses and add them to cache
            new_addresses = await generate_addresses_data(0, missing_address_titles)
            existing_address_data.extend(new_addresses)

            # Update address cache
            try:
                address_json_path.parent.mkdir(parents=True, exist_ok=True)
                with address_json_path.open("w", encoding="utf-8") as f:
                    json.dump(existing_address_data, f, indent=2, ensure_ascii=False)
                logger.info(f"Updated address cache with {len(missing_address_titles)} new addresses")
            except Exception as e:
                logger.error(f"Error updating address cache: {e}")

        # Now insert all required addresses
        await insert_addresses(address_titles=address_titles)

    # Insert contacts from the data
    existing_contacts = client.get_list(
        "Contact",
        fields=["email_id", "company_name"],
        limit_page_length=settings.LIST_LIMIT,
    )
    existing_contact_keys = [f"{contact['email_id']}-{contact['company_name']}" for contact in existing_contacts]

    contacts_to_insert = []
    for contact_data in contacts_data:
        # Skip if contact already exists (using email + company as unique key)
        contact_key = f"{contact_data['email_id']}-{contact_data['company_name']}"
        if contact_key in existing_contact_keys:
            logger.info(f"Contact '{contact_data['full_name']} - {contact_data['company_name']}' already exists, skipping")
            continue

        # Remove address field to avoid link validation errors
        contact_data.pop("address", None)

        contacts_to_insert.append(contact_data)

    if not contacts_to_insert:
        logger.info("No new contacts to insert")
        return

    async def insert_contact(contact: dict):
        try:
            # Use run_in_executor to make the blocking client.insert call non-blocking
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(None, lambda: client.insert(contact))
            # logger.info(f"Inserted contact: {contact['full_name']} - {contact['company_name']}")
            return response
        except Exception as e:
            logger.error(f"Error inserting contact: {e}")
            logger.error(json.dumps(contact, indent=4))

    # Create a semaphore to limit concurrent executions to 1
    semaphore = asyncio.Semaphore(1)

    async def insert_contact_with_limit(contact: dict):
        async with semaphore:
            return await insert_contact(contact)

    results = await asyncio.gather(*[insert_contact_with_limit(contact) for contact in contacts_to_insert])
    logger.succeed(f"Successfully inserted {len(contacts_to_insert)} contacts")
    return results


async def delete_contacts():
    client = frappe_client.create_client()
    contacts = client.get_list(
        "Contact",
        fields=["name"],
        limit_page_length=settings.LIST_LIMIT,
    )
    for contact in contacts:
        try:
            client.delete("Contact", contact["name"])
            logger.info(f"Deleted contact: {contact['name']}")
        except Exception as e:
            logger.error(f"Error deleting contact: {e}")
            logger.error(json.dumps(contact, indent=4))


async def generate_addresses_data(number_of_addresses: int = 0, address_titles: list[str] | None = None):
    """Generate addresses data and return them as a list of dictionaries"""
    # Load reference data from contacts.json
    with COUNTRIES_JSON_FILE.open(encoding="utf-8") as f:
        reference_data = json.load(f)["reference_data"]

    countries = list(reference_data["countries"].keys())
    address_types = reference_data["address_types"]

    # Determine actual count of addresses to create
    actual_count = number_of_addresses
    if address_titles:
        # If address_titles is provided but number_of_addresses is 0,
        # use the length of address_titles
        actual_count = len(address_titles) if number_of_addresses == 0 else min(number_of_addresses, len(address_titles))

    addresses = []
    for i in range(actual_count):
        # Select a random country and get its states/provinces
        country = random.choice(countries)
        states = reference_data["countries"][country]

        address = {
            "doctype": "Address",
            "address_title": address_titles[i] if address_titles else (fake.company() if random.random() > 0.5 else fake.name()),
            "address_type": random.choice(address_types),
            "address_line1": fake.street_address(),
            "address_line2": fake.secondary_address() if random.random() > 0.3 else None,
            "city": fake.city(),
            "county": fake.city_suffix() if random.random() > 0.7 else None,
            "state": random.choice(states),
            "country": country,
            "pincode": fake.zipcode(),
            "email_id": fake.email() if random.random() > 0.5 else None,
            "phone": fake.numerify("(###) ###-####") if random.random() > 0.2 else None,
            "fax": fake.numerify("(###) ###-####") if random.random() > 0.8 else None,
        }
        addresses.append(address)

    return addresses


async def generate_contacts_data(
    # number_of_orgs: int,
    contacts_per_org: tuple[int, int] = (1, 3),
):
    """Generate contacts data and return them as a list of dictionaries"""
    # Load designations from contacts.json
    client = frappe_client.create_client()
    with COUNTRIES_JSON_FILE.open(encoding="utf-8") as f:
        contacts_data = json.load(f)
        designations = contacts_data.get("designations", [])

    orgs = client.get_list(
        "CRM Organization",
        fields=["name", "address", "website"],
        limit_page_length=settings.LIST_LIMIT,
    )
    contacts = []
    for org in orgs:
        for _ in range(random.randint(contacts_per_org[0], contacts_per_org[1])):
            gender = fake.random_element(["Male", "Female", "Other"])
            first_name = fake.first_name_male() if gender == "Male" else fake.first_name_female()
            last_name = fake.last_name()
            full_name = f"{first_name} {last_name}"

            # Generate email based on company website if available
            if org.get("website"):
                domain = org["website"].replace("http://", "").replace("https://", "").split("/")[0]
                email = f"{first_name.lower()}.{last_name.lower()}@{domain}"
            else:
                email = fake.email()
            phone = fake.numerify("(###) ###-####")

            # Determine salutation based on gender
            if gender == "Male":
                salutation = fake.random_element(["Mr", "Dr", "Master"])
            elif gender == "Female":
                salutation = fake.random_element(["Mrs", "Ms", "Miss", "Dr", "Madam"])
            else:
                salutation = fake.random_element(["Dr", "Mx"])

            contact = {
                "doctype": "Contact",
                "first_name": first_name,
                "last_name": last_name,
                "full_name": full_name,
                "email_id": email,
                "address": org["address"],
                "status": fake.random_element(["Passive", "Open", "Replied"]),
                "salutation": salutation,
                "designation": random.choice(designations),
                "gender": gender,
                "company_name": org["name"],
                "department": fake.random_element(["Sales", "Marketing", "Engineering", "Support", "HR", "Finance"]) if fake.boolean(chance_of_getting_true=70) else None,
                "email_ids": [
                    {
                        "email_id": email,
                        "is_primary": 1,
                        "parentfield": "email_ids",
                        "parenttype": "Contact",
                        "doctype": "Contact Email",
                    }
                ],
                "phone_nos": [
                    {
                        "phone": phone,
                        "is_primary_phone": 1,
                        "is_primary_mobile_no": 1,
                        "parentfield": "phone_nos",
                        "parenttype": "Contact",
                        "doctype": "Contact Phone",
                    }
                ],
            }
            contacts.append(contact)

    return contacts


async def update_empty_contacts():
    client = frappe_client.create_client()
    contacts = client.get_list(
        "Contact",
        limit_page_length=settings.LIST_LIMIT,
    )

    logger.start(f"Updating {len(contacts)} contacts")

    async def add_phone_number(contact: dict):
        contact["doctype"] = "Contact"
        contact["phone_nos"] = [
            {
                "phone": fake.numerify("(###) ###-####"),
                "is_primary_phone": 1,
                "is_primary_mobile_no": 1,
            }
        ]
        contact["company_name"] = settings.COMPANY_NAME

        try:
            client.update(contact)
            await asyncio.sleep(0.5)
        except Exception as e:
            logger.error(f"Error updating contact: {e}")
            logger.error(json.dumps(contact, indent=4))

    # First pass - update missing phone numbers
    for contact in contacts:
        if not contact.get("mobile_no") or not contact.get("phone") or not contact.get("company_name"):
            await add_phone_number(contact)

    # Second pass - verify and update any remaining missing info
    contacts = client.get_list(
        "Contact",
        limit_page_length=settings.LIST_LIMIT,
    )
    for contact in contacts:
        if not contact.get("mobile_no") or not contact.get("phone") or not contact.get("company_name"):
            await add_phone_number(contact)

    logger.succeed(f"Successfully updated {len(contacts)} contacts")
