import random

from faker import Faker

from apps.odoosales.config.constants import BANK_NAMES, COMPANY_INDUSTRIES, CONTACT_TAGS, CrmModelName, ResModelName
from apps.odoosales.config.settings import settings
from apps.odoosales.utils.odoo import OdooClient
from common.load_json import load_json
from common.logger import logger


faker = Faker()


async def insert_industries():
    logger.start("Inserting industries...")
    async with OdooClient() as client:
        try:
            # Fetch existing industries to avoid duplicates
            existing_industries = await client.search_read(ResModelName.RES_INDUSTRY.value, [], ["name"])
            existing_industries_set = {industry["name"] for industry in existing_industries}

            # Prepare new industries to insert
            new_industries = [{"name": industry} for industry in COMPANY_INDUSTRIES if industry not in existing_industries_set]

            if new_industries:
                await client.create(ResModelName.RES_INDUSTRY.value, [new_industries])
                logger.succeed(f"Inserted {len(new_industries)} new industries.")
            else:
                logger.succeed("No new industries to insert.")

        except Exception as e:
            raise ValueError(f"Error inserting industries: {e}")


async def insert_contact_tags():
    logger.start("Inserting contact tags...")
    async with OdooClient() as client:
        try:
            # Fetch existing tags to avoid duplicates
            existing_tags = await client.search_read(ResModelName.RES_CATEGORY.value, [], ["name"])
            existing_tags_set = {tag["name"] for tag in existing_tags}

            # Prepare new tags to insert
            new_tags = [{"name": tag} for tag in CONTACT_TAGS if tag not in existing_tags_set]

            if new_tags:
                await client.create(ResModelName.RES_CATEGORY.value, [new_tags])
                logger.succeed(f"Inserted {len(new_tags)} new contact tags.")
            else:
                logger.succeed("No new contact tags to insert.")

        except Exception as e:
            raise ValueError(f"Error inserting contact tags: {e}")


async def insert_banks():
    logger.start("Inserting banks...")
    async with OdooClient() as client:
        try:
            # Fetch existing banks to avoid duplicates
            existing_banks = await client.search_read(ResModelName.RES_BANK.value, [], ["name"])
            existing_banks_set = {bank["name"] for bank in existing_banks}

            new_banks = [{"name": bank} for bank in BANK_NAMES if bank not in existing_banks_set]

            if new_banks:
                await client.create(ResModelName.RES_BANK.value, [new_banks])
                logger.succeed(f"Inserted {len(new_banks)} new banks.")
            else:
                logger.succeed("No new banks to insert.")

        except Exception as e:
            raise ValueError(f"Error inserting banks: {e}")


