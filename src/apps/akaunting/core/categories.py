import json

from pydantic import BaseModel, Field

from apps.akaunting.config.settings import settings
from apps.akaunting.models.categories import CategoryType
from apps.akaunting.utils import api
from apps.akaunting.utils.ai import aopenai
from common.logger import logger


class CategoryKeyInfo(BaseModel):
    name: str = Field(..., description="The name of category")
    type: CategoryType  # noqa: A003, RUF100


class ListCategoryKeyInfo(BaseModel):
    items: list[CategoryKeyInfo]


async def generate_categories(number: int = 5):
    existing_items_key_info = [
        {
            "name": item.name,
            "type": item.type,
        }
        for item in await api.list_categories()
    ]

    completion = await aopenai.beta.chat.completions.parse(
        model="gpt-4o-mini",
        messages=[
            {
                "role": "system",
                "content": "Generate JSON data for an accounting software",
            },
            {
                "role": "user",
                "content": f"""
                    Create data for ${number} categories of money for {settings.DATA_THEME_SUBJECT}.
                    Try to create data that is realistic.
                    Here is existing data, try not to create duplicates of the existing data:
                    ```json
                    {json.dumps(existing_items_key_info)}
                    ```
                """,
            },
        ],
        response_format=ListCategoryKeyInfo,
    )
    response = completion.choices[0].message.parsed
    if not response:
        raise Exception("Invalid GPT response")
    items = response.items
    return items


async def create_generated_categories(number: int = 5):
    try:
        items = await generate_categories(number)

        for item in items:
            logger.info(item)
            await api.add_category(item.name, item.type)

    finally:
        await api.close()


async def delete_generated_categories():
    try:
        categories = await api.list_categories()

        for category in categories:
            logger.info(category)
            if category.created_from == "core::api":
                try:
                    await api.delete_category(str(category.id))
                except Exception as e:
                    logger.warning(e)

    finally:
        await api.close()
