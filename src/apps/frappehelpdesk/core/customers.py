import asyncio
import json
import random
from pathlib import Path

from faker import Faker

from apps.frappehelpdesk.config.settings import settings
from apps.frappehelpdesk.utils.frappe_client import FrappeClient
from common.logger import logger


fake = Faker()

# Cache file paths for customers
CUSTOMERS_CACHE_FILE = Path(Path(__file__).parent.parent, "data", "generated", "customers.json")
CUSTOMER_USERS_CACHE_FILE = Path(Path(__file__).parent.parent, "data", "generated", "customer_users.json")


async def generate_customers(number_of_customers: int):
    """
    Generate customers using Faker and save to JSON cache file.
    Always generates fresh data and overwrites existing cache.
    """
    logger.start(f"Generating {number_of_customers} customers...")

    customers_data = []
    generated_domains = set()  # Track generated domains to avoid duplicates
    generated_names = set()  # Track generated names to avoid duplicates

    attempts = 0
    max_attempts = number_of_customers * 5  # Allow more attempts than needed customers

    while len(customers_data) < number_of_customers and attempts < max_attempts:
        attempts += 1

        company_name = fake.company()
        company_name = company_name.replace(",", "")
        company_name = company_name.replace("-", " ")
        company_name = company_name.split(" and")[0]

        # Skip if company name already exists
        if company_name in generated_names:
            continue

        # Create base domain
        base_domain = "".join(c for c in company_name if c.isalnum()).lower() + ".com"
        domain = base_domain

        # If domain exists, try variations
        if domain in generated_domains:
            # Try with numbers
            for i in range(1, 100):
                domain = f"{base_domain.replace('.com', '')}{i}.com"
                if domain not in generated_domains:
                    break
            else:
                # If still no unique domain found, skip this iteration
                continue

        # Skip if domain still exists (shouldn't happen with above logic)
        if domain in generated_domains:
            continue

        # Add to tracking sets
        generated_domains.add(domain)
        generated_names.add(company_name)

        customer = {
            "doctype": "HD Customer",
            "customer_name": company_name,
            "domain": domain,
        }
        customers_data.append(customer)

    if len(customers_data) < number_of_customers:
        logger.warning(f"Could only generate {len(customers_data)} unique customers out of {number_of_customers} requested after {attempts} attempts")

    # Always save to cache (overwrite existing)
    try:
        CUSTOMERS_CACHE_FILE.parent.mkdir(exist_ok=True)
        with CUSTOMERS_CACHE_FILE.open("w") as f:
            json.dump(customers_data, f, indent=2)
        logger.info(f"Saved {len(customers_data)} fresh customers to {CUSTOMERS_CACHE_FILE}")
    except Exception as e:
        logger.warning(f"Error saving customers cache: {e}")

    logger.succeed(f"Generated {len(customers_data)} fresh customers")


async def seed_customers():
    """
    Read customers from cache file and insert them into Frappe helpdesk.
    """
    logger.start("Seeding customers...")

    # Load customers from cache
    if not CUSTOMERS_CACHE_FILE.exists():
        logger.fail("Customers cache file not found. Please run generate_customers first.")
        return

    try:
        with CUSTOMERS_CACHE_FILE.open() as f:
            customers_data = json.load(f)
    except (json.JSONDecodeError, Exception) as e:
        logger.fail(f"Error loading customers cache: {e}")
        return

    if not customers_data:
        logger.fail("No customers found in cache file")
        return

    async with FrappeClient() as client:
        # Insert customers from cached data
        for customer in customers_data:
            try:
                await client.insert(customer)
            except Exception as e:
                if "DuplicateEntryError" in str(e):
                    logger.info(f"Customer '{customer['customer_name']}' already exists, skipping creation")
                else:
                    logger.warning(f"Error inserting customer: {e}")

    logger.succeed(f"Seeded {len(customers_data)} customers")


