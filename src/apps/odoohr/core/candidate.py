"""Creates job candidates with skills and availability."""

import random

from faker import Faker

from apps.odoohr.config.constants import HRModelName, ResModelName
from apps.odoohr.config.settings import settings
from apps.odoohr.utils.odoo import OdooClient
from common.load_json import load_json
from common.logger import logger


faker = Faker()


async def insert_candidates():
    candidates = load_json(settings.DATA_PATH.joinpath("candidates.json"))

    logger.start(f"Inserting {len(candidates)} candidates")
    async with OdooClient() as client:
        skills = await client.search_read(
            HRModelName.HR_SKILL.value,
            [],
            ["id", "name", "skill_type_id"],
        )
        skill_levels = await client.search_read(
            HRModelName.HR_SKILL_LEVEL.value,
            [],
            ["id", "name", "skill_type_id"],
        )
        skills_map = {skill["name"]: skill for skill in skills}
        skill_levels_map = {}
        for skill_level in skill_levels:
            skill_type_id = skill_level["skill_type_id"][0] if isinstance(skill_level["skill_type_id"], list) else skill_level["skill_type_id"]
            if skill_type_id not in skill_levels_map:
                skill_levels_map[skill_type_id] = []
            skill_levels_map[skill_type_id].append(skill_level["id"])

        degrees = await client.search_read(
            HRModelName.HR_RECRUITMENT_DEGREE.value,
            [
                (
                    "name",
                    "in",
                    [
                        "Bachelor Degree",
                        "Graduate",
                    ],
                )
            ],
            ["id"],
        )
        departments = await client.search_read(
            HRModelName.HR_DEPARTMENT.value,
            [],
            ["id", "name", "manager_id"],
        )
        departments_lookup = {department["name"]: department for department in departments}
        jobs = await client.search_read(
            HRModelName.HR_JOB.value,
            [],
            ["id", "name"],
        )
        jobs_lookup = {job["name"]: job for job in jobs}
        stages = await client.search_read(model=HRModelName.HR_RECRUITMENT_STAGE.value, fields=["id", "name"])
        users = await client.search_read(ResModelName.USER.value, [("active", "=", True)], ["id"])

        utm_sources = await client.search_read(
            "utm.source",
            [],
            ["id"],
        )
        utm_media = await client.search_read(
            "utm.medium",
            [],
            ["id"],
        )

        for candidate in candidates:
            first_name = faker.first_name()
            last_name = faker.last_name()
            full_name = f"{first_name} {last_name}"
            email = f"{first_name.lower()}.{last_name.lower()}@{random.choice(['gmail', 'outlook'])}.com"

            candidate_id = await client.create(
                HRModelName.HR_CANDIDATE.value,
                {
                    "partner_name": full_name,
                    "email_from": email,
                    "partner_phone": faker.numerify("+1 (###) ###-####"),
                    "linkedin_profile": candidate["partner_website"],
                    "type_id": random.choice(degrees)["id"],
                    "availability": faker.date_between(start_date="today", end_date="+30d").strftime("%Y-%m-%d %H:%M:%S"),
                },
            )

            for skill in candidate["skills"]:
                if skill in skills_map:
                    skill_id = skills_map[skill]["id"]
                    skill_type_id = skills_map[skill]["skill_type_id"][0]
                    skill_levels = skill_levels_map.get(skill_type_id, [])
                    await client.create(
                        HRModelName.HR_CANDIDATE_SKILL.value,
                        {
                            "candidate_id": candidate_id,
                            "skill_id": skill_id,
                            "skill_type_id": skill_type_id,
                            "skill_level_id": random.choice(skill_levels),
                        },
                    )

            await client.create(
                HRModelName.HR_APP.value,
                {
                    "candidate_id": candidate_id,
                    "department_id": departments_lookup.get(candidate["department"], {}).get("id"),
                    "job_id": jobs_lookup.get(candidate["job_position"], {}).get("id"),
                    "priority": random.choice(["0", "1", "2", "3"]),
                    "user_id": departments_lookup.get(candidate["department"], {}).get("manager_id", [0])[0],
                    "interviewer_ids": [u["id"] for u in random.sample(users, min(2, len(users)))],
                    "stage_id": random.choice(stages)["id"],
                    "salary_expected": candidate["salary_expected"],
                    "salary_proposed": candidate["salary_expected"] - random.randint(1000, 2000),
                    "applicant_notes": candidate["note"],
                    "color": random.randint(0, 11),
                    "kanban_state": random.choice(["normal", "done", "blocked"]),
                    "source_id": random.choice(utm_sources)["id"],
                    "medium_id": random.choice(utm_media)["id"],
                },
            )
        logger.succeed(f"Inserted {len(candidates)} candidates")
