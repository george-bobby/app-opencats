from apps.odooinventory.config.settings import settings
from apps.odooinventory.models.work_center import WorkCenter, WorkCenterResponse
from apps.odooinventory.utils.openai import get_system_prompt, openai
from common.logger import logger
from common.save_to_json import save_to_json


FILENAME_TO_SAVE = "work_centers.json"


async def generate_work_centers(count: int | None = None):
    if count is None:
        return
    logger.start(f"Generating {count} work centers...")

    user_prompt = f"""
        Generate {count} realistic work centers for a US-based SME using an Odoo Manufacturing system.
    """
    response = await openai.responses.parse(
        model=settings.DEFAULT_MODEL,
        input=[
            {"role": "system", "content": get_system_prompt()},
            {"role": "user", "content": user_prompt},
        ],
        text_format=WorkCenterResponse,
        temperature=0.7,
        max_output_tokens=settings.MAX_OUTPUT_TOKENS,
    )

    if not response.output_parsed:
        logger.warning("No work_centers generated. Please generate again.")
        return

    work_centers: list[WorkCenter] = response.output_parsed.work_centers

    if not work_centers:
        logger.warning("No work_centers generated. Please generate again.")
        return

    save_to_json([center.model_dump() for center in work_centers], settings.DATA_PATH.joinpath(FILENAME_TO_SAVE))

    logger.succeed(f"Generated {len(work_centers)} work_centers")
