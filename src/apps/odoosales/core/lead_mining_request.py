import random

from apps.odoosales.config.settings import settings
from apps.odoosales.utils.odoo import OdooClient
from common.load_json import load_json
from common.logger import logger


async def get_records_by_names(client, model, field_name, names, fields_to_read=None):
    """Fetches records by a list of names."""
    if fields_to_read is None:
        fields_to_read = ["id"]
    if not names:
        return []
    records = await client.search_read(model, [(field_name, "in", names)], fields_to_read)
    return records


async def get_record_by_name(client, model, name, fields_to_read=None):
    """Fetches a single record by name."""
    if fields_to_read is None:
        fields_to_read = ["id"]
    if not name:
        return None
    record = await client.search_read(model, [("name", "=", name)], fields_to_read)
    return record


async def insert_lead_mining_requests():
    lead_mining_requests = load_json(settings.DATA_PATH.joinpath("lead_mining_requests.json"))
    logger.start(f"Inserting {len(lead_mining_requests)} lead mining requests...")
    async with OdooClient() as client:
        try:
            # Fetch all necessary data in advance
            all_country_names = list({c for req in lead_mining_requests for c in req["country_names"]})
            all_industry_names = list({i for req in lead_mining_requests for i in req["industry_names"]})
            all_team_names = list({req["sales_team_name"] for req in lead_mining_requests})
            all_salesperson_names = list({req["salesperson_name"] for req in lead_mining_requests})
            all_tag_names = list({t for req in lead_mining_requests for t in req["tag_names"]})

            countries = {
                c["name"]: c["id"]
                for c in await get_records_by_names(
                    client,
                    "res.country",
                    "name",
                    all_country_names,
                    fields_to_read=["id", "name"],
                )
            }

            available_iap_industries_records = await client.search_read("crm.iap.lead.industry", [], ["id", "name"])
            iap_industry_ids_map = {ind["name"]: ind["id"] for ind in available_iap_industries_records}

            for industry_name in all_industry_names:
                if industry_name not in iap_industry_ids_map:
                    print(
                        f"Warning: Industry '{industry_name}' from your data is not found in Odoo's crm.iap.lead.industry list. "
                        f"This industry will be skipped for requests that use it. "
                        f"Available IAP industries: {[r['name'] for r in available_iap_industries_records]}"
                    )

            sales_teams = {
                t["name"]: t["id"]
                for t in await get_records_by_names(
                    client,
                    "crm.team",
                    "name",
                    all_team_names,
                    fields_to_read=["id", "name"],
                )
            }
            # For users (salespersons), Odoo's 'name' field is often what you see in UI.
            salespersons = {
                sp["name"]: sp["id"]
                for sp in await get_records_by_names(
                    client,
                    "res.users",
                    "name",
                    all_salesperson_names,
                    fields_to_read=["id", "name"],
                )
            }
            tags = {
                t["name"]: t["id"]
                for t in await get_records_by_names(
                    client,
                    "crm.tag",
                    "name",
                    all_tag_names,
                    fields_to_read=["id", "name"],
                )
            }

            created_count = 0
            for req_data in lead_mining_requests:
                logger.text = f"Processing Lead Mining Request: {req_data['name_prefix']}"

                country_ids = [countries[name] for name in req_data["country_names"] if name in countries]
                # Use the mapped crm.iap.lead.industry IDs
                iap_industry_ids = [iap_industry_ids_map[name] for name in req_data["industry_names"] if name in iap_industry_ids_map]
                team_id = sales_teams.get(req_data["sales_team_name"])
                salesperson_id = salespersons.get(req_data["salesperson_name"])
                tag_ids = [tags[name] for name in req_data["tag_names"] if name in tags]

                # Construct a unique name for the mining request if needed, or let Odoo handle it.
                # Odoo's crm.iap.lead.mining.request usually auto-generates a name.
                # We will set 'name' for clarity, but it might be overwritten or used differently by Odoo.
                request_name = f"{req_data['name_prefix']} - {random.randint(1000, 9999)}"

                # Check if a similar request already exists to avoid duplicates (optional, based on specific criteria)
                # For this example, we'll create new ones.
                # existing_request = await client.search_read("crm.iap.lead.mining.request", [("name", "=", request_name)], ["id"])
                # if existing_request:
                #     print(f"Lead Mining Request '{request_name}' already exists. Skipping.")
                #     continue

                payload = {
                    "name": request_name,  # Odoo might auto-generate this based on criteria
                    "lead_type": "lead",  # 'lead' or 'opportunity'
                    "search_type": "companies",  # 'companies' or 'people'
                    "lead_count": req_data["leads_count"],
                    "country_ids": [(6, 0, country_ids)] if country_ids else False,
                    "industry_ids": [(6, 0, iap_industry_ids)] if iap_industry_ids else False,  # Use IAP industry IDs
                    "team_id": team_id or False,
                    "user_id": salesperson_id or False,  # Salesperson
                    "tag_ids": [(6, 0, tag_ids)] if tag_ids else False,
                    # 'filter_on_size': False, # Example: Do not filter by company size
                    # 'company_size_min': 0,
                    # 'company_size_max': 0,
                    # 'preferred_role_id': False, # If searching for people, specify role
                    # 'contact_filter_type': 'email_phone', # 'email_only', 'phone_only', 'email_phone'
                }

                # Remove keys with False values, as Odoo might not like them for m2m fields if empty
                payload = {k: v for k, v in payload.items() if v is not False}

                try:
                    await client.create("crm.iap.lead.mining.request", payload)
                    created_count += 1
                except Exception:
                    continue

            if created_count > 0:
                logger.succeed(f"Successfully created {created_count} lead mining requests.")
            else:
                logger.info("No new lead mining requests were created. Check warnings if any.")

        except Exception as e:
            logger.fail(f"An error occurred during lead mining request insertion: {e}")
