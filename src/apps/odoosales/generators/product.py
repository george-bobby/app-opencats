from apps.odoosales.config.settings import settings
from apps.odoosales.models.product import Product, ProductResponse
from apps.odoosales.utils.openai import get_system_prompt, openai
from common.logger import logger
from common.save_to_json import save_to_json


PRODUCT_FILENAME_TO_SAVE = "products.json"


async def generate_products(n_products: int | None = None):
    if n_products is None:
        return

    logger.start(f"Generating {n_products} products...")

    user_prompt = f"""
        Generate exactly {n_products} products for a SME company in Consumer Goods & Retail industry based in USA.
        The products should be diverse and unique, covering a wide range of categories.
        The products should be realistic and could exist in the USA market.
        Each product should have the following attributes:
        - name: Name of the product. Should be generic, descriptive and unique. Using popular product names is recommended. Avoid using brand names or specific product lines.
        - description: Summary description of the product. Should be concise and informative. No more than 100 words
        - description_picking: Description of the product for internal transfer operations. Should be concise and informative. No more than 100 words.
        - description_pickingin: Description of the product for receiving operations. Should be concise and informative. No more than 100 words.
        - description_pickingout: Description of the product for picking operations. Should be concise and informative. No more than 100 words.
        - description_purchase: Description of the product for purchase operations. Should be concise and informative. No more than 100 words.
        - description_sale: Description of the product for sale operations. Should be concise and informative. No more than 100 words
        - type: Type of the product. Choose from the following options:
          - 'consu': For consumable products that can be sold.
          - 'service': For services that can be sold.
          Use 'consu' for physical products that can be sold. Use 'service' for services that can be sold.
          Default to 'consu'.
        - list_price: Price of the product in USD. Give a realistic price for the product.
        - cost: Cost of the product in USD. This is the cost to the store, not the selling price.
        - category: Category of the product. Should be relevant to the product name and description.
          Choose from the following categories:
          - Home Essentials
          - Electronics
          - Apparel
          - Health & Beauty
          - Office Supplies
          - Gift Sets & Bundles
        - variants: List of product variants base on provided attributes
        - tags: List of product tags. Tags should be relevant to the product name and description.
          Use popular and realistic tag names. Each product should have at least 2 tags.
        - uom: The unit of measure for the product.
    """
    response = await openai.responses.parse(
        model=settings.DEFAULT_MODEL,
        input=[
            {"role": "system", "content": get_system_prompt()},
            {"role": "user", "content": user_prompt},
        ],
        text_format=ProductResponse,
        temperature=0.7,
    )

    if not response.output_parsed:
        logger.warning("No products generated. Please generate again.")
        return

    products: list[Product] = response.output_parsed.products

    if not products:
        logger.warning("No products generated. Please generate again.")
        return

    save_to_json([product.model_dump() for product in products], settings.DATA_PATH.joinpath(PRODUCT_FILENAME_TO_SAVE))

    logger.succeed(f"Generated {len(products)} products")
