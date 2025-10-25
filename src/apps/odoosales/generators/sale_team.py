import pandas as pd

from apps.odoosales.config.settings import settings
from apps.odoosales.models.sale_team import SaleTeam, SaleTeamResponse
from apps.odoosales.utils.openai import get_system_prompt, openai
from common.logger import logger
from common.save_to_json import save_to_json


FILENAME_TO_SAVE = "sale_teams.json"


async def generate_sale_teams(count: int):
    logger.start(f"Generating {count} sale teams...")

    df_users = pd.read_json(settings.DATA_PATH.joinpath("users.json"))

    user_prompt = f"""
        Generate at least {count} realistic sale teams for a US-based SME using an Odoo Sales system.
        The sale teams should be relevant to the business theme: {settings.DATA_THEME_SUBJECT}
        
        Each sale team should have the following attributes:
        - name: A unique name for the sale team.
        - description: A brief description of the sale team.
        - leader: The name of the team leader, get from {df_users["name"].tolist()}.
        - members: A list of team members names (at least 3 members), get from {df_users["name"].tolist()}.
        
        The leader name should be unique and not repeated in the members list.
    """

    response = await openai.responses.parse(
        model=settings.DEFAULT_MODEL,
        input=[
            {"role": "system", "content": get_system_prompt()},
            {"role": "user", "content": user_prompt},
        ],
        text_format=SaleTeamResponse,
        temperature=0.7,
        max_output_tokens=settings.MAX_OUTPUT_TOKENS,
    )

    if not response.output_parsed:
        logger.warning("No sale teams generated. Please generate again.")
        return

    sale_teams: list[SaleTeam] = response.output_parsed.sale_teams

    if not sale_teams:
        logger.warning("No sale teams generated. Please generate again.")
        return

    save_to_json([team.model_dump() for team in sale_teams], settings.DATA_PATH.joinpath(FILENAME_TO_SAVE))

    logger.succeed(f"Generated {len(sale_teams)} sale teams")
