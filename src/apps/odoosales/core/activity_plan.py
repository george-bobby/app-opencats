from apps.odoosales.config.constants import IrModelName, MailModelName
from apps.odoosales.config.settings import settings
from apps.odoosales.utils.odoo import OdooClient
from common.load_json import load_json
from common.logger import logger


async def insert_activity_plans():
    activity_plans = load_json(settings.DATA_PATH.joinpath("activity_plans.json"))

    logger.start(f"Inserting {len(activity_plans)} activity plans...")
    async with OdooClient() as client:
        res_model = await client.search_read(
            IrModelName.IR_MODEL.value,
            [("model", "=", "sale.order")],
            ["id"],
        )
        for plan in activity_plans:
            plan_id = await client.create(
                MailModelName.MAIL_ACTIVITY_PLAN.value,
                {
                    "name": plan["name"],
                    "res_model_id": res_model[0]["id"] if res_model else False,
                    "res_model": "sale.order",
                },
            )
            for line in plan["activity_plan_lines"]:
                activity_type = await client.search_read(
                    MailModelName.MAIL_ACTIVITY_TYPE.value,
                    [("name", "=", line["activity_type_name"])],
                    ["id"],
                    limit=1,
                )
                if not activity_type:
                    logger.fail(f"Activity type '{line['activity_type_name']}' not found.")
                    continue
                await client.create(
                    MailModelName.MAIL_ACTIVITY_PLAN_TEMPLATE.value,
                    {
                        "activity_type_id": activity_type[0]["id"] if activity_type else False,
                        "summary": line["summary"],
                        "delay_count": line["delay_count"],
                        "delay_unit": "days",
                        "plan_id": plan_id,
                    },
                )
        logger.succeed(f"Inserted {len(activity_plans)} activity plans successfully.")
