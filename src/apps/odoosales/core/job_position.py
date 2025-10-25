import contextlib

from apps.odoosales.config.constants import HRModelName
from apps.odoosales.config.settings import settings
from apps.odoosales.utils.odoo import OdooClient
from common.load_json import load_json
from common.logger import logger


async def insert_job_positions():
    await delete_default_job_positions()

    job_positions = load_json(settings.DATA_PATH.joinpath("job_positions.json"))

    logger.start(f"Inserting {len(job_positions)} job positions")
    async with OdooClient() as client:
        departments = await client.search_read(HRModelName.HR_DEPARTMENT.value, [], ["id", "name"])
        department_map = {d["name"]: d["id"] for d in departments}

        contract_type = await client.search_read(HRModelName.HR_CONTRACT_TYPE.value, [], ["id", "name"])
        contract_type_map = {ct["name"]: ct["id"] for ct in contract_type}

        job_positions_records = []
        for job in job_positions:
            dept_id = department_map.get(job["department"])

            data = {
                "name": job["name"],
                "no_of_recruitment": job["no_of_recruitment"],
                # "address_id": 1,
                # "industry_id": industry_map.get(settings.DATA_THEME_SUBJECT),
                "contract_type_id": contract_type_map.get("Full-Time"),
                "description": job["description"],
                # "date_from": f"{today}",
                # "date_to": f"{today + timedelta(days=365 * 2)}",
                # "interviewer_ids": [u["id"] for u in random.sample(users, min(2, len(users)))],
            }

            if dept_id:
                data["department_id"] = dept_id
                # data["skill_ids"] = [skill_map.get(s) for s in job["skills"] if skill_map.get(s) is not None]

            job_positions_records.append(data)

        await client.create(HRModelName.HR_JOB.value, [job_positions_records])
    logger.succeed(f"Inserted {len(job_positions)} job positions")


async def delete_default_job_positions():
    async with OdooClient() as client:
        with contextlib.suppress(Exception):
            jobs = await client.search_read(HRModelName.HR_JOB.value, [], ["id", "name"])
            if jobs:
                await client.unlink(HRModelName.HR_JOB.value, [j["id"] for j in jobs])
