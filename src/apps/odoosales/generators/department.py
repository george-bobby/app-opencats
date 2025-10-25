from apps.odoosales.config.settings import settings
from apps.odoosales.models.department import Department, DepartmentResponse
from apps.odoosales.utils.openai import get_system_prompt, openai
from common.logger import logger
from common.save_to_json import save_to_json


FILENAME_TO_SAVE = "departments.json"


async def generate_departments(count: int):
    logger.start(f"Generating {count} departments...")

    user_prompt = f"""
        Generate at least {count} realistic departments for a US-based SME using an Odoo HR system.
        The departments should be relevant to the business theme: {settings.DATA_THEME_SUBJECT}
        The departments should cover various aspects and positions of the business.
    """
    response = await openai.responses.parse(
        model=settings.DEFAULT_MODEL,
        input=[
            {"role": "system", "content": get_system_prompt()},
            {"role": "user", "content": user_prompt},
        ],
        text_format=DepartmentResponse,
        temperature=0.7,
    )

    if not response.output_parsed:
        logger.warning("No department data generated. Please generate again.")
        return

    departments: list[Department] = response.output_parsed.departments

    if not departments:
        logger.warning("No department data generated. Please generate again.")
        return

    save_to_json([dept.model_dump() for dept in departments], settings.DATA_PATH.joinpath(FILENAME_TO_SAVE))

    logger.succeed(f"Generated {count} departments")
