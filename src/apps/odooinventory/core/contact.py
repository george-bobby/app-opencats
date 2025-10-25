import random
from functools import partial

from faker import Faker

from apps.odooinventory.config.constants import COMPANY_INDUSTRIES, CONTACT_TAGS
from apps.odooinventory.config.settings import settings
from apps.odooinventory.utils.odoo import OdooClient
from common.load_json import load_json
from common.logger import logger
from common.threading import process_in_parallel


faker = Faker()


async def insert_industries():
    logger.start("Inserting industries...")
    async with OdooClient() as client:
        try:
            # Fetch existing industries to avoid duplicates
            existing_industries = await client.search_read("res.partner.industry", [], ["name"])
            existing_industries_set = {industry["name"] for industry in existing_industries}

            # Prepare new industries to insert
            new_industries = [{"name": industry} for industry in COMPANY_INDUSTRIES if industry not in existing_industries_set]

            if new_industries:
                await client.create("res.partner.industry", [new_industries])
                logger.succeed(f"Inserted {len(new_industries)} new industries.")

        except Exception as e:
            raise ValueError(f"Error inserting industries: {e}")


async def insert_contact_tags():
    logger.start("Inserting contact tags...")
    async with OdooClient() as client:
        try:
            # Fetch existing tags to avoid duplicates
            existing_tags = await client.search_read("res.partner.category", [], ["name"])
            existing_tags_set = {tag["name"] for tag in existing_tags}

            # Prepare new tags to insert
            new_tags = [{"name": tag} for tag in CONTACT_TAGS if tag not in existing_tags_set]

            if new_tags:
                await client.create("res.partner.category", [new_tags])
                logger.succeed(f"Inserted {len(new_tags)} new contact tags.")

        except Exception as e:
            raise ValueError(f"Error inserting contact tags: {e}")


async def _process_companies_chunk(
    companies_chunk,
    states_map,
    industries_map,
    titles_map,
    categories_map,
):
    async with OdooClient() as client:
        company_records = []
        for company in companies_chunk:
            vals = {
                "name": company["name"],
                "is_company": True,
                "company_type": "company",
                "color": random.randint(1, 11),
                "email": company["email"],
                "phone": faker.numerify("+1 (###) ###-####"),
                "mobile": faker.numerify("+1 (###) ###-####"),
                "street": company["primary_address"]["street"],
                "street2": faker.secondary_address(),
                "state_id": states_map[company["primary_address"]["state"]],
                "city": company["primary_address"]["city"],
                "zip": company["primary_address"]["zip_code"],
                "country_id": 233,
                "vat": faker.numerify("##-#######"),
                "website": company["website"],
                "category_id": [categories_map[company["category"]]] if company["category"] in categories_map else [],
                "comment": company["note"],
                "industry_id": industries_map.get(company["industry"]),
            }
            company_records.append(vals)

        try:
            company_ids = await client.create("res.partner", [company_records])
        except Exception as e:
            raise ValueError(f"Error inserting companies: {e}")

        company_contact_records = []
        for company, company_id in zip(companies_chunk, company_ids, strict=False):
            if not all(company.get(key) for key in ["linked_contact", "invoice_address", "delivery_address"]):
                continue

            user_id = await client.create(
                "res.users",
                {
                    "name": company["linked_contact"]["name"],
                    "login": company["linked_contact"]["email"],
                    "email": company["linked_contact"]["email"],
                    "password": faker.password(),
                },
            )
            contact_data = {
                "name": company["linked_contact"]["name"],
                "title": titles_map[company["linked_contact"]["title"]],
                "function": company["linked_contact"]["job_position"],
                "email": company["linked_contact"]["email"],
                "phone": faker.numerify("+1 (###) ###-####"),
                "mobile": faker.numerify("+1 (###) ###-####"),
                "comment": company["linked_contact"]["note"],
                "type": "contact",
                "user_id": user_id,
                "parent_id": company_id,
            }
            invoice_addr_data = {
                "name": company["invoice_address"]["contact_name"],
                "email": company["invoice_address"]["email"],
                "phone": faker.numerify("+1 (###) ###-####"),
                "mobile": faker.numerify("+1 (###) ###-####"),
                "street": company["invoice_address"]["street"],
                "street2": faker.secondary_address(),
                "city": company["invoice_address"]["city"],
                "state_id": states_map[company["invoice_address"]["state"]],
                "zip": company["invoice_address"]["zip_code"],
                "country_id": 233,
                "comment": company["invoice_address"]["note"],
                "type": "invoice",
                "parent_id": company_id,
            }
            delivery_addr_data = {
                "name": company["delivery_address"]["contact_name"],
                "email": company["delivery_address"]["email"],
                "phone": faker.numerify("+1 (###) ###-####"),
                "mobile": faker.numerify("+1 (###) ###-####"),
                "street": company["delivery_address"]["street"],
                "street2": faker.secondary_address(),
                "city": company["delivery_address"]["city"],
                "state_id": states_map[company["delivery_address"]["state"]],
                "zip": company["delivery_address"]["zip_code"],
                "country_id": 233,
                "comment": company["delivery_address"]["note"],
                "type": "delivery",
                "parent_id": company_id,
            }
            company_contact_records.extend([contact_data, invoice_addr_data, delivery_addr_data])
        try:
            await client.create("res.partner", [company_contact_records])
        except Exception as e:
            raise ValueError(f"Error inserting company contacts: {e}")


