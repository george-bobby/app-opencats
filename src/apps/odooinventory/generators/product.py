from apps.odooinventory.config.constants import PRODUCT_CATEGORIES
from apps.odooinventory.config.settings import settings
from apps.odooinventory.models.product import Product, ProductResponse
from apps.odooinventory.utils.openai import get_system_prompt, openai
from common.logger import logger
from common.save_to_json import save_to_json


FILENAME_TO_SAVE = "products.json"


async def generate_products(count: int | None = None):
    logger.start(f"Generating {count} products...")

    user_prompt = f"""
        Generate {count} realistic products for a US-based SME using an Odoo Inventory and Odoo Manufacturing system.
        
        Each product must have:
        - A name
        - A description
        - A list price (a price to sell the product)
        - A standard price (a cost to purchase the product or manufacture it)
        - A category (get from the list of categories in products: {PRODUCT_CATEGORIES})
        - Variants
            - A name
            - Display type
            - Values of the variant (e.g., color, size, etc.)
        - UOM (Unit of Measure)
    """
    response = await openai.responses.parse(
        model=settings.DEFAULT_MODEL,
        input=[
            {"role": "system", "content": get_system_prompt()},
            {"role": "user", "content": user_prompt},
        ],
        text_format=ProductResponse,
        temperature=0.7,
        max_output_tokens=settings.MAX_OUTPUT_TOKENS,
    )

    if not response.output_parsed:
        logger.warning("No products generated. Please generate again.")
        return

    products: list[Product] = response.output_parsed.products

    if not products:
        logger.warning("No products generated. Please generate again.")
        return

    save_to_json([product.model_dump() for product in products], settings.DATA_PATH.joinpath(FILENAME_TO_SAVE))

    logger.succeed(f"Generated {len(products)} products")
