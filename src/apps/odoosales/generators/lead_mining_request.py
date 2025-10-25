from apps.odoosales.config.settings import settings
from apps.odoosales.models.lead_mining_request import LeadMiningRequest, LeadMiningRequestResponse
from apps.odoosales.utils.openai import get_system_prompt, openai
from common.load_json import load_json
from common.logger import logger
from common.save_to_json import save_to_json


FILENAME_TO_SAVE = "lead_mining_requests.json"


async def generate_lead_mining_requests(count: int | None = None):
    if count is None:
        return

    logger.start(f"Generating {count} lead mining requests...")

    industries = load_json(settings.DATA_PATH.joinpath("industries.json"))
    countries = load_json(settings.DATA_PATH.joinpath("countries.json"))

    user_prompt = f"""
        Generate {count} realistic lead mining requests for a US-based SME using an Odoo Sales system.
        
        Each request should include:
        - A unique name prefix
        - A list of country names from the following options: {countries}
        - A list of industry names from the following options: {industries}
        - A sales team name (e.g., "Sales Team A")
        - A salesperson name (e.g., "John Doe")
        - A list of tag names (e.g., "Tag1", "Tag2")
    """
    response = await openai.responses.parse(
        model=settings.DEFAULT_MODEL,
        input=[
            {"role": "system", "content": get_system_prompt()},
            {"role": "user", "content": user_prompt},
        ],
        text_format=LeadMiningRequestResponse,
        temperature=0.7,
    )

    if not response.output_parsed:
        logger.warning("No lead mining requests generated. Please generate again.")
        return

    lead_mining_requests: list[LeadMiningRequest] = response.output_parsed.lead_mining_requests

    if not lead_mining_requests:
        logger.warning("No lead mining requests generated. Please generate again.")
        return

    save_to_json([request.model_dump() for request in lead_mining_requests], settings.DATA_PATH.joinpath(FILENAME_TO_SAVE))

    logger.succeed(f"Generated {len(lead_mining_requests)} lead mining requests")
