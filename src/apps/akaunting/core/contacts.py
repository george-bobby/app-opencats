import asyncio

from faker import Faker

from apps.akaunting.models.contacts import ContactType
from apps.akaunting.utils import api, faker
from common.logger import logger


async def create_fake_contact(contact_type: ContactType):
    """
    Create a fake customer using Faker and add it to Akaunting via API
    """
    # Generate fake customer data
    company_info = faker.company_with_email()

    # Select a random country and set the locale for address generation
    country_locale_map = {
        "United States": "en_US",
        "United Kingdom": "en_GB",
        "Canada": "en_CA",
        "Australia": "en_AU",
        "Germany": "de_DE",
        "France": "fr_FR",
        "Spain": "es_ES",
        "Italy": "it_IT",
    }

    # Randomly select a country and create a localized faker
    country = faker.random_element(list(country_locale_map.keys()))
    locale_faker = Faker(country_locale_map[country])

    # Generate location-specific address data
    customer_data = {
        "name": company_info["name"],
        "email": company_info["email"],
        "tax_number": faker.numerify(text="##########"),
        "currency_code": "USD",
        "phone": faker.custom_phone_number(),
        "website": company_info["website"],
        "enabled": True,
        "reference": faker.numerify(text="REF####"),
        "type": contact_type,
        "address": locale_faker.street_address(),
        "city": locale_faker.city(),
        "post_code": locale_faker.postcode(),
        "country": country,
    }

    # Add customer to Akaunting
    try:
        await api.add_contact(**customer_data)
        logger.info(f"Created {contact_type} {customer_data['name']}")
        await asyncio.sleep(1)
    except Exception as e:
        logger.error(e)


async def create_customers(number: int = 1):
    """
    Create fake customers using Faker and add it to Akaunting via API
    """
    await api.refresh_session()
    for _ in range(number):
        await create_fake_contact("customer")


async def create_vendors(number: int = 1):
    """
    Create fake vendors using Faker and add it to Akaunting via API
    """
    for _ in range(number):
        await create_fake_contact("vendor")


async def delete_generated_contacts():
    try:
        contacts = [
            *await api.list_contacts(search_type="customer"),
            *await api.list_contacts(search_type="vendor"),
        ]

        for contact in contacts:
            logger.info(contact)
            if contact.created_from == "core::api":
                try:
                    await api.delete_contact(str(contact.id))
                except Exception as e:
                    logger.warning(e)

    finally:
        await api.close()
