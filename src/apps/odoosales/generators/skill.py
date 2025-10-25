from apps.odoosales.config.settings import settings
from apps.odoosales.models.skill import Skill, SkillResponse
from apps.odoosales.utils.openai import get_system_prompt, openai
from common.logger import logger
from common.save_to_json import save_to_json


FILENAME_TO_SAVE = "skills.json"


async def generate_skills(count: int):
    logger.start(f"Generating {count} skills...")

    user_prompt = f"""
        Generate at least {count} realistic skills for a US-based SME using an Odoo HR system.
        The skills should be relevant to the business theme: {settings.DATA_THEME_SUBJECT}
        The skills should be diverse and cover various aspects and positions of the business.
        Always include English skill as language skill.
    """

    response = await openai.responses.parse(
        model=settings.DEFAULT_MODEL,
        input=[
            {"role": "system", "content": get_system_prompt()},
            {"role": "user", "content": user_prompt},
        ],
        text_format=SkillResponse,
        temperature=0.5,
    )

    if not response.output_parsed:
        logger.warning("No skills generated. Please generate again.")
        return

    skills: list[Skill] = response.output_parsed.skills

    if not skills:
        logger.warning("No skills generated. Please generate again.")
        return

    save_to_json([skill.model_dump() for skill in skills], settings.DATA_PATH.joinpath(FILENAME_TO_SAVE))

    logger.succeed(f"Generated {len(skills)} skills")
