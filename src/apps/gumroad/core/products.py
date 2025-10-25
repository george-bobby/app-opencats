import asyncio
import json
import random
from pathlib import Path
from typing import Literal

from openai import AsyncOpenAI
from pydantic import BaseModel, Field

from apps.gumroad.config.settings import settings
from apps.gumroad.core.settings import get_all_taxonomies, get_profile_settings
from apps.gumroad.utils import PexelsAPI, faker, formatter
from apps.gumroad.utils.gumroad import GumroadAPI
from common.logger import logger


openai_client = AsyncOpenAI()

# Cache file path using settings.DATA_PATH
PRODUCTS_CACHE_FILE = settings.DATA_PATH / "generated" / "products.json"
PEXELS_CACHE_FILE = settings.DATA_PATH / "pexels.json"


class ProductCustomAttribute(BaseModel):
    name: str
    value: str


class Product(BaseModel):
    name: str
    price: int
    currency: str = "usd"
    description: str = Field(
        ...,
        description="The description of the product, use HTML tags to format the text",
    )
    is_physical: bool
    is_recurring: bool
    release_date: str | None
    release_time: str | None
    subscription_duration: Literal["monthly", "yearly"] | None
    product_type: Literal[
        "course",
        "ebook",
        "membership",
        "physical",
        "digital",
        "bundle",
        "call",
        "coffee",
    ]
    taxonomy_id: int
    require_shipping: bool
    price_cents: int
    customizable_price: bool
    custom_summary: str
    custom_attributes: list[ProductCustomAttribute]
    should_show_sales_count: bool
    quantity_enabled: bool
    max_purchase_count: int | None
    is_adult: bool
    display_product_reviews: bool
    custom_button_text_option: Literal[
        "i_want_this_prompt",
        "buy_this_prompt",
        "pay_prompt",
        "donate_prompt",
        "support_prompt",
        "tip_prompt",
    ]
    content: str = Field(
        ...,
        description="""The content of the product, meant for customer after they buy the product, use HTML tags to format the text.
        Talk about how to activate the product with the license key, what to do next, etc.
        """,
    )
    slug: str = Field(
        ...,
        description="The slug of the product, used for the product URL. It should be a unique and as short as possible.",
    )


class ProductTitleList(BaseModel):
    titles: list[str]


async def _generate_single_product(title: str):
    """Internal function to generate a single product using OpenAI"""
    taxonomies = await get_all_taxonomies()
    profile = await get_profile_settings()

    # Add variety to prevent identical descriptions
    styles = [
        "conversational and friendly",
        "professional and authoritative",
        "enthusiastic and energetic",
        "minimalist and direct",
        "storytelling and narrative",
    ]

    formats = [
        "bullet points with emojis",
        "short paragraphs with headers",
        "numbered lists",
        "mixed format with callouts",
        "FAQ-style benefits",
    ]

    chosen_style = random.choice(styles)
    chosen_format = random.choice(formats)

    response = await openai_client.beta.chat.completions.parse(
        model="gpt-4.1-mini-2025-04-14",
        messages=[
            {
                "role": "system",
                "content": f"You are an expert Gumroad product creator. Write in a {chosen_style} tone using {chosen_format} for the description.",
            },
            {
                "role": "user",
                "content": f"""
                Create a compelling product for: "{title}"
                
                Seller Profile: {profile}
                Taxonomies: {taxonomies}
                
                Requirements:
                • Description: 200-300 words, well-formatted HTML with proper tags
                • Include what buyers get, who it's for, key benefits
                • Content: Post-purchase instructions with license activation steps
                • Pricing: Set competitive price based on value and target market
                • Make each field unique and specific to this product
                
                Vary your approach - be creative with structure and don't follow a rigid template!
                """,
            },
        ],
        response_format=Product,
    )
    return response.choices[0].message.parsed


