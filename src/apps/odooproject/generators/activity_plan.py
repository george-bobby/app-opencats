import pandas as pd

from apps.odooproject.config.settings import settings
from apps.odooproject.models.activity_plan import ActivityPlan, ActivityPlanResponse
from common.logger import logger
from common.openai import get_system_prompt, openai
from common.save_to_json import save_to_json


FILENAME_TO_SAVE = "activity_plans.json"


async def generate_activity_plans(count: int):
    logger.start(f"Generating {count} activity plans...")

    df_activity_types = pd.read_json(settings.DATA_PATH.joinpath("activity_types.json"))

    max_retries = 3
    for attempt in range(max_retries):
        try:
            activity_plans = await _generate_activity_plans(count, df_activity_types)
            save_to_json([plan.model_dump() for plan in activity_plans], settings.DATA_PATH.joinpath(FILENAME_TO_SAVE))
            logger.succeed(f"Generated {len(activity_plans)} activity plans")
            break
        except Exception as e:
            if attempt < max_retries - 1:
                logger.info("Retrying...")
            else:
                logger.error(f"Failed to generate activity plans after {max_retries} attempts: {e}")
                return []


async def _generate_activity_plans(count: int, df_activity_types: pd.DataFrame) -> list[ActivityPlan]:
    """Internal function to generate activity plans."""
    activity_plan_prompt = f"""
        Generate {count} realistic activity plans for an Odoo Project system.
        
        The activity plans should be relevant for a US-based SME in the '{settings.DATA_THEME_SUBJECT}' industry.
        Each activity plan should have:
        - A descriptive name that indicates the type of workflow (e.g., "New Client Setup", "Project Kickoff")
        - A model: either "project.task" or "project.project"
        - 2-4 activity lines that define the workflow steps
        
        Each activity line should have:
        - activity_type: Get from provided list of activity types: {df_activity_types["name"].to_list()}
        - summary: A brief description of the activity
        - assignment: "ask_at_launch" or "default_user"
        - interval: A number (0-10) representing timing
        - delay_unit: "days"
        - trigger: "before_plan_date" or "after_plan_date"
        
        Activity plans should represent common business workflows like onboarding, project initiation, client management, etc.
    """
    response = await openai.responses.parse(
        model=settings.DEFAULT_MODEL,
        input=[
            {"role": "system", "content": get_system_prompt()},
            {"role": "user", "content": activity_plan_prompt},
        ],
        text_format=ActivityPlanResponse,
        temperature=0.2,
    )

    plans = response.output_parsed.activity_plans

    if not plans:
        logger.warning("No activity plans generated. Please generate again.")
        return []

    return plans
