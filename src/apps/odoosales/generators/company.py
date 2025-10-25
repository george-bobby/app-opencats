from apps.odoosales.config.constants import BANK_NAMES, COMPANY_INDUSTRIES, CONTACT_TAGS
from apps.odoosales.config.settings import settings
from apps.odoosales.models.contact import Company, CompanyResponse
from apps.odoosales.utils.openai import get_system_prompt, openai
from common.logger import logger
from common.save_to_json import save_to_json


FILENAME_TO_SAVE = "companies.json"


async def generate_companies(count: int | None = None):
    if count is None:
        return
    logger.start(f"Generating {count} companies...")

    user_prompt = f"""
        Generate {count} realistic company contacts for a US-based SME using an Odoo Sales system.
        Each contact must be a plausible company operating in the USA.
        Get category from following list of categories: {CONTACT_TAGS}
        Get industry from following list of industries: {COMPANY_INDUSTRIES}
        Get bank name from following list of banks: {BANK_NAMES}
    """
    response = await openai.responses.parse(
        model=settings.DEFAULT_MODEL,
        input=[
            {"role": "system", "content": get_system_prompt()},
            {"role": "user", "content": user_prompt},
        ],
        text_format=CompanyResponse,
        temperature=0.7,
        max_output_tokens=settings.MAX_OUTPUT_TOKENS,
    )

    if not response.output_parsed:
        logger.warning("No companies generated. Please generate again.")
        return

    companies: list[Company] = response.output_parsed.companies

    if not companies:
        logger.warning("No companies generated. Please generate again.")
        return

    save_to_json([company.model_dump() for company in companies], settings.DATA_PATH.joinpath(FILENAME_TO_SAVE))

    logger.succeed(f"Generated {len(companies)} companies")