async def insert_contacts():
    logger.start("Inserting contacts...")
    async with OdooClient() as client:
        try:
            states = await client.search_read(
                ResModelName.RES_COUNTRY_STATE.value,
                [("country_id", "=", 233)],
                ["id", "name"],
            )
            states_map = {state["name"]: state["id"] for state in states}

            industries = await client.search_read(ResModelName.RES_INDUSTRY.value, [], ["id", "name"])
            industries_map = {industry["name"]: industry["id"] for industry in industries}

            sale_people = await client.search_read(
                CrmModelName.CRM_TEAM_MEMBER.value,
                [],
                ["id", "user_id"],
            )

            # Filter out sale people with None user_id and ensure we have valid users
            valid_sale_people = [sp for sp in sale_people if sp.get("user_id")]
            if not valid_sale_people:
                # Fallback to admin user (ID 1) if no valid sale people found
                valid_sale_people = [{"user_id": [1, "Administrator"]}]

            titles = await client.search_read("res.partner.title", [], ["id", "name"])
            titles_map = {title["name"]: title["id"] for title in titles}

            categories = await client.search_read(
                ResModelName.RES_CATEGORY.value,
                [],
                ["id", "name"],
            )
            categories_map = {category["name"]: category["id"] for category in categories}

            banks = await client.search_read(ResModelName.RES_BANK.value, [], ["id"])

            companies = load_json(settings.DATA_PATH.joinpath("companies.json"))
            individuals = load_json(settings.DATA_PATH.joinpath("individuals.json"))

            company_records = []
            for company in companies:
                vals = {
                    "name": company["name"],
                    "is_company": True,
                    "company_type": "company",
                    "color": random.randint(1, 11),  # Random color index
                    "email": company["email"],
                    "phone": faker.numerify("+1 (###) ###-####"),
                    "mobile": faker.numerify("+1 (###) ###-####"),
                    "street": company["primary_address"]["street"],
                    "street2": faker.secondary_address(),
                    "state_id": states_map[company["primary_address"]["state"]],
                    "city": company["primary_address"]["city"],
                    "zip": company["primary_address"]["zip_code"],
                    "country_id": 233,
                    "vat": company["vat"],
                    "website": company["website"],
                    "property_payment_term_id": 1,
                    "property_supplier_payment_term_id": 1,
                    "property_inbound_payment_method_line_id": 1,
                    "property_outbound_payment_method_line_id": 1,
                    "comment": company["note"],
                    "user_id": random.choice(valid_sale_people)["user_id"][0],
                    "industry_id": industries_map[company["industry"]],
                    "customer_rank": random.randint(1, 9999),
                    "invoice_sending_method": random.choice(["email", "manual", "snailmail"]),
                    "property_product_pricelist": 1,
                    "invoice_edi_format": random.choice(
                        [
                            "facturx",
                            "ubl_bis3",
                            "xrechnung",
                            "nlcius",
                            "ubl_a_nz",
                            "ubl_sg",
                        ]
                    ),
                }

                if categories_map.get(company["category"]):
                    vals["category_id"] = [categories_map[company["category"]]]

                company_records.append(vals)

            company_ids = await client.create("res.partner", [company_records])

            company_contact_records = []
            for company, company_id in zip(companies, company_ids, strict=False):
                if company.get("linked_contact"):
                    contact_data = {
                        "name": company["linked_contact"]["name"],
                        "title": titles_map.get(company["linked_contact"]["title"]),
                        "function": company["linked_contact"]["job_position"],
                        "email": company["linked_contact"]["email"],
                        "phone": faker.numerify("+1 (###) ###-####"),
                        "mobile": faker.numerify("+1 (###) ###-####"),
                        "comment": company["linked_contact"]["note"],
                        "type": "contact",
                        "parent_id": company_id,
                    }
                    company_contact_records.append(contact_data)

                if company.get("invoice_address"):
                    invoice_addr_data = {
                        "name": company["invoice_address"]["contact_name"],
                        "email": company["invoice_address"]["email"],
                        "phone": faker.numerify("+1 (###) ###-####"),
                        "mobile": faker.numerify("+1 (###) ###-####"),
                        "street": company["invoice_address"]["street"],
                        "street2": faker.secondary_address(),
                        "city": company["invoice_address"]["city"],
                        "state_id": states_map.get(company["invoice_address"]["state"]),
                        "zip": company["invoice_address"]["zip_code"],
                        "country_id": 233,
                        "comment": company["invoice_address"]["note"],
                        "type": "invoice",
                        "parent_id": company_id,
                    }
                    company_contact_records.append(invoice_addr_data)

                if company.get("delivery_address"):
                    delivery_addr_data = {
                        "name": company["delivery_address"]["contact_name"],
                        "email": company["delivery_address"]["email"],
                        "phone": faker.numerify("+1 (###) ###-####"),
                        "mobile": faker.numerify("+1 (###) ###-####"),
                        "street": company["delivery_address"]["street"],
                        "street2": faker.secondary_address(),
                        "city": company["delivery_address"]["city"],
                        "state_id": states_map.get(company["delivery_address"]["state"]),
                        "zip": company["delivery_address"]["zip_code"],
                        "country_id": 233,
                        "comment": company["delivery_address"]["note"],
                        "type": "delivery",
                        "parent_id": company_id,
                    }
                    company_contact_records.append(delivery_addr_data)

                if company.get("primary_bank_account"):
                    bank_data = {
                        "acc_number": company["primary_bank_account"]["account_number"],
                        "partner_id": company_id,
                        "bank_id": random.choice(banks)["id"],
                    }
                    await client.create(ResModelName.RES_PARTNER_BANK.value, [bank_data])
            await client.create("res.partner", [company_contact_records])

            logger.succeed(f"Inserted {len(companies)} companies.")

            logger.start(f"Inserting {len(individuals)} individuals...")

            individual_records = []
            for individual in individuals:
                vals = {
                    "name": individual["name"],
                    "is_company": False,
                    "function": individual["job_position"],
                    "color": random.randint(1, 11),  # Random color index
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
                    "vat": individual["vat"],
                    "website": individual["website"],
                    "property_payment_term_id": 1,
                    "property_supplier_payment_term_id": 1,
                    "property_inbound_payment_method_line_id": 1,
                    "property_outbound_payment_method_line_id": 1,
                    "comment": individual["note"],
                    "user_id": random.choice(valid_sale_people)["user_id"][0],
                    "customer_rank": random.randint(1, 9999),
                    "invoice_sending_method": random.choice(["email", "manual", "snailmail"]),
                    "property_product_pricelist": 1,
                    "invoice_edi_format": random.choice(
                        [
                            "facturx",
                            "ubl_bis3",
                            "xrechnung",
                            "nlcius",
                            "ubl_a_nz",
                            "ubl_sg",
                        ]
                    ),
                }

                if categories_map.get(individual["category"]):
                    vals["category_id"] = [categories_map[individual["category"]]]

                individual_records.append(vals)

            individual_ids = await client.create("res.partner", [individual_records])

            individual_contact_records = []
            for individual, individual_id in zip(individuals, individual_ids, strict=False):
                if individual:
                    contact_data = {
                        "name": individual["name"],
                        "title": titles_map.get(individual["title"]),
                        "function": individual.get("job_position"),
                        "email": individual["email"],
                        "phone": individual["phone"],
                        "mobile": individual["mobile"],
                        "type": "contact",
                        "parent_id": individual_id,
                    }
                    individual_contact_records.append(contact_data)

                if individual.get("primary_address"):
                    invoice_addr_data = {
                        "name": individual["name"],
                        "email": individual["email"],
                        "phone": individual["phone"],
                        "mobile": individual["mobile"],
                        "street": individual["primary_address"]["street"],
                        "street2": faker.secondary_address(),
                        "city": individual["primary_address"]["city"],
                        "state_id": states_map.get(individual["primary_address"]["state"]),
                        "zip": individual["primary_address"]["zip_code"],
                        "country_id": 233,
                        "type": "invoice",
                        "parent_id": individual_id,
                    }
                    delivery_addr_data = {
                        "name": individual["name"],
                        "email": individual["email"],
                        "phone": individual["phone"],
                        "mobile": individual["mobile"],
                        "street": individual["primary_address"]["street"],
                        "street2": faker.secondary_address(),
                        "city": individual["primary_address"]["city"],
                        "state_id": states_map.get(individual["primary_address"]["state"]),
                        "zip": individual["primary_address"]["zip_code"],
                        "country_id": 233,
                        "type": "delivery",
                        "parent_id": individual_id,
                    }
                    individual_contact_records.extend([invoice_addr_data, delivery_addr_data])
                if individual.get("primary_bank_account"):
                    bank_data = {
                        "acc_number": individual["primary_bank_account"]["account_number"],
                        "partner_id": individual_id,
                        "bank_id": random.choice(banks)["id"],
                    }
                    await client.create(ResModelName.RES_PARTNER_BANK.value, [bank_data])
            await client.create("res.partner", [individual_contact_records])
            logger.succeed(f"Inserted {len(individuals)} individuals.")

        except Exception as e:
            raise ValueError(f"Error inserting contacts: {e}")
