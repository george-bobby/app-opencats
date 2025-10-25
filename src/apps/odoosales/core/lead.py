import random
from collections import OrderedDict

from faker import Faker

from apps.odoosales.config.constants import CrmModelName, MailModelName, ResModelName
from apps.odoosales.config.settings import settings
from apps.odoosales.utils.odoo import OdooClient
from common.load_json import load_json
from common.logger import logger


faker = Faker()


stages = ["New", "Qualified", "Proposition", "Won", "Lost"]


async def insert_lost_stage():
    logger.start("Inserting lost stage...")
    async with OdooClient() as client:
        await client.create(
            "crm.stage",
            {
                "name": "Lost",
                "fold": False,
                "is_won": False,
                "sequence": 100,
            },
        )
    logger.succeed("Inserted Lost stage")


async def insert_leads():
    pre_leads = {}
    leads = load_json(settings.DATA_PATH.joinpath("leads.json"))

    logger.start("Fetching prerequisites for leads")
    async with OdooClient() as client:
        pre_leads["companies"] = await client.search_read(
            "res.partner",
            [("is_company", "=", True), ("customer_rank", ">", 0)],
            ["id", "name", "email", "phone"],
        )
        pre_leads["teams"] = await client.search_read(
            "crm.team",
            [
                ("use_leads", "=", True),
                ("use_opportunities", "=", True),
            ],
            ["id"],
        )

        pre_leads["contacts"] = await client.search_read(
            "res.partner",
            [("is_company", "=", False), ("parent_id", "!=", False)],
            ["id", "name", "email", "phone", "parent_id"],
        )
        pre_leads["users"] = await client.search_read("res.users", [("share", "=", False)], ["id"], limit=50)
        pre_leads["tags"] = await client.search_read("crm.tag", [], ["id"])

        lead_records = []
        for lead in leads:
            company = random.choice(pre_leads["companies"]) if pre_leads["companies"] else None

            # Try to find a contact associated with the company, or pick any contact
            contact = None
            if company and pre_leads["contacts"]:
                company_contacts = [c for c in pre_leads["contacts"] if c.get("parent_id") and c["parent_id"][0] == company["id"]]
                if company_contacts:
                    contact = random.choice(company_contacts)
            if not contact and pre_leads["contacts"]:  # Fallback to any contact
                contact = random.choice(pre_leads["contacts"])

            opportunity_name = f"{faker.bs().capitalize()} for {company['name']}" if company else f"{faker.bs().capitalize()}"

            contact_name_val = contact["name"] if contact else faker.name()
            email_from_val = contact["email"] if contact and contact.get("email") else faker.email()
            phone_val = contact["phone"] if contact and contact.get("phone") else faker.phone_number()

            vals = {
                "name": lead.get("name", opportunity_name),
                "description": lead["description"] if "description" in lead else faker.text(),
                "priority": random.choice(["0", "1", "2", "3"]),
                "type": "lead",
                "partner_id": company["id"] if company else None,
                "contact_name": contact_name_val,
                "email_from": email_from_val,
                "phone": phone_val,
                "color": random.randint(1, 11),  # Random color index
                "tag_ids": [random.choice(pre_leads["tags"])["id"]] if pre_leads["tags"] else [],
                "expected_revenue": random.randint(5000, 100000),
                "recurring_revenue": 0,  # As per prompt
                "recurring_plan": pre_leads.get("monthly_plan_id"),
                "team_id": random.choice(pre_leads["teams"])["id"] if pre_leads["teams"] else None,
                "user_id": random.choice(pre_leads["users"])["id"] if pre_leads["users"] else None,
            }
            # Remove None values for optional fields to avoid issues
            vals = {k: v for k, v in vals.items() if v is not None}
            lead_records.append(vals)
        await client.create(CrmModelName.CRM_LEAD.value, [lead_records])
        logger.succeed(f"Inserted {len(lead_records)} leads")


