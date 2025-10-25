import asyncio
import json
import random
from datetime import datetime
from typing import Any

from apps.spree.config.settings import settings
from apps.spree.utils.constants import IMAGE_TAG_PLACEHOLDER, IMAGES_FILE
from apps.spree.utils.pexels import PexelsAPI
from common.logger import logger


def load_image_cache() -> dict:
    """Load existing image cache from JSON file."""
    try:
        if IMAGES_FILE.exists():
            with IMAGES_FILE.open("r", encoding="utf-8") as f:
                cache_data = json.load(f)
                # Ensure proper structure
                if "cache" not in cache_data:
                    cache_data["cache"] = {}
                return cache_data
    except Exception as e:
        logger.warning(f"Failed to load image cache: {e}")

    # Return default structure if file doesn't exist or fails to load
    return {"cache": {}, "generated_at": ""}


def save_image_cache(cache_data: dict) -> None:
    """Save image cache to JSON file."""
    try:
        IMAGES_FILE.parent.mkdir(parents=True, exist_ok=True)
        with IMAGES_FILE.open("w", encoding="utf-8") as f:
            json.dump(cache_data, f)
        logger.info(f"Image cache saved to {IMAGES_FILE}")
    except Exception as e:
        logger.error(f"Failed to save image cache: {e}")


def clear_image_cache() -> None:
    """Clear image cache."""
    IMAGES_FILE.unlink(missing_ok=True)
    logger.info("Image cache cleared")


async def generate_product_images(product: dict, image_cache: dict) -> dict | None:
    """Generate images data for a single product using Pexels API with caching."""

    product_id = product.get("id")
    product_name = product.get("name", "Unknown")
    image_keywords = product.get("image_keywords", [])
    variants = product.get("variants", [])

    if not image_keywords:
        logger.warning(f"No image keywords found for product {product_id}: {product_name}")
        return None

    # Check cache first
    cache_key = product_id
    if cache_key in image_cache["cache"]:
        cached_data = image_cache["cache"][cache_key]
        if cached_data and cached_data.get("search_query") == " ".join(image_keywords):
            logger.info(f"Using cached Pexels data for product {product_id}")
            # Process cached raw data into images
            return process_pexels_data_to_images(cached_data, product_name)

    try:
        async with PexelsAPI(api_keys=settings.PEXELS_API_KEYS) as pexels:
            # Create the best possible search query with available keywords
            search_query = " ".join(image_keywords)

            # Calculate needed photos: master images + variant images
            needed_photos = 3 + len(variants) * 2 if variants else 3  # 3 main + 2 per variant

            # Make single API call
            result = await pexels.search_photos(
                query=search_query,
                per_page=min(needed_photos + 2, 30),  # Get extra for variety, max 30 per page
                orientation="landscape",
            )

            # Extract photos from the search result
            photos = []
            if result and result.get("status_code") == 200 and result.get("photos"):
                photos = result["photos"]

            if not photos:
                logger.warning(f"No photos found for query: '{search_query}' for product {product_id}")
                return None

            # Cache the complete raw Pexels response
            raw_pexels_data = {
                "product_id": product_id,
                "product_name": product_name,
                "search_query": search_query,
                "attempted_keywords": image_keywords,
                "pexels_response": result,
                "raw_photos": photos,
                "cached_at": str(datetime.now()),
            }

            image_cache["cache"][cache_key] = raw_pexels_data

            return process_pexels_data_to_images(raw_pexels_data, product_name)

    except Exception as e:
        logger.error(f"Failed to generate images for product {product_id}: {e}")
        return None


def process_pexels_data_to_images(pexels_data: dict, product_name: str) -> dict | None:
    """Process raw Pexels data into structured image data for seeding."""

    photos = pexels_data.get("raw_photos", [])
    if not photos:
        return None

    # Process photos to extract only the needed image data
    processed_photos = []
    for photo in photos:
        processed_photo = {
            "url": photo.get("src", {}).get("large", ""),
            "alt": photo.get("alt", f"{product_name} image"),
            "width": photo.get("width"),
            "height": photo.get("height"),
        }
        if processed_photo["url"]:  # Only include if we have a valid URL
            processed_photos.append(processed_photo)

    # Create structure expected by seed_product_images_direct
    # Distribute photos between main_images and variant_images
    main_images = []
    variant_images = {}

    if processed_photos:
        # First 3 photos go to main_images
        main_images = processed_photos[:3]

        # Remaining photos go to variant_images (position 1)
        remaining_photos = processed_photos[3:]
        if remaining_photos:
            variant_images["1"] = remaining_photos

    # Return structure expected by seed_product_images_direct
    return {
        "product_id": pexels_data.get("product_id"),
        "product_name": product_name,
        "search_query": pexels_data.get("search_query"),
        "main_images": main_images,
        "variant_images": variant_images,
        "cached_at": pexels_data.get("cached_at"),
    }


