from apps.odoosales.config.settings import settings
from apps.odoosales.utils.odoo import OdooClient
from common.load_json import load_json
from common.logger import logger


async def insert_activity_plans_crm():
    activity_plans = load_json(settings.DATA_PATH.joinpath("activity_plans_crm.json"))

    logger.start("Inserting activity plans...")
    async with OdooClient() as client:
        res_model = await client.search_read(
            "ir.model",
            [("model", "=", "crm.lead")],
            ["id"],
        )
        for plan in activity_plans:
            plan_id = await client.create(
                "mail.activity.plan",
                {
                    "name": plan["name"],
                    "res_model_id": res_model[0]["id"] if res_model else False,
                    "res_model": "crm.lead",
                },
            )
            for line in plan["activity_plan_lines"]:
                activity_type = await client.search_read(
                    "mail.activity.type",
                    [("name", "=", line["activity_type_name"])],
                    ["id"],
                    limit=1,
                )
                if not activity_type:
                    logger.fail(f"Activity type '{line['activity_type_name']}' not found.")
                    continue
                await client.create(
                    "mail.activity.plan.template",
                    {
                        "activity_type_id": activity_type[0]["id"] if activity_type else False,
                        "summary": line["summary"],
                        "delay_count": line["delay_count"],
                        "delay_unit": "days",
                        "plan_id": plan_id,
                    },
                )
        logger.succeed(f"Inserted {len(activity_plans)} activity plans")
