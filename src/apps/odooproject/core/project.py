import contextlib
import datetime
import itertools
import random

from apps.odooproject.config.constants import MailModelName, ProjectModelName, ResModelName
from apps.odooproject.config.settings import settings
from apps.odooproject.utils.odoo import OdooClient
from common.load_json import load_json
from common.logger import logger


async def unfold_all_project_stages():
    async with OdooClient() as client:
        stages = await client.search_read(ProjectModelName.PROJECT_PROJECT_STAGE.value, [], fields=["id"])

        for stage in stages:
            await client.write(ProjectModelName.PROJECT_PROJECT_STAGE.value, stage["id"], {"fold": False})


async def insert_project_tags():
    projects: list[dict] = load_json(settings.DATA_PATH.joinpath("projects.json"))
    tasks: list[dict] = load_json(settings.DATA_PATH.joinpath("tasks.json"))

    all_taggable_items = itertools.chain(
        projects,
        tasks,
        *(t.get("children", []) or [] for t in tasks),
        *(t.get("blockers", []) or [] for t in tasks),
    )

    tags = {tag for item in all_taggable_items for tag in item.get("tags", [])}

    logger.start(f"Inserting {len(tags)} project tags into Odoo...")
    async with OdooClient() as client:
        with contextlib.suppress(Exception):
            existing_tags = await client.search_read(ProjectModelName.PROJECT_TAGS.value, [], fields=["id"])
            if existing_tags:
                await client.unlink(ProjectModelName.PROJECT_TAGS.value, [tag["id"] for tag in existing_tags])

        tag_records = []
        for tag in tags:
            tag_data = {
                "name": tag,
                "color": random.randint(1, 11),  # Default color if not specified
            }
            tag_records.append(tag_data)

        await client.create(ProjectModelName.PROJECT_TAGS.value, [tag_records])
        logger.succeed(f"Inserted {len(tags)} project tags into Odoo.")


async def insert_projects():
    projects = load_json(settings.DATA_PATH.joinpath("projects.json"))

    logger.start(f"Inserting {len(projects)} projects into Odoo...")

    async with OdooClient() as client:
        # Fetch all necessary reference data from Odoo
        users = await client.search_read(ResModelName.RES_USERS.value, [("active", "=", True)], fields=["id", "name"])
        partners = await client.search_read(ResModelName.RES_PARTNER.value, fields=["id", "name"])
        tags = await client.search_read(ProjectModelName.PROJECT_TAGS.value, fields=["id", "name"])
        stages = await client.search_read(ProjectModelName.PROJECT_PROJECT_STAGE.value, fields=["id", "name"])
        activity_types = await client.search_read(MailModelName.MAIL_ACTIVITY_TYPE.value, fields=["id", "name"])
        project_res_model = await client.search_read("ir.model", [("model", "=", "project.project")], ["id"])

        # Create lookup dictionaries for easy mapping
        partner_lookup = {partner["name"]: partner["id"] for partner in partners}
        tag_lookup = {tag["name"]: tag["id"] for tag in tags}
        project_records = []

        for project in projects:
            manager_id = random.choice(users)["id"]

            customer_id = None
            if project.get("customer"):
                customer_id = partner_lookup.get(project["customer"])
                if not customer_id:
                    customer_id = await client.create(
                        ResModelName.RES_PARTNER.value,
                        {
                            "name": project["customer"],
                            "is_company": True,
                            "company_type": "company",
                        },
                    )

            # Map tag names to IDs
            tag_ids = []
            for tag_name in project["tags"]:
                tag_id = tag_lookup.get(tag_name)
                if tag_id:
                    tag_ids.append(tag_id)

            stage = random.choice(stages)

            # Create the project record
            project_record = {
                "name": project["name"],
                "user_id": manager_id,
                "partner_id": customer_id if customer_id else False,
                "tag_ids": [(6, 0, tag_ids)] if tag_ids else False,
                "date_start": project["date_start"],
                "date": project["date_end"],
                "description": project["description"],
                "stage_id": stage["id"],
            }

            if stage["name"] == "Done":
                project_record["last_update_status"] = "done"
            elif stage["name"] == "Cancelled":
                project_record["last_update_status"] = random.choice(["at_risk", "off_track"])
            else:
                project_record["last_update_status"] = random.choice(["on_track", "on_hold", "to_define"])

            project_records.append(project_record)

        if project_records:
            project_ids = await client.create(ProjectModelName.PROJECT_PROJECT.value, [project_records])

            for project_id in project_ids:
                activity_id = await client.create(
                    MailModelName.MAIL_ACTIVITY.value,
                    {
                        "res_id": project_id,
                        "activity_type_id": random.choice(activity_types)["id"],
                        "res_model": "project.project",
                        "res_model_id": project_res_model[0]["id"],
                        "date_deadline": (datetime.date.today() + datetime.timedelta(days=random.randint(3, 15))).strftime("%Y-%m-%d"),
                    },
                )
                await client.write(
                    ProjectModelName.PROJECT_PROJECT.value,
                    project_id,
                    {
                        "activity_ids": [(4, activity_id)],
                    },
                )

            logger.succeed(f"Inserted {len(project_records)} projects successfully.")
        else:
            logger.fail("No projects were created due to missing reference data.")