async def generate_customer_users(max_customers: int):
    """
    Generate customer contacts using Faker and save to JSON cache file.
    Always generates fresh data and overwrites existing cache.
    """
    logger.start(f"Generating customer contacts for up to {max_customers} customers...")

    # Load customers from cache file
    if not CUSTOMERS_CACHE_FILE.exists():
        logger.fail("Customers cache file not found. Please run generate_customers first.")
        return

    try:
        with CUSTOMERS_CACHE_FILE.open() as f:
            customers_data = json.load(f)
    except (json.JSONDecodeError, Exception) as e:
        logger.fail(f"Error loading customers cache: {e}")
        return

    if not customers_data:
        logger.fail("No customers found in cache file")
        return

    # Limit the number of customers to process
    actual_customers_count = min(max_customers, len(customers_data))
    selected_customers = fake.random_elements(elements=customers_data, length=actual_customers_count, unique=True)

    # Generate fresh customer contacts
    logger.info(f"Generating contacts for {actual_customers_count} customers from cache")
    contact_docs_data = []
    generated_emails = set()  # Track generated emails to avoid duplicates

    for customer in selected_customers:
        contacts_per_customer = random.randint(1, 3)
        attempts = 0
        max_attempts_per_customer = contacts_per_customer * 5
        contacts_created_for_customer = 0

        while contacts_created_for_customer < contacts_per_customer and attempts < max_attempts_per_customer:
            attempts += 1

            first_name = fake.first_name()
            last_name = fake.last_name()
            full_name = f"{first_name} {last_name}"

            # Create email using customer domain
            base_email = f"{''.join(c for c in first_name if c.isalnum()).lower()}.{''.join(c for c in last_name if c.isalnum()).lower()}@{customer['domain']}"
            email = base_email

            # If email exists, try variations
            if email in generated_emails:
                # Try with middle initial
                middle_initial = fake.random_letter().lower()
                email = f"{''.join(c for c in first_name if c.isalnum()).lower()}.{middle_initial}.{''.join(c for c in last_name if c.isalnum()).lower()}@{customer['domain']}"

                # If still duplicate, try with numbers
                if email in generated_emails:
                    for i in range(1, 100):
                        email = f"{''.join(c for c in first_name if c.isalnum()).lower()}.{''.join(c for c in last_name if c.isalnum()).lower()}{i}@{customer['domain']}"
                        if email not in generated_emails:
                            break
                    else:
                        # If still no unique email found, skip this iteration
                        continue

            # Skip if email still exists
            if email in generated_emails:
                continue

            # Add to tracking set
            generated_emails.add(email)

            contact_doc = {
                "doctype": "Contact",
                "first_name": first_name,
                "last_name": last_name,
                "full_name": full_name,
                "email_ids": [
                    {
                        "email_id": email,
                        "is_primary": 1,
                    }
                ],
                "phone_nos": [
                    {
                        "phone": fake.numerify("###-###-####"),
                        "is_primary_phone": 1,
                    }
                ],
                "links": [
                    {
                        "link_doctype": "HD Customer",
                        "link_name": customer["customer_name"],
                        "link_title": customer["customer_name"],
                    }
                ],
                "status": "Open",
                # Store customer info for reference
                "customer_name": customer["customer_name"],
                "customer_domain": customer["domain"],
            }

            contact_docs_data.append(contact_doc)
            contacts_created_for_customer += 1

    # Always save to cache (overwrite existing)
    try:
        CUSTOMER_USERS_CACHE_FILE.parent.mkdir(exist_ok=True)
        cache_data = {"contact_docs": contact_docs_data, "customers_count": actual_customers_count}

        with CUSTOMER_USERS_CACHE_FILE.open("w") as f:
            json.dump(cache_data, f, indent=2)
        logger.info(f"Saved {len(contact_docs_data)} fresh customer contacts to {CUSTOMER_USERS_CACHE_FILE}")
    except Exception as e:
        logger.warning(f"Error saving customer contacts cache: {e}")

    logger.succeed(f"Generated {len(contact_docs_data)} fresh customer contacts")


