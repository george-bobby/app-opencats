"""Manages HR leave accrual plans and milestones."""

from apps.odoohr.config.constants import HRModelName
from apps.odoohr.config.settings import settings
from apps.odoohr.utils.load_json import load_json
from apps.odoohr.utils.odoo import OdooClient
from common.logger import logger


async def insert_accrual_plans():
    accrual_plans = load_json(settings.DATA_PATH.joinpath("accrual_plans.json"))

    logger.start(f"Inserting {len(accrual_plans)} accrual plans")
    async with OdooClient() as client:
        for plan in accrual_plans:
            new_accrual_plan_id = await client.create(
                HRModelName.HR_LEAVE_ACCRUAL_PLAN.value,
                {
                    "name": plan["name"],
                    "accrued_gain_time": "end",
                    "carryover_date": "year_start",
                    "is_based_on_worked_time": False,
                },
            )
            if not new_accrual_plan_id:
                raise ValueError("Failed to create accrual plan")

            for milestone in plan["milestones"]:
                await client.create(
                    HRModelName.HR_LEAVE_ACCRUAL_LEVEL.value,
                    {
                        "accrual_plan_id": new_accrual_plan_id,
                        **milestone,
                    },
                )
    logger.succeed(f"Inserted {len(accrual_plans)} accrual plans")
