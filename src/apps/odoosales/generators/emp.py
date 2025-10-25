import asyncio

import pandas as pd

from apps.odoosales.config.settings import settings
from apps.odoosales.models.emp import CLevelResponse, Employee, EmployeeResponse
from apps.odoosales.utils.openai import get_system_prompt, openai
from common.logger import logger
from common.save_to_json import save_to_json


FILENAME_TO_SAVE = "employees.json"


async def generate_employees(count: int):
    await generate_c_level_employees()

    logger.start(f"Generating {count} employees for each department...")

    df_departments = pd.read_json(settings.DATA_PATH.joinpath("departments.json"))
    department_names = df_departments["name"].tolist()

    async def generate_for_department(dept_name: str):
        user_prompt = f"""
            Generate exactly {count} employees for the department '{dept_name}' in a US-based SME using an Odoo HR system.
            Each employee should have realistic details such as name, job title, department, and contact information.
            Ensure that the employees are diverse in terms of roles and responsibilities within their department.
            Use the following job positions as a reference. Assign employees to job positions that belong to their respective department.
            Department data: {df_departments[df_departments["name"] == dept_name].to_dict("records")}
        """
        response = await openai.responses.parse(
            model=settings.DEFAULT_MODEL,
            input=[
                {"role": "system", "content": get_system_prompt()},
                {"role": "user", "content": user_prompt},
            ],
            text_format=EmployeeResponse,
            temperature=0.7,
        )
        if not response.output_parsed or not response.output_parsed.employees:
            logger.warning(f"No employees data generated for department {dept_name}. Please generate again.")
            return []
        return response.output_parsed.employees

    # Run all department generations concurrently
    all_employees_nested = await asyncio.gather(*[generate_for_department(dept) for dept in department_names])
    all_employees = [emp for dept_emps in all_employees_nested for emp in dept_emps]

    if not all_employees:
        logger.warning("No employees data generated. Please generate again.")
        return

    save_to_json([emp.model_dump() for emp in all_employees], settings.DATA_PATH.joinpath(FILENAME_TO_SAVE))

    logger.succeed(f"Generated {len(all_employees)} employees data")


async def generate_c_level_employees():
    logger.start("Generating C-level employees data...")

    user_prompt = """
        Generate ceo and coo for a US-based SME using an Odoo HR system.
        Each employee should have realistic details such as name, job title, department, and contact information.
    """
    response = await openai.responses.parse(
        model=settings.DEFAULT_MODEL,
        input=[
            {"role": "system", "content": get_system_prompt()},
            {"role": "user", "content": user_prompt},
        ],
        text_format=CLevelResponse,
        temperature=0.7,
    )

    if not response.output_parsed:
        logger.warning("No employees data generated. Please generate again.")
        return

    ceo: Employee = response.output_parsed.ceo
    coo: Employee = response.output_parsed.coo

    if not ceo or not coo:
        logger.warning("No c-level data generated. Please generate again.")
        return

    save_to_json(ceo.model_dump(), settings.DATA_PATH.joinpath("ceo.json"))
    save_to_json(coo.model_dump(), settings.DATA_PATH.joinpath("coo.json"))

    logger.succeed("Generated C-level employee data")
