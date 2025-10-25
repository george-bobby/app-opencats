from apps.odoosales.config.settings import settings
from apps.odoosales.models.user import User, UserResponse
from apps.odoosales.utils.openai import get_system_prompt, openai
from common.logger import logger
from common.save_to_json import save_to_json


FILENAME_TO_SAVE = "users.json"


async def generate_users(count: int | None = None):
    if count is None:
        return

    logger.start(f"Generating {count} users...")

    user_prompt = f"""
        Generate {count} realistic users for a US-based SME using an Odoo Sales system.
        
        Each user should have a unique email address.
        The email address should be unique and not already used by any other user.
        The email address should be gmail.com or outlook.com.
    """
    response = await openai.responses.parse(
        model=settings.DEFAULT_MODEL,
        input=[
            {"role": "system", "content": get_system_prompt()},
            {"role": "user", "content": user_prompt},
        ],
        text_format=UserResponse,
        temperature=0.7,
    )

    if not response.output_parsed:
        logger.warning("No users generated. Please generate again.")
        return

    users: list[User] = response.output_parsed.users

    if not users:
        logger.warning("No users generated. Please generate again.")
        return

    save_to_json([user.model_dump() for user in users], settings.DATA_PATH.joinpath(FILENAME_TO_SAVE))

    logger.succeed(f"Generated {len(users)} users")
