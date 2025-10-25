import pandas as pd

from apps.odoosales.config.settings import settings
from apps.odoosales.models.quotation import Quotation, QuotationResponse
from apps.odoosales.utils.openai import get_system_prompt, openai
from common.logger import logger
from common.save_to_json import save_to_json


FILENAME_TO_SAVE = "quotations.json"


async def generate_quotations(count: int):
    logger.start(f"Generating {count} quotations...")

    df_companies = pd.read_json(settings.DATA_PATH.joinpath("companies.json"))
    df_individuals = pd.read_json(settings.DATA_PATH.joinpath("individuals.json"))
    df_products = pd.read_json(settings.DATA_PATH.joinpath("products.json"))

    if df_companies.empty and df_individuals.empty and df_products.empty:
        logger.warning("No companies or individuals available to generate quotations. Please generate companies and individuals first.")
        return

    user_prompt = f"""
        Generate at least {count} realistic quotations for sales teams based in a US-based SME using an Odoo Sales system.
        
        Each quotation should include:
        - customer_name: Name of the customer, get from {df_companies["name"].tolist()} and {df_individuals["name"].tolist()}.
        - product_name: Name of the product, get from {df_products["name"].tolist()}.
    """
    response = await openai.responses.parse(
        model=settings.DEFAULT_MODEL,
        input=[
            {"role": "system", "content": get_system_prompt()},
            {"role": "user", "content": user_prompt},
        ],
        text_format=QuotationResponse,
        temperature=0.7,
        max_output_tokens=settings.MAX_OUTPUT_TOKENS,
    )

    if not response.output_parsed:
        logger.warning("No quotations generated. Please generate again.")
        return

    quotations: list[Quotation] = response.output_parsed.quotations

    if not quotations:
        logger.warning("No quotations generated. Please generate again.")
        return

    save_to_json([quotation.model_dump() for quotation in quotations], settings.DATA_PATH.joinpath(FILENAME_TO_SAVE))

    logger.succeed(f"Generated {len(quotations)} quotations")
