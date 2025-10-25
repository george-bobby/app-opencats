import pandas as pd

from apps.odoosales.config.settings import settings
from apps.odoosales.models.combo import Combo, ComboResponse
from apps.odoosales.utils.openai import get_system_prompt, openai
from common.logger import logger
from common.save_to_json import save_to_json


FILENAME_TO_SAVE = "combo.json"


async def generate_combos(count: int):
    logger.start(f"Generating {count} combos...")

    df_products = pd.read_json(settings.DATA_PATH.joinpath("products.json"))

    if df_products.empty:
        logger.warning("No products available to generate combos. Please generate products first.")
        return

    user_prompt = f"""
        Generate {count} realistic combo products for a US-based SME using an Odoo Sales system.
        Each combo should include at least 3 products.
        The combos should be relevant to the products generated in the previous step.
        The combos should be realistic and could exist in the USA market.
        The combos should be diverse and unique, covering a wide range of categories.
        
        The combo products should be in the following format:
        - name: Combo Product Name
        - products: a list of product names get from here: {df_products["name"].to_list()}
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
