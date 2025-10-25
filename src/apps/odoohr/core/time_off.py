"""Creates and manages employee time off requests."""

import random
from datetime import date, timedelta

from apps.odoohr.config.constants import HRModelName
from apps.odoohr.config.settings import settings
from apps.odoohr.utils.load_json import load_json
from apps.odoohr.utils.odoo import OdooClient
from common.logger import logger


async def insert_time_off(count=30):
    time_off_config = load_json(settings.DATA_PATH.joinpath("time_off.json"))

    leave_reasons = time_off_config.get("leaveReasons", [])

    logger.start(f"Inserting {count} time off records")
    async with OdooClient() as client:
        # Get all employees with their managers
        employees = await client.search_read(HRModelName.HR_EMPLOYEE.value, [], ["id", "name", "leave_manager_id"])
        if not employees:
            return

        # Get all time off types
        time_off_types = await client.search_read(HRModelName.HR_LEAVE_TYPE.value, [], ["id", "name"])
        if not time_off_types:
            return

        allowed_type_ids = [t["id"] for t in time_off_types]

        # Date range
        today = date.today()

        inserted_ids = []
        for idx in range(count):
            employee = employees[idx % len(employees)]
            # Only consider employees with a leave manager
            manager_id = None
            if employee.get("leave_manager_id"):
                manager_id = employee["leave_manager_id"][0] if isinstance(employee["leave_manager_id"], list) else employee["leave_manager_id"]
            if not manager_id:
                continue

            time_off_type_id = random.choice(allowed_type_ids)
            leave_start = today + timedelta(days=7)
            leave_end = leave_start

            description = random.choice(leave_reasons)

            vals = {
                "employee_id": employee["id"],
                "holiday_status_id": time_off_type_id,
                "request_date_from": leave_start.strftime("%Y-%m-%d"),
                "request_date_to": leave_end.strftime("%Y-%m-%d"),
                "name": description,
                "state": "confirm",  # 'To Approve' in Odoo
                "user_id": manager_id,
            }

            new_id = await client.create(HRModelName.HR_LEAVE.value, vals)
            inserted_ids.append(new_id)

        ids_to_diversify = inserted_ids[:count]
        random.shuffle(ids_to_diversify)
        approved = ids_to_diversify[8:18]
        refused = ids_to_diversify[18:25]
        cancelled = ids_to_diversify[25:30]
        for leave_id in approved:
            try:
                await client.execute_kw(HRModelName.HR_LEAVE.value, "action_approve", [[leave_id]])
                await client.execute_kw(HRModelName.HR_LEAVE.value, "action_validate", [[leave_id]])
            except Exception:
                continue
        for leave_id in refused:
            try:
                await client.execute_kw(HRModelName.HR_LEAVE.value, "action_refuse", [[leave_id]])
            except Exception:
                continue
        for leave_id in cancelled:
            try:
                await client.execute_kw(HRModelName.HR_LEAVE.value, "action_refuse", [[leave_id]])
                await client.execute_kw(HRModelName.HR_LEAVE.value, "action_cancel", [[leave_id]])
            except Exception:
                continue
    logger.succeed(f"Inserted {len(inserted_ids)} time off records")


async def delete_time_off():
    async with OdooClient() as client:
        time_offs = await client.search_read(
            HRModelName.HR_LEAVE.value,
            [],
            ["id", "state"],
        )
        if not time_offs:
            return

        # Reset any non-draft/confirm records to draft
        refused_ids = [t["id"] for t in time_offs if t["state"] == "refuse"]
        cancelled_ids = [t["id"] for t in time_offs if t["state"] == "cancel"]
        non_confirmed_ids = [t["id"] for t in time_offs if t["state"] != "confirm"]
        if refused_ids or cancelled_ids:
            for leave_id in refused_ids + cancelled_ids:
                await client.execute_kw(HRModelName.HR_LEAVE.value, "action_reset_confirm", [[leave_id]])
        if non_confirmed_ids:
            for leave_id in non_confirmed_ids:
                await client.execute_kw(HRModelName.HR_LEAVE.value, "action_refuse", [[leave_id]])
                await client.execute_kw(HRModelName.HR_LEAVE.value, "action_reset_confirm", [[leave_id]])
        # Now delete all time off records
        all_ids = [t["id"] for t in time_offs]
        await client.unlink(HRModelName.HR_LEAVE.value, all_ids)
