from apps.odooproject.config.constants import MailModelName
from apps.odooproject.config.settings import settings
from apps.odooproject.utils.odoo import OdooClient
from common.load_json import load_json
from common.logger import logger


async def insert_activity_plans():
    activity_plans = load_json(settings.DATA_PATH.joinpath("activity_plans.json"))

    logger.start(f"Inserting {len(activity_plans)} activity plans...")
    async with OdooClient() as client:
        res_model = await client.search_read(
            "ir.model",
            [],
            ["id", "model"],
        )
        res_model_lookup = {model["model"]: model["id"] for model in res_model}
        for plan in activity_plans:
            plan_id = await client.create(
                MailModelName.MAIL_ACTIVITY_PLAN.value,
                {
                    "name": plan["name"],
                    "res_model_id": res_model_lookup.get(plan["model"]),
                    "res_model": plan["model"],
                },
            )
            for line in plan["activity_lines"]:
                activity_type = await client.search_read(
                    MailModelName.MAIL_ACTIVITY_TYPE.value,
                    [("name", "=", line["activity_type"])],
                    ["id"],
                    limit=1,
                )
                if not activity_type:
                    logger.fail(f"Activity type '{line['activity_type']}' not found.")
                    continue
                await client.create(
                    MailModelName.MAIL_ACTIVITY_PLAN_TEMPLATE.value,
                    {
                        "activity_type_id": activity_type[0]["id"] if activity_type else False,
                        "summary": line["summary"],
                        "delay_count": line["interval"],
                        "delay_unit": line["delay_unit"],
                        "delay_from": line["trigger"],
                        "plan_id": plan_id,
                    },
                )
        logger.succeed(f"Inserted {len(activity_plans)} activity plans successfully.")
