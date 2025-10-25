from apps.odoosales.config.settings import settings
from apps.odoosales.models.sale_tag import SaleTag, SaleTagResponse
from apps.odoosales.utils.openai import get_system_prompt, openai
from common.logger import logger
from common.save_to_json import save_to_json


FILENAME_TO_SAVE = "sale_tags.json"


async def generate_sale_tags(count: int | None = None):
    if count is None:
        return
    logger.start(f"Generating {count} sale_tags...")

    user_prompt = f"""
        Generate {count} realistic sale tags for a US-based SME using an Odoo Sales system.
    """
    response = await openai.responses.parse(
        model=settings.DEFAULT_MODEL,
        input=[
            {"role": "system", "content": get_system_prompt()},
            {"role": "user", "content": user_prompt},
        ],
        text_format=SaleTagResponse,
        temperature=0.7,
    )

    if not response.output_parsed:
        logger.warning("No sale tags generated. Please generate again.")
        return

    sale_tags: list[SaleTag] = response.output_parsed.sale_tags

    if not sale_tags:
        logger.warning("No sale tags generated. Please generate again.")
        return

    save_to_json([sale_tag.model_dump() for sale_tag in sale_tags], settings.DATA_PATH.joinpath(FILENAME_TO_SAVE))

    logger.succeed(f"Generated {len(sale_tags)} sale tags")
