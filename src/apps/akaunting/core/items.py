import json

from pydantic import BaseModel, Field

from apps.akaunting.config.settings import settings
from apps.akaunting.models.items import ItemType
from apps.akaunting.utils import api
from apps.akaunting.utils.ai import aopenai
from common.logger import logger


class ItemKeyInfo(BaseModel):
    name: str = Field(..., description="The name of the product or service")
    type: ItemType  # noqa: A003, RUF100
    description: str = Field(..., description="The description for the product or service")
    sale_price: float = Field(..., description="The price of the product or service that is up for sale")
    purchase_price: float = Field(..., description="The price of the product or service that is purchased")
    category_id: int = Field(..., description="The category id for this item. Each item usally has one category. The category has to make sense in the context of item")
    tax_ids: list[int] = Field(
        ...,
        description="""The tax ids for this item. 
        The tax should make sense for the item.
        There's should be from 1 to 2 taxes for an item, but mostly just 1. Don't forget VAT if exists.""",
    )


class ListItemKeyInfo(BaseModel):
    items: list[ItemKeyInfo]


async def generate_items(number: int = 5):
    existing_items_key_info = [
        {
            "name": item.name,
            "type": item.type,
            "description": item.description,
            "sale_price": item.sale_price,
        }
        for item in await api.list_items()
    ]
    existing_taxes = [
        {
            "id": tax.id,
            "name": tax.name,
            "rate": tax.rate,
        }
        for tax in await api.list_taxes()
    ]
    existing_categories = [
        {
            "id": category.id,
            "name": category.name,
            "type": category.type,
        }
        for category in await api.list_categories()
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
                    Create data purchasable products and services of {settings.DATA_THEME_SUBJECT}.
                    Try to create data that is realistic, unique and can be a bit niche.
                    Here the list of existing taxes:
                    ```json
                    {json.dumps(existing_taxes)}
                    ```
                    Here the list of expense categories:
                    ```json
                    {json.dumps(existing_categories)}
                    ```
                    Here is existing data, try not to create duplicates of the existing data:
                    ```json
                    {json.dumps(existing_items_key_info)}
                    ```
                    Remember to create exactly ${number} items.
                """,
            },
        ],
        response_format=ListItemKeyInfo,
    )
    response = completion.choices[0].message.parsed
    if not response:
        raise Exception("Invalid GPT response")
    items = response.items
    return items


async def create_generated_items(number: int = 5):
    try:
        items = await generate_items(number)

        for item in items:
            logger.info(item)
            await api.add_item(
                item.name,
                sale_price=item.sale_price,
                purchase_price=item.purchase_price,
                type=item.type,
                description=item.description,
                tax_ids=[str(tax_id) for tax_id in item.tax_ids],
                category_id=str(item.category_id),
            )

    finally:
        await api.close()


async def delete_generated_items():
    try:
        items = await api.list_items()

        for item in items:
            logger.info(item)
            if item.created_from == "core::api":
                try:
                    await api.delete_item(str(item.id))
                except Exception as e:
                    logger.warning(e)

    finally:
        await api.close()
