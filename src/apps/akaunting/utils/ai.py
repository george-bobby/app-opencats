from openai import AsyncOpenAI

from apps.akaunting.config.settings import settings


aopenai = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