async def seed_customer_users():
    """
    Read customer contacts from cache file and insert them into Frappe helpdesk.
    """
    logger.start("Seeding customer users...")

    # Load customer contacts from cache
    if not CUSTOMER_USERS_CACHE_FILE.exists():
        logger.fail("Customer contacts cache file not found. Please run generate_customer_users first.")
        return

    try:
        with CUSTOMER_USERS_CACHE_FILE.open() as f:
            cache_data = json.load(f)
            contact_docs_data = cache_data.get("contact_docs", [])
    except (json.JSONDecodeError, KeyError, Exception) as e:
        logger.fail(f"Error loading customer contacts cache: {e}")
        return

    if not contact_docs_data:
        logger.fail("No customer contacts found in cache file")
        return

    successful_contacts = 0
    successful_invites = 0

    # Use a single shared client for all operations
    async with FrappeClient() as client:

        async def process_contact(contact_doc):
            nonlocal successful_contacts, successful_invites

            contact_name = f"{contact_doc['full_name']}-{contact_doc['customer_name']}"
            email = contact_doc["email_ids"][0]["email_id"]

            max_retries = 3
            retry_delay = 1  # seconds

            # Step 1: Insert contact (no retry needed for duplicates)
            try:
                doc_data = {
                    "doctype": "Contact",
                    "first_name": contact_doc["first_name"],
                    "last_name": contact_doc["last_name"],
                    "email_ids": contact_doc["email_ids"],
                    "links": contact_doc["links"],
                    "phone_nos": contact_doc["phone_nos"],
                }

                await client.insert(doc_data)
                successful_contacts += 1

            except Exception as e:
                if "DuplicateEntryError" in str(e):
                    logger.info(f"Contact '{contact_doc['full_name']}' already exists, skipping creation")
                else:
                    logger.warning(f"Error inserting contact {contact_name}: {e}")
                    return  # If contact creation fails (non-duplicate), skip other steps

            # Step 2: Try to invite user (with retries and fallback approaches)
            user_invited = False
            for attempt in range(max_retries):
                try:
                    # Try different API formats
                    if attempt == 0:
                        # Method 1: Direct contact invite
                        await client.post_api("frappe.contacts.doctype.contact.contact.invite_user", contact_name)
                    elif attempt == 1:
                        # Method 2: Alternative parameter format
                        await client.post_api("frappe.contacts.doctype.contact.contact.invite_user", {"contact": contact_name})
                    else:
                        # Method 3: Create user directly
                        user_doc = {
                            "doctype": "User",
                            "email": email,
                            "first_name": contact_doc["first_name"],
                            "last_name": contact_doc["last_name"],
                            "full_name": contact_doc["full_name"],
                            "user_type": "Website User",
                            "new_password": settings.USER_PASSWORD,
                            "enabled": 1,
                        }
                        await client.insert(user_doc)

                    successful_invites += 1
                    user_invited = True
                    break  # Success, exit retry loop
                except Exception as e:
                    if attempt < max_retries - 1:
                        await asyncio.sleep(retry_delay)
                    else:
                        logger.warning(f"All invite methods failed for {email}: {e}")

            # Step 3: Update contact with user link (if user was created)
            if user_invited:
                try:
                    await client.update({"doctype": "Contact", "name": contact_name, "user": email})
                except Exception as e:
                    logger.warning(f"Failed to link user to contact {contact_name}: {e}")

        semaphore = asyncio.Semaphore(5)

        async def process_with_semaphore(contact_doc):
            async with semaphore:
                await process_contact(contact_doc)

        tasks = [process_with_semaphore(contact_doc) for contact_doc in contact_docs_data]
        await asyncio.gather(*tasks, return_exceptions=True)

    logger.succeed(f"Seeded {successful_contacts}/{len(contact_docs_data)} customer contacts and invited {successful_invites} as users")
