import asyncio
import json
from datetime import datetime
from pathlib import Path

from pydantic import BaseModel, Field

from apps.chatwoot.config.settings import settings
from apps.chatwoot.utils.chatwoot import ChatwootClient
from apps.chatwoot.utils.faker import faker
from common.logger import logger


CONTACTS_FILE_PATH = settings.DATA_PATH / "generated" / "contacts.json"


class ContactData(BaseModel):
    name: str = Field(description="The full name of the contact")
    email: str = Field(description="The email address of the contact")
    phone_number: str = Field(description="The phone number of the contact")
    company_name: str = Field(description="The company name of the contact")
    city: str = Field(description="The city of the contact")
    state: str = Field(description="The state of the contact")
    username: str = Field(description="The username derived from the name")
    customer_since: str = Field(description="The date when the customer joined")
    social_profiles: dict = Field(description="Social media profiles")
    created_at: datetime = Field(description="When the contact was created")
    updated_at: datetime = Field(description="When the contact was last updated")


class ContactList(BaseModel):
    contacts: list[ContactData] = Field(description="A list of contacts")


def load_us_cities_data():
    """Load US cities data from the JSON file."""
    us_cities_file = Path(__file__).parent.parent.joinpath("data", "us_cities.json")
    try:
        with us_cities_file.open(encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        logger.warning(f"US cities file not found: {us_cities_file}")
        return {}


async def generate_contacts(number_of_contacts: int):
    """Generate specified number of contacts using faker and save them to JSON file."""
    # Ensure the generated directory exists
    CONTACTS_FILE_PATH.parent.mkdir(parents=True, exist_ok=True)

    # Load US cities data
    us_cities_data = load_us_cities_data()

    logger.start(f"Generating {number_of_contacts} contacts")

    contacts = []
    for _ in range(number_of_contacts):
        name = faker.name()
        username = name.replace(" ", "").lower()
        company_name = faker.normal_company_name()
        company_email = faker.company_email(
            first_name=name.split(" ")[0],
            last_name=name.split(" ")[1],
            domain="".join(c for c in company_name.lower() if c.isalnum()) + ".com",
        )

        # Use US cities data if available, otherwise fallback to faker
        if us_cities_data:
            # Select a random state
            state = faker.random_element(list(us_cities_data.keys()))
            # Select a random city from that state
            city = faker.random_element(us_cities_data[state])
        else:
            state = faker.state()
            city = faker.city()

        customer_since = faker.date_time_between(start_date="-2y", end_date="now").isoformat()

        # Generate faker timestamps
        created_at = faker.date_time_between(start_date="-1y", end_date="-1m")
        updated_at = faker.date_time_between(start_date=created_at, end_date="now")

        social_profiles = {
            "facebook": faker.random_element([username, None]),
            "github": faker.random_element([username, None]),
            "instagram": faker.random_element([username, None]),
            "linkedin": faker.random_element([username, None]),
            "twitter": faker.random_element([username, None]),
        }

        contacts.append(
            ContactData(
                name=name,
                email=company_email,
                phone_number=faker.numerify("+1##########"),
                company_name=company_name,
                city=city,
                state=state,
                username=username,
                customer_since=customer_since,
                social_profiles=social_profiles,
                created_at=created_at,
                updated_at=updated_at,
            )
        )

    # Convert Pydantic models to dictionaries before serializing to JSON
    serializable_contacts = [contact.model_dump(mode="json") for contact in contacts]

    # Store contacts in JSON file
    with CONTACTS_FILE_PATH.open("w", encoding="utf-8") as f:
        json.dump(serializable_contacts, f, indent=2, default=str)
        logger.succeed(f"Stored {len(contacts)} contacts in {CONTACTS_FILE_PATH}")


async def seed_contacts():
    """Seed contacts from JSON file into Chatwoot."""
    async with ChatwootClient() as client:
        contacts = None
        try:
            with CONTACTS_FILE_PATH.open(encoding="utf-8") as f:
                contacts = [ContactData(**contact) for contact in json.load(f)]
                logger.info(f"Loaded {len(contacts)} contacts from {CONTACTS_FILE_PATH}")
        except FileNotFoundError:
            logger.error(f"Contacts file not found: {CONTACTS_FILE_PATH}")
            logger.error("Please run generate_contacts() first to create the contacts file")
            return
        except json.JSONDecodeError:
            logger.error(f"Invalid JSON format in {CONTACTS_FILE_PATH}")
            return

        if contacts is None:
            logger.error("No contacts loaded from file")
            return

        # Create async tasks for adding contacts concurrently
        async def add_single_contact(contact_data: ContactData) -> dict | None:
            """Add a single contact and return the contact if successful, None if failed."""
            try:
                contact = {
                    "additional_attributes": {
                        "company_name": contact_data.company_name,
                        "country_code": "US",
                        "country": "United States",
                        "city": contact_data.city,
                        "state": contact_data.state,
                        "social_profiles": contact_data.social_profiles,
                    },
                    "availability_status": "offline",
                    "email": contact_data.email,
                    "name": contact_data.name,
                    "phone_number": contact_data.phone_number,
                    "blocked": False,
                    "identifier": None,
                    "thumbnail": "",
                    "custom_attributes": {"customer_since": contact_data.customer_since},
                    "contact_inboxes": [],
                }

                await client.add_contact(contact)
                return contact_data.model_dump()
            except Exception as e:
                logger.error(f"Error adding contact {contact_data.email}: {e}")
                return None

        # Run all add_contact calls concurrently
        logger.start(f"Adding {len(contacts)} contacts concurrently...")
        results = await asyncio.gather(*[add_single_contact(contact_data) for contact_data in contacts], return_exceptions=True)

        # Filter out None results and exceptions to get successfully added contacts
        added_contacts = [result for result in results if result is not None and not isinstance(result, Exception)]

        logger.succeed(f"Successfully added {len(added_contacts)} out of {len(contacts)} contacts")


async def insert_contacts(number_of_contacts: int):
    """Legacy function - generates contacts and seeds them into Chatwoot."""
    await generate_contacts(number_of_contacts)
    await seed_contacts()


async def delete_contacts():
    async with ChatwootClient() as client:
        contacts = await client.list_contacts()
        while len(contacts) > 0:
            for contact in contacts:
                try:
                    await client.delete_contact(contact["id"])
                    logger.info(f"Deleted contact: {contact['id']}")
                except Exception as e:
                    logger.error(f"Error deleting contact: {e}")
            contacts = await client.list_contacts()


async def get_all_contacts(max_contacts: int | None = None):
    async with ChatwootClient() as client:
        all_contacts = []
        page = 1
        contacts = await client.list_contacts(page)
        all_contacts.extend(contacts)
        count = 0
        while (max_contacts is None or len(all_contacts) < max_contacts) and count < 999:
            count += 1
            all_contacts.extend(contacts)
            page += 1
            contacts = await client.list_contacts(page)
        return all_contacts