async def convert_to_opportunity():
    logger.start("Converting leads to opportunities...")
    async with OdooClient() as client:
        leads = await client.search_read(
            CrmModelName.CRM_LEAD.value,
            [("type", "=", "lead")],
            ["id", "name"],
        )
        res_model = await client.search_read(
            "ir.model",
            [("model", "=", CrmModelName.CRM_LEAD.value)],
            ["id"],
        )
        stages_data = await client.search_read(CrmModelName.CRM_STAGE.value, [("name", "in", stages)], ["id", "name"])
        users = await client.search_read(
            ResModelName.RES_USERS.value,
            [("active", "=", True)],
            ["id"],
        )
        activity_types = await client.search_read(
            MailModelName.MAIL_ACTIVITY_TYPE.value,
            [],
            ["id", "name"],
        )
        activity_type_lookup = {activity_type["name"]: activity_type["id"] for activity_type in activity_types}

        lost_reasons = await client.search_read("crm.lost.reason", [], ["id"])

        if not leads:
            logger.fail("No opportunities found to convert")
            return

        leads = leads[: int(len(leads) * 0.5)]

        for idx, lead in enumerate(leads):
            stage = faker.random_element(OrderedDict(new=0.2, qualified=0.2, proposition=0.2, won=0.2, lost=0.2))

            lead_to_opportunity_id = await client.create(
                "crm.lead2opportunity.partner",
                {
                    "lead_id": lead["id"],
                    "name": "convert",
                    "action": "exist",
                    "force_assignment": True,
                },
            )

            await client.execute_kw(
                "crm.lead2opportunity.partner",
                "action_apply",
                [lead_to_opportunity_id],
                {
                    "context": {
                        "active_id": lead["id"],
                        "active_ids": [lead["id"]],
                    }
                },
            )

            lead_data = {}

            if idx <= len(leads) // 2:
                lead_data["user_id"] = 2

            if stage == "new":
                lead_data["stage_id"] = next((s["id"] for s in stages_data if s["name"] == "New"), None)
            elif stage == "qualified":
                lead_data["stage_id"] = next((s["id"] for s in stages_data if s["name"] == "Qualified"), None)
            elif stage == "proposition":
                lead_data["stage_id"] = next((s["id"] for s in stages_data if s["name"] == "Proposition"), None)
            elif stage == "won":
                await client.execute_kw(
                    CrmModelName.CRM_LEAD.value,
                    "action_set_won_rainbowman",
                    [lead["id"]],
                )
            elif stage == "lost":
                lost_id = await client.create(
                    "crm.lead.lost",
                    {
                        "lead_ids": [lead["id"]],
                        "lost_reason_id": random.choice(lost_reasons)["id"],
                    },
                )
                await client.execute_kw("crm.lead.lost", "action_lost_reason_apply", [lost_id])
                lead_data["stage_id"] = next((s["id"] for s in stages_data if s["name"] == "Lost"), None)

            if stage != "lost":
                activity_id = await client.create(
                    MailModelName.MAIL_ACTIVITY.value,
                    {
                        "res_id": lead["id"],
                        "activity_type_id": activity_type_lookup.get(random.choice(["Email", "Demo", "Follow-up", "Upload Document", "Contract Review"])),
                        "res_model": "crm.lead",
                        "res_model_id": res_model[0]["id"] if res_model else False,
                        "date_deadline": faker.date_between(start_date="-30d", end_date="+30d").strftime("%Y-%m-%d"),
                        "user_id": random.choice(users)["id"] if users else None,
                    },
                )

                lead_data["activity_ids"] = [(4, activity_id)]

            await client.write(CrmModelName.CRM_LEAD.value, lead["id"], lead_data)

        logger.succeed(f"Converted {len(leads)} leads to opportunities")


async def mark_activities_done():
    async with OdooClient() as client:
        activities = await client.search_read(
            "mail.activity",
            [],
            ["id", "date_deadline"],
        )
        if not activities:
            logger.fail("No planned activities found")
            return

        for activity in activities[: int(len(activities) // 1.5)]:
            await client.execute_kw("mail.activity", "action_feedback", [activity["id"]])
            # await client.write(
            #     "mail.activity",
            #     activity["id"],
            #     {
            #         "date_done": (datetime.datetime.strptime(activity["date_deadline"], "%Y-%m-%d").date() + datetime.timedelta(days=random.randint(3, 5))).strftime("%Y-%m-%d"),
            #     },
            # )

        logger.succeed(f"Marked {len(activities)} activities as done")
