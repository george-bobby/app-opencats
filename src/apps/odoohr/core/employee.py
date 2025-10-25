"""Manages employee data, categories, and organizational structure."""

import random
from pathlib import Path

from faker import Faker

from apps.odoohr.config.constants import (
    DEFAULT_ADDRESS_ID,
    DEFAULT_ADMIN_USER_ID,
    DEFAULT_COUNTRY_ID,
    DEFAULT_EMPLOYEE_ID,
    HRModelName,
    ResModelName,
)
from apps.odoohr.config.settings import settings
from apps.odoohr.utils.load_json import load_json
from apps.odoohr.utils.odoo import OdooClient
from common.img_to_b64 import img_to_b64
from common.logger import logger


faker = Faker()


async def _transform_emp_data(emp):
    async with OdooClient() as client:
        us_states = await client.search_read(
            ResModelName.COUNTRY_STATE.value,
            [["country_id", "=", DEFAULT_COUNTRY_ID]],
            ["id", "name"],
        )
        us_states_map = {state["name"]: state["id"] for state in us_states}

        job_positions = await client.search_read(
            HRModelName.HR_JOB.value,
            [],
            ["id", "name"],
        )
        job_positions_map = {jp["name"]: jp["id"] for jp in job_positions}

        categories = await client.search_read(
            HRModelName.HR_EMPLOYEE_CATEGORY.value,
            [],
            ["id", "name"],
        )
        categories_map = {cat["name"]: cat["id"] for cat in categories}

        work_locations = await client.search_read(
            HRModelName.HR_WORK_LOCATION.value,
            [],
            ["id"],
        )
    data = {
        "name": emp["name"],
        "work_email": emp["work_email"],
        "private_email": emp["private_email"],
        "job_id": job_positions_map.get(emp["job_position"], None),
        "job_title": emp["job_title"],
        "private_street": emp["private_address"]["street"],
        "private_street2": faker.secondary_address(),
        "private_city": emp["private_address"]["city"],
        "private_state_id": us_states_map[emp["private_address"]["state"]],
        "private_zip": emp["private_address"]["zip"],
        "private_car_plate": emp["private_car_plate"],
        "identification_id": emp["identification_id"],
        "ssnid": emp["ssnid"],
        "gender": emp["gender"],
        "category_ids": [categories_map[cat] for cat in emp["categories"] if cat in categories_map],
        "birthday": faker.date_of_birth(minimum_age=18, maximum_age=60).strftime("%Y-%m-%d"),
        "place_of_birth": emp["place_of_birth"],
        "country_of_birth": DEFAULT_COUNTRY_ID,
        "passport_id": emp["passport_id"],
        "certificate": emp["education"]["certificate"],
        "study_field": emp["education"]["study_field"],
        "study_school": emp["education"]["study_school"],
        "visa_no": emp["work_permit"]["visa_no"],
        "permit_no": emp["work_permit"]["permit_no"],
        "visa_expire": emp["work_permit"]["visa_expire"],
        "work_permit_expiration_date": emp["work_permit"]["work_permit_expiration_date"],
        "country_id": DEFAULT_COUNTRY_ID,
        "private_country_id": DEFAULT_COUNTRY_ID,
        "address_id": DEFAULT_ADDRESS_ID,
        "phone": faker.numerify("+1 (###) ###-####"),
        "work_phone": faker.numerify("+1 (###) ###-####"),
        "mobile_phone": faker.numerify("+1 (###) ###-####"),
        "private_phone": faker.numerify("+1 (###) ###-####"),
        "emergency_phone": faker.numerify(),
        "emergency_contact": faker.name(),
        "work_location_id": random.choice(work_locations)["id"],
        "tz": "America/New_York",
        "distance_home_work": random.randint(1, 20),  # Distance in km
        "marital": random.choice(["single", "married", "divorced"]),
        "spouse_complete_name": faker.name(),
        "spouse_birthdate": faker.date_of_birth(minimum_age=18, maximum_age=60).strftime("%Y-%m-%d"),
        "children": random.randint(0, 5),  # Number of children
        "barcode": faker.numerify("############"),
        "pin": faker.numerify("######"),
    }
    return data