async def _generate_product_titles(number_of_titles: int):
    """Internal function to generate product titles using OpenAI"""
    profile = await get_profile_settings()
    generated_titles = []

    # Keep generating until we have enough unique titles
    while len(generated_titles) < number_of_titles:
        remaining = number_of_titles - len(generated_titles)
        batch_size = min(remaining + 5, 20)  # Generate a few extra to account for duplicates

        response = await openai_client.beta.chat.completions.parse(
            model="gpt-4.1-mini-2025-04-14",
            messages=[
                {
                    "role": "system",
                    "content": "You are a helper that creates data for Gumroad.",
                },
                {
                    "role": "user",
                    "content": f"""
                    Generate {batch_size} creative and engaging product titles for a Gumroad seller with this profile: {profile}
                    The titles should be:
                    - Catchy and memorable
                    - Clear about the product's value
                    - Optimized for search
                    - Between 5-20 words
                    - Professional and trustworthy
                    - Unique and different from each other
                    
                    Avoid duplicating these already generated titles: {generated_titles}
                    """,
                },
            ],
            response_format=ProductTitleList,
        )

        parsed_response = response.choices[0].message.parsed
        if parsed_response is None:
            logger.error("OpenAI API returned None for parsed response")
            continue

        new_titles = parsed_response.titles

        # Add unique titles only
        for title in new_titles:
            if title not in generated_titles and len(generated_titles) < number_of_titles:
                generated_titles.append(title)

        logger.info(f"Generated {len(generated_titles)}/{number_of_titles} titles so far")

    # Return a ProductTitleList object with the exact number requested
    return ProductTitleList(titles=generated_titles[:number_of_titles])


def _load_cached_pexels(query: str = "panoramic", orientation: str = "landscape") -> list[dict] | None:
    """Load cached Pexels images from JSON file"""
    try:
        if PEXELS_CACHE_FILE.exists():
            with Path.open(PEXELS_CACHE_FILE, encoding="utf-8") as f:
                data = json.load(f)
                # Check if we have cached data for this specific query and orientation
                cache_key = f"{query}_{orientation}"
                if data.get(cache_key) and data[cache_key].get("images"):
                    images = data[cache_key]["images"]
                    logger.info(f"Loaded {len(images)} cached Pexels images for query: {query}, orientation: {orientation}")
                    return images
    except (json.JSONDecodeError, FileNotFoundError) as e:
        logger.warning(f"Error loading cached Pexels images: {e}")
    return None


