import pandas as pd

from apps.odoosales.config.settings import settings
from apps.odoosales.models.job_position import JobPosition, JobPositionResponse
from apps.odoosales.utils.openai import get_system_prompt, openai
from common.logger import logger
from common.save_to_json import save_to_json


FILENAME_TO_SAVE = "job_positions.json"


async def generate_job_positions(count: int | None = None):
    logger.start(f"Generating {count} job positions...")

    df_departments = pd.read_json(settings.DATA_PATH.joinpath("departments.json"))

    user_prompt = f"""
        Generate {count} realistic job positions for a US-based SME using an Odoo HR system.
        Each job position should have:
        - A realistic job title/name
        - A detailed description of responsibilities and duties
        - A department from the provided list: {df_departments["name"].to_list()}
        - A realistic expected salary range (annual USD)
        - A list of requirements and qualifications
        - A list of required skills
        - An experience level (Entry Level, Mid Level, Senior, Executive)
        - An employment type (Full Time, Part Time, Contract, Internship)
        - A location (city, state)
        - Whether remote work is allowed
        - Active status (should be True for most positions)
        
        Each department should have 2-4 job positions.
        
        Always include 2 job positions for CEO and COO.
        
        Make sure the data is diverse and realistic for a US business environment.
        Focus on positions relevant to the theme of '{settings.DATA_THEME_SUBJECT}'.
    """
    response = await openai.responses.parse(
        model=settings.DEFAULT_MODEL,
        input=[
            {"role": "system", "content": get_system_prompt()},
            {"role": "user", "content": user_prompt},
        ],
        text_format=JobPositionResponse,
        temperature=0.7,
    )

    if not response.output_parsed:
        logger.warning("No job positions generated. Please generate again.")
        return

    job_positions: list[JobPosition] = response.output_parsed.job_positions

    if not job_positions:
        logger.warning("No job positions generated. Please generate again.")
        return

    save_to_json([job_position.model_dump() for job_position in job_positions], settings.DATA_PATH.joinpath(FILENAME_TO_SAVE))

    logger.succeed(f"Generated {len(job_positions)} job positions")
