import pandas as pd

from apps.odooinventory.config.settings import settings
from apps.odooinventory.models.bom import BOM, BOMResponse
from apps.odooinventory.utils.openai import get_system_prompt, openai
from common.logger import logger
from common.save_to_json import save_to_json


FILENAME_TO_SAVE = "bill_of_materials.json"


async def generate_bill_of_materials():
    df_work_centers = pd.read_json(settings.DATA_PATH.joinpath("work_centers.json"))
    df_products = pd.read_json(settings.DATA_PATH.joinpath("products.json"))

    logger.start(f"Generating {len(df_products)} bill of materials...")

    user_prompt = f"""
        Generate exactly {len(df_products)} realistic bill of materials for a US-based SME using an Odoo manufacturing system.
        
        For each bom, provide the following details:
        - A product name, get from the list of products: {df_products["name"].to_list()}
        - A list of components, each with:
            - A name
            - A category (get from the list of categories in products)
        - A list of operations, each with:
            - A name
            - A work center (get from the list of work centers: {df_work_centers["name"].to_list()})

        IMPORTANT:
        - Each BOM must have a unique product name.
        - Each BOM must have at least 2 components and 2 operation.
        - The work center should be relevant to the operation.
        - Each BOM must have 1 product. The product name must be unique.
    """
    response = await openai.responses.parse(
        model=settings.DEFAULT_MODEL,
        input=[
            {"role": "system", "content": get_system_prompt()},
            {"role": "user", "content": user_prompt},
        ],
        text_format=BOMResponse,
        temperature=0.5,
        max_output_tokens=settings.MAX_OUTPUT_TOKENS,
    )

    if not response.output_parsed:
        logger.warning("No bill of materials generated. Please generate again.")
        return

    bill_of_materials: list[BOM] = response.output_parsed.bill_of_materials

    if not bill_of_materials:
        logger.warning("No bill of materials generated. Please generate again.")
        return

    save_to_json([bom.model_dump() for bom in bill_of_materials], settings.DATA_PATH.joinpath(FILENAME_TO_SAVE))

    logger.succeed(f"Generated {len(bill_of_materials)} bill of materials")
