from apps.odoosales.config.settings import settings
from apps.odoosales.models.activity_plan import ActivityPlan, ActivityPlanResponse
from apps.odoosales.utils.openai import get_system_prompt, openai
from common.logger import logger
from common.save_to_json import save_to_json


FILENAME_TO_SAVE = "activity_plans.json"


async def generate_activity_plans(count: int | None = None):
    if count is None:
        return

    logger.start(f"Generating {count} activity plans...")

    user_prompt = f"""
        Generate {count} distinct and practical sales activity plans for a sales team using Odoo Sales.
        These plans should be suitable for a US-based SME.

        For each activity plan, you must:
        1.  **Create a Plan Name**: Devise a clear and descriptive name for the plan that reflects its purpose 
            (e.g., "New Lead Follow-Up", "Post-Demo Nurturing", "High-Value Prospect Engagement").
        2.  **Define Activity Lines**: Create 2 to 4 sequential activity lines that outline the sales process.

        For each activity line, provide:
        - **Activity Type Name**: The type of activity, such as 'Email', 'Call', 'Meeting', 'LinkedIn Message'.
        - **Summary**: A brief, actionable summary of the activity's goal (e.g., "Initial introduction email", "Qualify lead over the phone", "Schedule a product demo").
        - **Delay Count**: The number of units of time to wait before this activity (e.g., 3, 7, 14).
        - **Interval Type**: The unit of time for the delay, which must be one of: "days", "weeks", or "months".

        The sequence of activities should be logical for a standard sales process.
    """
    response = await openai.responses.parse(
        model=settings.DEFAULT_MODEL,
        input=[
            {"role": "system", "content": get_system_prompt()},
            {"role": "user", "content": user_prompt},
        ],
        text_format=ActivityPlanResponse,
        temperature=0.7,
    )

    if not response.output_parsed:
        logger.warning("No activity plans generated. Please generate again.")
        return

    activity_plans: list[ActivityPlan] = response.output_parsed.activity_plans

    if not activity_plans:
        logger.warning("No activity plans generated. Please generate again.")
        return

    save_to_json([plan.model_dump() for plan in activity_plans], settings.DATA_PATH.joinpath(FILENAME_TO_SAVE))

    logger.succeed(f"Generated {len(activity_plans)} activity plans")
