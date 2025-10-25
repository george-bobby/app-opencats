from apps.odoosales.config.constants import BANK_NAMES, CONTACT_TAGS
from apps.odoosales.config.settings import settings
from apps.odoosales.models.contact import Individual, IndividualResponse
from apps.odoosales.utils.openai import get_system_prompt, openai
from common.logger import logger
from common.save_to_json import save_to_json


FILENAME_TO_SAVE = "individuals.json"


def get_user_prompt(count) -> str:
    prompt = f"""
        Generate {count} realistic individual customer contacts for a US-based SME using an Odoo Sales system.
        Each contact must be a plausible person residing in the USA.

        For each individual, provide the following details:
        - **name**: Full name of the individual.
        - **title**: Title of contact. Must be one of: 'Miss', 'Madam', 'Mister'.
        - **phone**: Primary 10-digit phone number for the contact (e.g., 555-123-4567).
        - **mobile**: Mobile phone number for the contact (e.g., 555-987-6543).
        - **job_position**: The individual's job title or role.
        - **email**: Primary email address for the individual.
        - **primary_address**: The individual's primary residential or business address, including street, city, state (full name), and zip.
        - **category**: Get from the following list of categories: {CONTACT_TAGS}
        - **vat**: Tax identification number (e.g., Social Security Number - SSN in the US).
        - **website**: Personal or professional website URL (optional).
        - **note**: General notes about the individual (optional).
        - **primary_bank_account**: The individual's primary bank account details, including:
            - **bank_name**: Get from the following list of banks: {BANK_NAMES}
            - **account_number**: The bank account number
    """
    return prompt


async def generate_individuals(count: int | None = None):
    if count is None:
        return
    logger.start(f"Generating {count} individuals...")

    user_prompt = get_user_prompt(count)
    response = await openai.responses.parse(
        model=settings.DEFAULT_MODEL,
        input=[
            {"role": "system", "content": get_system_prompt()},
            {"role": "user", "content": user_prompt},
        ],
        text_format=IndividualResponse,
        temperature=0.7,
        max_output_tokens=settings.MAX_OUTPUT_TOKENS,
    )

    if not response.output_parsed:
        logger.warning("No individuals generated. Please generate again.")
        return

    individuals: list[Individual] = response.output_parsed.individuals

    if not individuals:
        logger.warning("No individuals generated. Please generate again.")
        return

    save_to_json([individual.model_dump() for individual in individuals], settings.DATA_PATH.joinpath(FILENAME_TO_SAVE))

    logger.succeed(f"Generated {len(individuals)} individuals")