async def generate_images_for_products_batch(products: list[dict], max_concurrent: int = 4) -> dict[str, Any]:
    """Generate images data for a batch of products concurrently with caching."""

    if not products:
        return {"images": {}}

    # Load existing cache
    image_cache = load_image_cache()
    logger.info(f"Loaded image cache with {len(image_cache.get('cache', {}))} cached products")

    async def process_single_product(product: dict) -> tuple[str, dict | None]:
        """Process a single product."""
        try:
            # Add small delay to avoid rate limiting
            await asyncio.sleep(random.uniform(1, 5))

            product_id = str(product.get("id"))
            result = await generate_product_images(product, image_cache)
            return product_id, result
        except Exception as e:
            product_id = str(product.get("id", "unknown"))
            logger.error(f"Failed to process product {product_id}: {e}")
            return product_id, None

    # Process products in batches to respect concurrency limit
    logger.info(f"Generating images for {len(products)} products in batches of {max_concurrent}...")

    images_data = {"images": {}}
    successful_products = 0
    failed_products = 0

    for i in range(0, len(products), max_concurrent):
        batch = products[i : i + max_concurrent]
        batch_number = (i // max_concurrent) + 1
        total_batches = (len(products) + max_concurrent - 1) // max_concurrent

        logger.info(f"Processing batch {batch_number}/{total_batches} ({len(batch)} products)...")

        # Create tasks for this batch
        tasks = [process_single_product(product) for product in batch]

        # Execute this batch concurrently
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Process batch results
        for result in results:
            if isinstance(result, Exception):
                failed_products += 1
                logger.error(f"Product image generation failed: {result}")
            elif isinstance(result, tuple):
                product_id, product_images = result
                if product_images is not None:
                    images_data["images"][product_id] = product_images
                    successful_products += 1
                else:
                    failed_products += 1

        # Small delay between batches to be respectful
        if i + max_concurrent < len(products):
            await asyncio.sleep(1)

    # Save updated cache
    image_cache["generated_at"] = str(datetime.now())
    save_image_cache(image_cache)

    logger.info(f"Image generation completed: {successful_products} successful, {failed_products} failed")
    logger.info(f"Cache now contains {len(image_cache.get('cache', {}))} products")

    return images_data


def replace_image_placeholders_in_descriptions(products_data: dict) -> dict:
    """Replace IMAGE_TAG_PLACEHOLDER with actual image tags using product's own images."""

    for product in products_data.get("products", []):
        description = product.get("description", "")
        images = product.get("images", {})

        if not description or not images:
            continue

        # Get all available photos from main_images and variant_images
        all_photos = []

        # Add main images
        main_images = images.get("main_images", [])
        all_photos.extend(main_images)

        # Add variant images
        variant_images = images.get("variant_images", {})
        for variant_image_list in variant_images.values():
            if isinstance(variant_image_list, list):
                all_photos.extend(variant_image_list)
            else:
                all_photos.append(variant_image_list)

        if not all_photos:
            continue

        # Count how many placeholders we need to replace
        placeholder_count = description.count(IMAGE_TAG_PLACEHOLDER)

        if placeholder_count == 0:
            continue

        # Create a copy of photos to avoid modifying the original list
        available_photos = all_photos.copy()

        # Replace each placeholder with an image tag
        for _ in range(placeholder_count):
            if not available_photos:
                # If we run out of photos, refill from original list
                available_photos = all_photos.copy()

            # Randomly select one photo from available photos
            photo = random.choice(available_photos)
            # Remove the selected photo from available photos to avoid reuse
            available_photos.remove(photo)

            # Get the URL and alt text
            url = photo.get("url", "")
            alt_text = photo.get("alt", f"{product.get('name', 'Product')} image")

            if url:
                img_tag = f'<br>  <img src="{url}" alt="{alt_text}" class="product-image" loading="lazy" style="width: 100%; padding-bottom: 1rem" /><br>  '
                description = description.replace(IMAGE_TAG_PLACEHOLDER, img_tag, 1)

        # Update the product description
        product["description"] = description

    return products_data
