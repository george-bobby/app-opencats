"""Manages job applications and recruitment data."""

import random
from datetime import datetime, timedelta

from faker import Faker

from apps.odoohr.config.constants import HRModelName, ResModelName
from apps.odoohr.utils.odoo import OdooClient
from common.logger import logger


faker = Faker()


async def insert_applications():
    logger.start("Inserting applications")
    async with OdooClient() as client:
        # Fetch candidates
        candidates = await client.search_read(model=HRModelName.HR_CANDIDATE.value, fields=["id", "partner_name", "email_from"])
        if not candidates:
            raise ValueError("No candidates found. Please insert candidates first.")

        # Fetch job positions with departments
        jobs = await client.search_read(model=HRModelName.HR_JOB.value, domain=[("name", "!=", "CEO")], fields=["id", "name", "department_id"])
        if not jobs:
            raise ValueError("No job positions found. Please insert job positions first.")

        # Fetch users for recruiters/interviewers
        users = await client.search_read(model=ResModelName.USER.value, fields=["id", "name", "login"])
        if not users:
            raise ValueError("No users found. Please insert users first.")

        # Fetch recruitment stages
        stages = await client.search_read(model=HRModelName.HR_RECRUITMENT_STAGE.value, fields=["id", "name"])
        if not stages:
            raise ValueError("No recruitment stages found.")

        ceo_position = await client.search_read(model=HRModelName.HR_JOB.value, domain=[("name", "=", "CEO")], fields=["id"])
        ceo = await client.search_read(
            model=HRModelName.HR_EMPLOYEE.value,
            domain=[("job_id", "=", ceo_position[0]["id"])],
            fields=["id", "user_id"],
        )

        ceo_user_id = ceo[0]["user_id"][0] if ceo and ceo[0]["user_id"] else 2  # Default to user ID 2 if no user is linked

        app_records = []
        for idx in range(len(candidates)):
            # Candidate
            candidate = candidates[idx]
            candidate_name = candidate.get("partner_name") or faker.name()

            # Extract first and last name from candidate name
            name_parts = candidate_name.split()
            first_name = name_parts[0] if name_parts else "john"
            last_name = name_parts[-1] if len(name_parts) > 1 else "doe"

            email = f"{first_name.lower()}.{last_name.lower()}@{random.choice(['gmail', 'outlook'])}.com"
            # Job position
            job = random.choice(jobs)
            job_id = job["id"]
            department_id = job["department_id"][0] if job["department_id"] else None
            # Interviewers (1-3, but only if enough users)
            interviewer_pool = [u["id"] for u in users]
            if interviewer_pool:
                max_interviewers = min(3, len(interviewer_pool))
                num_interviewers = random.randint(1, max_interviewers)
                interviewer_ids = random.sample(interviewer_pool, num_interviewers)
            else:
                interviewer_ids = []
            # Stage
            stage = random.choice(stages)
            stage_id = stage["id"]
            # Internal note
            internal_note = faker.sentence(nb_words=8)
            # Salary package
            salary = random.randint(50000, 180000)
            # Application date (within the past 180 days)
            application_date = datetime.now() - timedelta(days=random.randint(1, 180))
            application_date_str = application_date.strftime("%Y-%m-%d")

            # Insert application
            application_data = {
                "partner_name": candidate_name,
                "candidate_id": candidate["id"],
                "email_from": email,
                "partner_phone": faker.numerify("+1 (###) ###-####"),
                "job_id": job_id,
                "department_id": department_id,
                "user_id": ceo_user_id,
                "interviewer_ids": interviewer_ids,
                "stage_id": stage_id,
                "salary_expected": salary,
                "date_open": application_date_str,
                "applicant_notes": internal_note,
            }
            app_records.append(application_data)
        await client.create(HRModelName.HR_APP.value, [app_records])
        logger.succeed(f"Inserted {len(app_records)} applications")
