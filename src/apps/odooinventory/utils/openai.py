from typing import TypeVar

from openai import AsyncOpenAI
from pydantic import BaseModel

from apps.odooinventory.config.settings import settings


openai = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)

T = TypeVar("T", bound=BaseModel)


def get_system_prompt() -> str:
    prompt = f"""
        You are an expert data generation assistant for a US-based Small to Medium-sized Enterprise (SME).
        Your specialization is creating realistic and high-quality synthetic data for business software, specifically for an Odoo Sales system.
        The data you generate should be related to the theme of '{settings.DATA_THEME_SUBJECT}'.
        Follow the user's instructions precisely to generate content that is plausible, coherent, and contextually appropriate for a US business environment.
        Ensure that all generated data adheres to the provided JSON schema.
    """
    return prompt