def _save_pexels_to_cache(images: list[dict], query: str = "panoramic", orientation: str = "landscape"):
    """Save Pexels images to JSON cache file"""
    try:
        # Ensure the data directory exists
        PEXELS_CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)

        cache_key = f"{query}_{orientation}"

        # Load existing cache data
        existing_data = {}
        if PEXELS_CACHE_FILE.exists():
            try:
                with Path.open(PEXELS_CACHE_FILE, encoding="utf-8") as f:
                    existing_data = json.load(f)
            except (json.JSONDecodeError, FileNotFoundError):
                existing_data = {}

        # Update with new data
        existing_data[cache_key] = {
            "images": images,
            "generated_at": faker.date_time().isoformat(),
            "count": len(images),
            "query": query,
            "orientation": orientation,
        }

        with Path.open(PEXELS_CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(existing_data, f, indent=2, ensure_ascii=False)

        logger.info(f"Saved {len(images)} Pexels images to cache for query: {query}, orientation: {orientation}")
    except Exception as e:
        logger.error(f"Error saving Pexels images to cache: {e}")


async def _get_pexels_images_from_cache_or_api(query: str = "panoramic", orientation: str = "landscape", min_ratio: float = 2.0) -> list[dict]:
    """Get Pexels images from cache if available, otherwise use API"""
    # If pexels.json exists, skip generation and use cached data
    if PEXELS_CACHE_FILE.exists():
        logger.info(f"Pexels cache file exists at {PEXELS_CACHE_FILE}, skipping generation")
        cached_images = _load_cached_pexels(query, orientation)
        if cached_images:
            # Filter cached images by aspect ratio
            filtered_images = [img for img in cached_images if img["width"] / img["height"] >= min_ratio]
            if filtered_images:
                logger.info(f"Using {len(filtered_images)} cached Pexels images (filtered by ratio >= {min_ratio})")
                return filtered_images
            else:
                logger.warning(f"No images meet ratio requirement >= {min_ratio}, using all cached images")
                return cached_images
        else:
            logger.warning("Pexels cache file exists but no images found for the specified query/orientation")

    # Generate new images if cache file doesn't exist or is empty
    logger.info(f"Fetching new Pexels images for query: {query}, orientation: {orientation}")
    async with PexelsAPI() as pexels:
        images = await pexels.get_random_photos(query=query, orientation=orientation)

        # Save to cache before filtering
        _save_pexels_to_cache(images, query, orientation)

        # Filter by aspect ratio
        filtered_images = [img for img in images if img["width"] / img["height"] >= min_ratio]
        logger.info(f"Fetched {len(images)} images, {len(filtered_images)} meet ratio requirement >= {min_ratio}")

        return filtered_images


async def generate_products(number_of_products: int):
    """
    Generate product data and save to JSON file in settings.DATA_PATH

    Args:
        number_of_products: Number of products to generate
    """
    logger.info(f"Generating {number_of_products} products...")

    # Start both title generation and image fetching concurrently
    logger.info("Starting concurrent generation of titles and images...")
    titles_task = _generate_product_titles(number_of_products)
    images_task = _get_pexels_images_from_cache_or_api(query="panoramic", orientation="landscape", min_ratio=2.0)

    # Wait for both to complete
    titles_response, images = await asyncio.gather(titles_task, images_task)
    product_titles = titles_response.titles

    # Generate product data for each title concurrently
    logger.info(f"Starting concurrent generation of {len(product_titles)} products...")
    product_tasks = [_generate_single_product(title) for title in product_titles]

    # Execute all product generation tasks concurrently
    products = await asyncio.gather(*product_tasks, return_exceptions=True)

    # Process results and handle any exceptions
    products_data = []
    for i, product in enumerate(products):
        if isinstance(product, Exception):
            logger.error(f"Error generating product '{product_titles[i]}': {product}")
            continue
        if product is None:
            logger.error(f"Product generation returned None for '{product_titles[i]}'")
            continue

        # Type guard: ensure product is a Product instance
        if not isinstance(product, Product):
            logger.error(f"Product generation returned unexpected type for '{product_titles[i]}': {type(product)}")
            continue

        try:
            products_data.append(product.model_dump())
        except Exception as e:
            logger.error(f"Error dumping product data for '{product_titles[i]}': {e}")
            continue

    # Prepare the final data structure
    output_data = {
        "products": products_data,
        "titles": product_titles,
        "images": images,
        "generated_at": faker.date_time().isoformat(),
        "count": len(products_data),
    }

    # Ensure the data directory exists
    PRODUCTS_CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)

    # Save to JSON file
    with Path.open(PRODUCTS_CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(output_data, f, indent=2, ensure_ascii=False)

    logger.info(f"Successfully generated and saved {len(products_data)} products to {PRODUCTS_CACHE_FILE}")
    return output_data


async def seed_products():
    """
    Insert product data from JSON file into Gumroad
    """
    logger.start("Starting product seeding from JSON file...")

    # Load product data from JSON file
    if not PRODUCTS_CACHE_FILE.exists():
        raise FileNotFoundError(f"Products file not found at {PRODUCTS_CACHE_FILE}. Run generate_product() first.")

    with Path.open(PRODUCTS_CACHE_FILE, encoding="utf-8") as f:
        data = json.load(f)

    products_data = data.get("products", [])
    images = data.get("images", [])

    if not products_data:
        raise ValueError("No products found in the JSON file")

    logger.start(f"Seeding {len(products_data)} products to Gumroad")

    # Create products in Gumroad concurrently
    async with GumroadAPI() as gumroad:
        # Create all product creation tasks
        product_tasks = [_create_single_product_in_gumroad(product_data, images, gumroad) for product_data in products_data]

        # Execute all product creation tasks concurrently
        logger.info(f"Starting concurrent creation of {len(product_tasks)} products...")
        results = await asyncio.gather(*product_tasks, return_exceptions=True)

        # Process results and handle any exceptions
        processed_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                error_msg = str(result)
                product_name = products_data[i]["name"]
                logger.error(f"Error creating product {product_name}: {error_msg}")
                processed_results.append({"success": False, "error": error_msg, "title": product_name})
            elif result is None:
                product_name = products_data[i]["name"]
                logger.error(f"Product creation returned None for {product_name}")
                processed_results.append({"success": False, "error": "Product creation returned None", "title": product_name})
            else:
                # Type guard: ensure result is a dictionary
                if not isinstance(result, dict):
                    product_name = products_data[i]["name"]
                    logger.error(f"Product creation returned unexpected type for {product_name}: {type(result)}")
                    processed_results.append({"success": False, "error": f"Unexpected result type: {type(result)}", "title": product_name})
                    continue

                processed_results.append(result)
                if result.get("success"):
                    logger.info(f"Successfully created product: {result.get('title')}")
                else:
                    logger.error(f"Failed to create product: {result.get('title')} - {result.get('error')}")

        results = processed_results

        # Summary
        successful = sum(1 for r in results if r.get("success"))
        failed = len(results) - successful

        logger.succeed(f"Product seeding completed: {successful} successful, {failed} failed")
        return {"successful": successful, "failed": failed, "results": results}


async def _create_single_product_in_gumroad(product_data: dict, images: list[dict], gumroad: GumroadAPI):
    """Create a single product in Gumroad with all its components"""
    try:
        title = product_data["name"]

        # Create the basic product
        response = await gumroad.add_product(
            name=title,
            price="100",  # Price must be a string
        )

        # Check if product creation was successful
        if not response.get("product_id"):
            error_msg = f"Failed to create product '{title}': {response.get('error', 'No product_id in response')}"
            logger.error(error_msg)
            logger.error(f"Full response: {response}")
            return {"success": False, "error": error_msg, "title": title}

        product_id = response["product_id"]

        # Add cover photos (non-blocking)
        cover_photos = faker.random_elements(images, length=6)
        cover_tasks = []
        for cover_photo in cover_photos:
            cover_tasks.append(
                gumroad.add_product_cover(
                    product_id=product_id,
                    cover_url=cover_photo["src"]["original"],
                )
            )

        # Execute cover photo uploads concurrently
        cover_results = await asyncio.gather(*cover_tasks, return_exceptions=True)
        for i, result in enumerate(cover_results):
            if isinstance(result, Exception):
                logger.warning(f"Cannot add cover photo {i}: {result}")

        # Convert product_data to Product object
        product = Product(**product_data)

        content = formatter.convert_html_to_rich_content(product.content)
        content = formatter.add_license_key(content)

        # Update product details
        await gumroad.update_product_details(
            product_id=product_id,
            product_details={
                "name": product.name,
                "description": product.description,
                "price": product.price,
                "currency": product.currency,
                "is_physical": product.is_physical,
                "is_recurring": product.is_recurring,
                "release_date": product.release_date,
                "release_time": product.release_time,
                "native_type": product.product_type,
                "taxonomy_id": product.taxonomy_id,
                "require_shipping": product.require_shipping,
                "price_cents": product.price_cents,
                "customizable_price": product.customizable_price,
                "custom_summary": product.custom_summary,
                "custom_attributes": [attr.model_dump() for attr in product.custom_attributes],
                "custom_button_text_option": product.custom_button_text_option,
                "rich_content": content,
                "custom_permalink": product.slug,
            },
        )

        # Publish the product
        await gumroad.publish_product(product_id=product_id)
        logger.info(f"Successfully completed product: {title} (ID: {product_id})")

        return {
            "success": True,
            "product_id": product_id,
            "title": title,
            "product_data": product_data,
        }

    except Exception as e:
        logger.error(f"Error creating product '{title}': {e}")
        return {"success": False, "error": str(e), "title": title}