async def _process_individuals_chunk(
    individuals_chunk,
    states_map,
    titles_map,
    categories_map,
):
    async with OdooClient() as client:
        for individual in individuals_chunk:
            user_id = await client.create(
                "res.users",
                {
                    "name": individual["name"],
                    "login": individual["email"],
                    "email": individual["email"],
                    "password": faker.password(),
                },
            )
            parner_record = await client.search_read("res.partner", [("email", "=", individual["email"])], ["id"])
            vals = {
                "user_id": user_id,
                "name": individual["name"],
                "is_company": False,
                "function": individual["job_position"],
                "color": random.randint(1, 11),
                "company_type": "person",
                "email": individual["email"],
                "phone": individual["phone"],
                "mobile": individual["mobile"],
                "title": titles_map[individual["title"]],
                "street": individual["primary_address"]["street"],
                "street2": faker.secondary_address(),
                "state_id": states_map[individual["primary_address"]["state"]],
                "city": individual["primary_address"]["city"],
                "zip": individual["primary_address"]["zip_code"],
                "country_id": 233,
                "vat": faker.numerify("###-#######"),
                "website": individual["website"],
                "category_id": [categories_map[individual["category"]]] if individual["category"] else [],
                "comment": individual["note"],
            }

            try:
                await client.write("res.partner", parner_record[0]["id"], vals)
            except Exception as e:
                raise ValueError(f"Error inserting individuals: {e}")


async def insert_contacts():
    companies = load_json(settings.DATA_PATH.joinpath("companies.json"))
    individuals = load_json(settings.DATA_PATH.joinpath("individuals.json"))

    logger.start(f"Inserting {len(companies) + len(individuals)} contacts...")
    async with OdooClient() as client:
        states = await client.search_read(
            "res.country.state",
            [("country_id", "=", 233)],
            ["id", "name"],
        )
        if not states:
            raise ValueError("No states found for USA")
        states_map = {state["name"]: state["id"] for state in states}

        industries = await client.search_read("res.partner.industry", [], ["id", "name"])
        if not industries:
            raise ValueError("No industries found")
        industries_map = {industry["name"]: industry["id"] for industry in industries}

        titles = await client.search_read("res.partner.title", [], ["id", "name"])
        if not titles:
            raise ValueError("No titles found")
        titles_map = {title["name"]: title["id"] for title in titles}

        categories = await client.search_read(
            "res.partner.category",
            [],
            ["id", "name"],
        )
        if not categories:
            raise ValueError("No contact categories found")
        categories_map = {category["name"]: category["id"] for category in categories}

    # Create partial functions with the necessary mappings
    company_processor = partial(
        _process_companies_chunk,
        states_map=states_map,
        industries_map=industries_map,
        titles_map=titles_map,
        categories_map=categories_map,
    )
    individual_processor = partial(
        _process_individuals_chunk,
        states_map=states_map,
        titles_map=titles_map,
        categories_map=categories_map,
    )

    # Process companies and individuals in parallel
    await process_in_parallel(companies, company_processor)
    await process_in_parallel(individuals, individual_processor)

    logger.succeed(f"Successfully inserted {len(companies)} companies and {len(individuals)} individuals.")