async def insert_employee_categories():
    org = load_json(settings.DATA_PATH.joinpath("org.json"))
    categories = set()
    for dept in org["departments"]:
        for emp in dept["employees"]:
            categories.update(emp["categories"])

    logger.start(f"Inserting {len(categories)} employee categories")
    async with OdooClient() as client:
        for category in categories:
            await client.create(
                HRModelName.HR_EMPLOYEE_CATEGORY.value,
                {
                    "name": category,
                    "color": random.randint(1, 11),  # Random color between 1 and 11
                },
            )
    logger.succeed(f"Inserted {len(categories)} employee categories.")


async def insert_employees():
    org = load_json(str(settings.DATA_PATH.joinpath("org.json")))

    emp_count = sum(len(dept["employees"]) for dept in org["departments"])

    ceo = org["ceo"]
    coo = org["coo"]
    departments = org["departments"]

    # Preload and shuffle avatars
    male_avatar_dir = Path(settings.DATA_PATH) / "avatars" / "male"
    female_avatar_dir = Path(settings.DATA_PATH) / "avatars" / "female"
    male_avatars = list(male_avatar_dir.glob("*.jpg"))
    female_avatars = list(female_avatar_dir.glob("*.jpg"))
    random.shuffle(male_avatars)
    random.shuffle(female_avatars)

    # Collect all employees by gender
    all_emps = []
    male_emps = []
    female_emps = []
    for dept in departments:
        for emp in dept["employees"]:
            all_emps.append(emp)
            if emp["gender"] == "male":
                male_emps.append(emp)
            else:
                female_emps.append(emp)

    # Assign avatars by index
    if len(male_emps) > len(male_avatars):
        raise ValueError("Not enough male avatars for unique assignment!")
    if len(female_emps) > len(female_avatars):
        raise ValueError("Not enough female avatars for unique assignment!")
    for idx, emp in enumerate(male_emps):
        emp["image_1920"] = img_to_b64(male_avatars[idx])
    for idx, emp in enumerate(female_emps):
        emp["image_1920"] = img_to_b64(female_avatars[idx])

    logger.start(f"Inserting {emp_count} employees")
    async with OdooClient() as client:
        resume_line_types = await client.search_read(
            HRModelName.HR_RESUME_LINE_TYPE.value,
            [],
            ["id", "name"],
        )
        resume_line_types_map = {rlt["name"]: rlt["id"] for rlt in resume_line_types}

        existing_departments = await client.search_read(
            HRModelName.HR_DEPARTMENT.value,
            [],
            ["id", "name"],
        )
        departments_lookup = {dept["name"]: dept for dept in existing_departments}

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

        emp_map = {}

        await client.write(
            ResModelName.USER.value,
            DEFAULT_ADMIN_USER_ID,
            {
                "name": ceo["name"],
                "phone": faker.numerify("+1 (###) ###-####"),
                "mobile": faker.numerify("+1 (###) ###-####"),
            },
        )
        emp_map[ceo["name"]] = DEFAULT_ADMIN_USER_ID
        coo_user_id = await client.create(
            ResModelName.USER.value,
            {
                "name": coo["name"],
                "login": coo["work_email"],
                "email": coo["work_email"],
                "phone": faker.numerify("+1 (###) ###-####"),
                "mobile": faker.numerify("+1 (###) ###-####"),
                "active": True,
                "groups_id": [1],
            },
        )
        emp_map[coo["name"]] = coo_user_id

        ceo_data = await _transform_emp_data(ceo)
        ceo_data["user_id"] = DEFAULT_ADMIN_USER_ID
        # Assign avatar to CEO if gendered
        if ceo["gender"] == "male":
            ceo_data["image_1920"] = img_to_b64(male_avatars[0])
        else:
            ceo_data["image_1920"] = img_to_b64(female_avatars[0])
        await client.write(HRModelName.HR_EMPLOYEE.value, DEFAULT_EMPLOYEE_ID, ceo_data)

        coo_data = await _transform_emp_data(coo)
        coo_data["user_id"] = coo_user_id
        coo_data["coach_id"] = DEFAULT_EMPLOYEE_ID
        coo_data["leave_manager_id"] = DEFAULT_EMPLOYEE_ID
        coo_data["parent_id"] = DEFAULT_EMPLOYEE_ID
        # Assign avatar to COO if gendered
        if coo["gender"] == "male":
            coo_data["image_1920"] = img_to_b64(male_avatars[1])
        else:
            coo_data["image_1920"] = img_to_b64(female_avatars[1])
        coo_id = await client.create(HRModelName.HR_EMPLOYEE.value, coo_data)

        for idx, dept in enumerate(departments):
            dept_id = departments_lookup.get(dept["name"], {}).get("id")
            manager = dept["manager"]
            manager_data = await _transform_emp_data(manager)
            manager_data["parent_id"] = coo_id
            manager_data["coach_id"] = coo_id
            manager_data["leave_manager_id"] = coo_id
            # Assign avatar to manager
            if manager["gender"] == "male":
                manager_data["image_1920"] = img_to_b64(male_avatars[2 + idx])
            else:
                manager_data["image_1920"] = img_to_b64(female_avatars[2 + idx])
            manager_id = await client.create(HRModelName.HR_EMPLOYEE.value, manager_data)
            emp_map[manager["name"]] = manager_id

            await client.write(
                HRModelName.HR_DEPARTMENT.value,
                dept_id,
                {"manager_id": manager_id, "color": idx + 1},
            )

            for emp in dept["employees"]:
                user_id = await client.create(
                    ResModelName.USER.value,
                    {
                        "name": emp["name"],
                        "login": emp["work_email"],
                        "email": emp["work_email"],
                        "phone": faker.numerify("+1 (###) ###-####"),
                        "mobile": faker.numerify("+1 (###) ###-####"),
                        "active": True,
                        "groups_id": [1],
                    },
                )

                emp_data = await _transform_emp_data(emp)
                emp_data["department_id"] = dept_id
                emp_data["user_id"] = user_id
                emp_data["coach_id"] = manager_id
                emp_data["leave_manager_id"] = DEFAULT_ADMIN_USER_ID
                emp_data["parent_id"] = manager_id
                # Avatar already assigned in emp["image_1920"]
                emp_data["image_1920"] = emp["image_1920"]
                emp_id = await client.create(HRModelName.HR_EMPLOYEE.value, emp_data)
                emp_map[emp["name"]] = emp_id

                for line in emp["resume_lines"]:
                    await client.create(
                        HRModelName.HR_RESUME_LINE.value,
                        {
                            "name": line["name"],
                            "description": line["description"],
                            "date_end": line["date_end"] if line["date_end"] else None,
                            "date_start": line["date_start"] if line["date_start"] else None,
                            "line_type_id": resume_line_types_map[line["type"]],
                            "display_type": "classic",
                            "employee_id": emp_id,
                        },
                    )
                for skill in emp["skills"]:
                    if skill in skills_map:
                        skill_id = skills_map[skill]["id"]
                        skill_type_id = skills_map[skill]["skill_type_id"][0]
                        skill_levels = skill_levels_map.get(skill_type_id, [])
                        await client.create(
                            HRModelName.HR_EMPLOYEE_SKILL.value,
                            {
                                "employee_id": emp_id,
                                "skill_id": skill_id,
                                "skill_type_id": skill_type_id,
                                "skill_level_id": random.choice(skill_levels),
                            },
                        )

        logger.succeed(f"Inserted {emp_count} employees.")
