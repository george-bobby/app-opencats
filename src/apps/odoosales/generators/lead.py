from apps.odoosales.config.settings import settings
from apps.odoosales.models.lead import Lead, LeadResponse
from apps.odoosales.utils.openai import get_system_prompt, openai
from common.logger import logger
from common.save_to_json import save_to_json


FILENAME_TO_SAVE = "leads.json"


async def generate_leads(count: int):
    logger.start(f"Generating {count} leads...")

    user_prompt = f"""
        Generate exact {count} realistic leads for a US-based SME using an Odoo CRM system.
        
        Each lead should have the following fields:
        - name: Name of the lead
        - description: Brief description of the lead
    """
    response = await openai.responses.parse(
        model=settings.DEFAULT_MODEL,
        input=[
            {"role": "system", "content": get_system_prompt()},
            {"role": "user", "content": user_prompt},
        ],
        text_format=LeadResponse,
        temperature=0.7,
        max_output_tokens=settings.MAX_OUTPUT_TOKENS,
    )

    if not response.output_parsed:
        logger.warning("No leads generated. Please generate again.")
        return

    leads: list[Lead] = response.output_parsed.leads

    if not leads:
        logger.warning("No leads generated. Please generate again.")
        return

    save_to_json([lead.model_dump() for lead in leads], settings.DATA_PATH.joinpath(FILENAME_TO_SAVE))

    logger.succeed(f"Generated {len(leads)} leads")
