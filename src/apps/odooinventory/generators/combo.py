import pandas as pd

from apps.odooinventory.config.settings import settings
from apps.odooinventory.models.combo import Combo, ComboResponse
from apps.odooinventory.utils.openai import get_system_prompt, openai
from common.logger import logger
from common.save_to_json import save_to_json


FILENAME_TO_SAVE = "combo.json"


async def generate_combos(count: int | None = None):
    logger.start(f"Generating {count} combos...")

    df_products = pd.read_json(settings.DATA_PATH.joinpath("products.json"))

    if df_products.empty:
        logger.warning("No products available to generate combos. Please generate products first.")
        return

    user_prompt = f"""
        Generate {count} realistic combos for a US-based SME using an Odoo Inventory and Odoo Manufacturing system.

        Each combo must have:
        - Combo name
        - List of products (get from the list of products: {df_products["name"].to_list()})
    """
    response = await openai.responses.parse(
        model=settings.DEFAULT_MODEL,
        input=[
            {"role": "system", "content": get_system_prompt()},
            {"role": "user", "content": user_prompt},
        ],
        text_format=ComboResponse,
        temperature=0.7,
        max_output_tokens=settings.MAX_OUTPUT_TOKENS,
    )

    if not response.output_parsed:
        logger.warning("No combos generated. Please generate again.")
        return

    combos: list[Combo] = response.output_parsed.combos

    if not combos:
        logger.warning("No combos generated. Please generate again.")
        return

    save_to_json([combo.model_dump() for combo in combos], settings.DATA_PATH.joinpath(FILENAME_TO_SAVE))

    logger.succeed(f"Generated {len(combos)} combos")
