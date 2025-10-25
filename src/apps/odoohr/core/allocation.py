"""Creates time off allocations for employees."""

import random
from datetime import date, timedelta

from apps.odoohr.config.constants import HRModelName
from apps.odoohr.config.settings import settings
from apps.odoohr.utils.load_json import load_json
from apps.odoohr.utils.odoo import OdooClient
from common.logger import logger


async def insert_time_off_allocations():
    time_off_config = load_json(settings.DATA_PATH.joinpath("time_off.json"))
    reasons = time_off_config.get("reasons", [])

    logger.start("Inserting time off allocations")
    async with OdooClient() as client:
        # Fetch employees
        employees = await client.search_read(HRModelName.HR_EMPLOYEE.value, [], ["id", "name"])
        if not employees:
            return
        # Fetch time off types
        leave_types = await client.search_read(HRModelName.HR_LEAVE_TYPE.value, [("requires_allocation", "=", "yes")], ["id", "name"])
        if not leave_types:
            return
        # Map leave type name to id
        leave_type_map = {lt["name"]: lt["id"] for lt in leave_types}

        accrual_plans = await client.search_read(HRModelName.HR_LEAVE_ACCRUAL_PLAN.value, [], ["id", "name"])

        inserted_ids = []
        allocations_to_create = []

        today = date.today() + timedelta(days=7)
        # For each employee, create one allocation for each type
        for employee in employees:
            for leave_type_name in leave_type_map:
                allocation_data = {
                    "employee_id": employee["id"],
                    "holiday_status_id": leave_type_map[leave_type_name],
                    "date_from": today.strftime("%Y-%m-%d"),
                    "date_to": (today + timedelta(days=365)).strftime("%Y-%m-%d"),
                    "allocation_type": random.choice(["regular", "accrual"]),
                    "notes": random.choice(reasons),
                    "state": "confirm",  # Set status to Approved
                }

                if allocation_data["allocation_type"] == "regular":
                    allocation_data["number_of_days"] = random.randint(12, 15)
                elif allocation_data["allocation_type"] == "accrual":
                    allocation_data["accrual_plan_id"] = random.choice(accrual_plans)["id"]

                allocations_to_create.append(allocation_data)

        async with OdooClient() as client:
            inserted_ids = await client.create(HRModelName.HR_LEAVE_ALLOCATION.value, [allocations_to_create])
            logger.succeed(f"Inserted {len(inserted_ids)} time off allocations")

            if not inserted_ids:
                return

            for leave_id in inserted_ids:
                await client.execute_kw(HRModelName.HR_LEAVE_ALLOCATION.value, "action_approve", [[leave_id]])
