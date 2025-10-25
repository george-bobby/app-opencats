import asyncio
import base64
import hashlib
import json
import random
import secrets
import sys
import time
from datetime import datetime
from pathlib import Path

import aiofiles
import aiohttp

from apps.spree.config.settings import settings
from apps.spree.utils.constants import (
    IMAGE_TAG_PLACEHOLDER,
    PRODUCTS_FILE,
)
from apps.spree.utils.database import db_client
from apps.spree.utils.pexels import PexelsAPI
from common.logger import logger


MAX_CONCURRENT_IMAGE_REQUESTS = settings.MAX_CONCURRENT_GENERATION_REQUESTS


class DirectImageSeeder:
    """High-performance image seeder that bypasses Rails completely."""

    def __init__(self, storage_path: str = "src/apps/spree/docker/storage"):
        """Initialize the direct image seeder.

        Args:
                storage_path: Path to Active Storage directory (host-side path)
        """
        self.storage_path = storage_path
        self.session: aiohttp.ClientSession | None = None

    async def __aenter__(self):
        """Async context manager entry."""

        # Create session
        self.session = aiohttp.ClientSession()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        if self.session:
            await self.session.close()

    def _generate_storage_key(self) -> str:
        """Generate a unique storage key for Active Storage."""
        return secrets.token_hex(16)

    def _get_storage_path_for_key(self, key: str) -> str:
        """Get the full storage path for a given key.

        Args:
            key: Storage key

        Returns:
            Full path to storage file
        """
        # Active Storage uses first 2 characters as directory
        prefix = key[:2]
        middle = key[2:4]
        return f"{self.storage_path}/{prefix}/{middle}/{key}"

    async def _download_image_to_storage(self, url: str, storage_key: str) -> tuple[int, str, str]:
        """Download image directly to storage location and calculate MD5 checksum.

        Args:
                    url: Image URL to download
                    storage_key: Generated storage key

        Returns:
                    tuple: (file_size, original_filename, md5_checksum)
        """
        if not self.session:
            raise RuntimeError("Session not initialized. Use async context manager.")

        storage_file_path = self._get_storage_path_for_key(storage_key)

        # Create directory structure
        Path(storage_file_path).parent.mkdir(parents=True, exist_ok=True)

        async with self.session.get(url) as response:
            response.raise_for_status()

            # Get original filename from URL or Content-Disposition
            original_filename = url.split("/")[-1].split("?")[0]
            if "." not in original_filename:
                content_type = response.headers.get("content-type", "image/jpeg")
                ext = "jpg" if "jpeg" in content_type else content_type.split("/")[-1]
                original_filename = f"{storage_key}.{ext}"

            # Write file directly to storage and calculate MD5 checksum
            if aiofiles is None:
                raise ImportError("aiofiles package is required for direct image seeding. Install with: pip install aiofiles")

            md5_hash = hashlib.md5()
            file_size = 0

            async with aiofiles.open(storage_file_path, "wb") as f:
                async for chunk in response.content.iter_chunked(8192):
                    await f.write(chunk)
                    md5_hash.update(chunk)
                    file_size += len(chunk)

            # Convert MD5 hash to base64 (Rails format)
            checksum = base64.b64encode(md5_hash.digest()).decode("ascii")

        return file_size, original_filename, checksum

    async def _insert_blob_record(self, storage_key: str, filename: str, file_size: int, checksum: str, content_type: str = "image/jpeg") -> int:
        """Insert Active Storage blob record directly with checksum.

        Args:
            storage_key: Generated storage key
            filename: Original filename
            file_size: Size of file in bytes
            checksum: MD5 checksum in base64 format
            content_type: MIME content type

        Returns:
            blob_id: ID of inserted blob record
        """
        # Minimal metadata - no analysis needed since we're providing checksum
        metadata = json.dumps({"identified": True, "analyzed": True})

        blob_id = await db_client.fetchval(
            """
            INSERT INTO active_storage_blobs (
                key, filename, content_type, metadata, service_name, byte_size, checksum, created_at
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
            RETURNING id
            """,
            storage_key,
            filename,
            content_type,
            metadata,
            "local",
            file_size,
            checksum,
            datetime.utcnow(),
        )

        if blob_id is None:
            raise RuntimeError("Failed to insert blob record")
        return int(blob_id)

    async def _insert_spree_asset(self, variant_id: int, alt_text: str, position: int) -> int:
        """Insert Spree asset record.

        Args:
            variant_id: Spree variant ID to attach to
            alt_text: Alt text for accessibility
            position: Position/order of the image

        Returns:
            asset_id: ID of inserted asset record
        """
        asset_id = await db_client.fetchval(
            """
            INSERT INTO spree_assets (
                viewable_type, viewable_id, type, alt, position, created_at, updated_at
            ) VALUES ($1, $2, $3, $4, $5, $6, $7)
            RETURNING id
            """,
            "Spree::Variant",
            variant_id,
            "Spree::Image",
            alt_text,
            position,
            datetime.utcnow(),
            datetime.utcnow(),
        )

        if asset_id is None:
            raise RuntimeError("Failed to insert asset record")
        return int(asset_id)

    async def _insert_attachment_record(self, asset_id: int, blob_id: int) -> int:
        """Insert Active Storage attachment record.

        Args:
            asset_id: Spree asset ID
            blob_id: Active Storage blob ID

        Returns:
            attachment_id: ID of inserted attachment record
        """
        attachment_id = await db_client.fetchval(
            """
            INSERT INTO active_storage_attachments (
                name, record_type, record_id, blob_id, created_at
            ) VALUES ($1, $2, $3, $4, $5)
            RETURNING id
            """,
            "attachment",
            "Spree::Asset",
            asset_id,
            blob_id,
            datetime.utcnow(),
        )

        if attachment_id is None:
            raise RuntimeError("Failed to insert attachment record")
        return int(attachment_id)

    async def seed_single_image(self, variant_id: int, image_url: str, alt_text: str, position: int) -> bool:
        """Seed a single image directly to storage and database.

        Args:
            variant_id: Spree variant ID
            image_url: URL of image to download
            alt_text: Alt text for accessibility
            position: Position/order of the image

        Returns:
            bool: Success status
        """
        try:
            # Generate unique storage key
            storage_key = self._generate_storage_key()

            # Download image directly to storage and calculate checksum
            file_size, filename, checksum = await self._download_image_to_storage(image_url, storage_key)

            # Insert database records in order
            blob_id = await self._insert_blob_record(storage_key, filename, file_size, checksum)
            asset_id = await self._insert_spree_asset(variant_id, alt_text, position)
            attachment_id = await self._insert_attachment_record(asset_id, blob_id)

            return True
            logger.debug(f"✅ Direct seeded image: blob_id={blob_id}, asset_id={asset_id}, attachment_id={attachment_id}, checksum={checksum[:8]}...")

        except Exception as e:
            logger.error(f"❌ Failed to seed image for variant {variant_id}: {e}")
            return False

    async def seed_product_images_direct(
        self,
        product_id: int,
        product_images: dict,
        processed_images: list | None = None,
        failed_images: list | None = None,
        total_images: int = 0,
        start_time: float = 0,
    ) -> tuple[int, int]:
        """Seed all images for a single product directly.

        Args:
            product_id: Spree product ID
            product_images: Product image data from images.json
            processed_images: Shared counter for successfully processed images
            failed_images: Shared counter for failed images
            total_images: Total number of images to process (for progress calculation)
            start_time: Start time for rate calculation

        Returns:
            tuple: (success_count, total_count)
        """
        # Get all variant IDs for this product from database
        variants = await db_client.fetch(
            """
            SELECT id, position, is_master 
            FROM spree_variants 
            WHERE product_id = $1 
            ORDER BY position
            """,
            product_id,
        )

        if not variants:
            logger.warning(f"No variants found for product {product_id}")
            return 0, 0

        # Create mapping of position to variant_id
        variant_id_map = {}
        master_variant_id = None

        for variant in variants:
            if variant["is_master"]:
                master_variant_id = variant["id"]
            else:
                # Non-master variants: position 2,3,4... map to our image positions 1,2,3...
                image_position = variant["position"] - 1
                variant_id_map[image_position] = variant["id"]

        success_count = 0
        total_count = 0

        # Process variant-specific images
        variant_images = product_images.get("variant_images", {})
        for position_str, variant_image_list in variant_images.items():
            position = int(position_str)

            if position not in variant_id_map:
                logger.debug(f"No variant found for position {position}, skipping")
                continue

            variant_id = variant_id_map[position]

            # Handle both list and single image formats
            images_to_process = variant_image_list if isinstance(variant_image_list, list) else [variant_image_list]

            for img_idx, img in enumerate(images_to_process):
                url = img.get("url")
                if not url:
                    continue

                # Generate meaningful alt text based on product context
                product_name = product_images.get("product_name", f"Product {product_id}")
                variant_sku = img.get("sku_suffix", f"Variant {position}")
                if img_idx == 0:
                    alt_text = f"{product_name} - {variant_sku.replace('-', ' ').title()} variant"
                else:
                    alt_text = f"{product_name} - {variant_sku.replace('-', ' ').title()} variant image {img_idx + 1}"
                image_position = img_idx + 1  # Start at position 1

                success = await self.seed_single_image(variant_id, url, alt_text, image_position)
                total_count += 1
                if success:
                    success_count += 1
                    if processed_images is not None:
                        processed_images[0] += 1
                else:
                    if failed_images is not None:
                        failed_images[0] += 1

                # Show progress every 10 images or so
                if processed_images is not None and failed_images is not None and (processed_images[0] + failed_images[0]) % 10 == 0:
                    self._log_progress(processed_images[0], failed_images[0], total_images, start_time)

        # Process main images (attach to master variant or first variant)
        main_images = product_images.get("main_images", [])
        if main_images:
            # Prefer variant position 1 for main images, fallback to master
            target_variant_id = variant_id_map.get(1, master_variant_id)

            for idx, img in enumerate(main_images):
                url = img.get("url")
                if not url:
                    continue

                # Generate meaningful alt text based on product context
                product_name = product_images.get("product_name", f"Product {product_id}")
                alt_text = f"{product_name} - Main product image" if idx == 0 else f"{product_name} - Product image {idx + 1}"
                # Start main images after variant images
                max_variant_position = max([1] + [len(variant_images.get(str(p), [])) for p in variant_id_map])
                image_position = max_variant_position + idx + 1

                success = await self.seed_single_image(target_variant_id, url, alt_text, image_position)
                total_count += 1
                if success:
                    success_count += 1
                    if processed_images is not None:
                        processed_images[0] += 1
                else:
                    if failed_images is not None:
                        failed_images[0] += 1

                # Show progress every 10 images or so
                if processed_images is not None and failed_images is not None and (processed_images[0] + failed_images[0]) % 10 == 0:
                    self._log_progress(processed_images[0], failed_images[0], total_images, start_time)

        return success_count, total_count

    def _log_progress(self, processed: int, failed: int, total: int, start_time: float) -> None:
        """Log current progress with statistics."""
        if total == 0:
            return

        completed = processed + failed
        percentage = (completed / total) * 100
        elapsed_time = time.time() - start_time

        if elapsed_time > 0:
            rate = processed / elapsed_time
            eta_seconds = (total - completed) / rate if rate > 0 else 0
            eta_minutes = eta_seconds / 60

            progress_line = f"\rProgress: {completed}/{total} images ({percentage:.1f}%) | ✅ {processed} success | ❌ {failed} failed | ⚡ {rate:.1f}/s | ETA: {eta_minutes:.1f}m"
            sys.stdout.write(progress_line)
            sys.stdout.flush()


async def seed_images_for_products(max_concurrent: int = 32) -> None:
    """
    High-performance image seeding using direct database/storage manipulation.

    This function provides 10-50x performance improvement over the API approach by:
    - Bypassing all Rails processing and Active Storage analysis
    - Writing files directly to storage directories
    - Inserting database records directly
    - Using higher concurrency limits
    - Calculating proper MD5 checksums for data integrity

    Args:
        max_concurrent: Maximum concurrent product processing (can be higher than API approach)
    """

    # Load products data with embedded images
    if not PRODUCTS_FILE.exists():
        logger.error(f"Products file not found at {PRODUCTS_FILE}")
        raise FileNotFoundError("Products file not found. Run generate command first.")

    with Path.open(PRODUCTS_FILE, encoding="utf-8") as f:
        products_data = json.load(f)

    products = products_data.get("products", [])
    if not products:
        logger.warning("No products found in products.json")
        return

    # Filter products that have image data
    products_with_images = []
    for product in products:
        if product.get("images"):
            products_with_images.append(product)

    if not products_with_images:
        logger.warning("No products with image data found in products.json")
        return

    logger.info(f"Found {len(products_with_images)} products with image data to seed")

    # Count total images for progress tracking
    total_images = 0
    for product in products_with_images:
        product_images = product["images"]
        main_images = product_images.get("main_images", [])
        variant_images = product_images.get("variant_images", {})

        total_images += len(main_images)
        for variant_image_list in variant_images.values():
            if isinstance(variant_image_list, list):
                total_images += len(variant_image_list)
            else:
                total_images += 1

    logger.info(f"Total images to seed: {total_images}")

    # Shared progress tracking (using lists for thread-safe mutable state)
    processed_images = [0]  # Images successfully processed
    failed_images = [0]  # Images that failed to process
    start_time = time.time()

    # Create semaphore to limit concurrent processing
    semaphore = asyncio.Semaphore(max_concurrent)

    async def process_single_product(product: dict) -> tuple[int, int]:
        """Process a single product's images with semaphore limiting and progress tracking."""
        async with semaphore:
            product_id = product["id"]
            product_images = product["images"]
            async with DirectImageSeeder() as seeder:
                result = await seeder.seed_product_images_direct(product_id, product_images, processed_images, failed_images, total_images, start_time)
                return result

    # Create tasks for all products with images
    tasks = [process_single_product(product) for product in products_with_images]

    # Process all products concurrently
    results = await asyncio.gather(*tasks, return_exceptions=True)

    total_success = 0
    total_processed = 0
    failed_products = 0

    for i, result in enumerate(results):
        if isinstance(result, Exception):
            failed_products += 1
            product_id = products_with_images[i]["id"] if i < len(products_with_images) else "unknown"
            logger.error(f"Product {product_id} processing failed: {result}")
        elif isinstance(result, tuple):
            success_count, total_count = result
            total_success += success_count
            total_processed += total_count
        else:
            failed_products += 1

    logger.info(f"✅ Successfully seeded {total_success}/{total_processed} images")
    if failed_products > 0:
        logger.warning(f"  ❌ Failed products: {failed_products}")

    if total_success != total_processed:
        logger.warning(f"  ❌ Failed images: {total_processed - total_success}")


# Image generation helper functions
def _analyze_variant_importance(variant: dict, variant_idx: int, total_variants: int) -> float:
    """
    Analyze variant characteristics to determine its relative importance.
    Returns a score between 0.5 and 1.5 where higher = more important.
    """
    base_score = 1.0
    sku_suffix = variant.get("sku_suffix", "").lower()

    # Position-based scoring (earlier positions slightly more important)
    position_bonus = max(0, (total_variants - variant_idx) * 0.05)

    # SKU-based importance analysis
    importance_indicators = {
        # Size importance (larger sizes often more popular)
        "xl": 0.2,
        "xxl": 0.2,
        "large": 0.15,
        "lg": 0.15,
        "medium": 0.1,
        "md": 0.1,
        "small": 0.05,
        "sm": 0.05,
        # Color popularity (neutral colors often more popular)
        "black": 0.15,
        "white": 0.15,
        "blue": 0.1,
        "navy": 0.1,
        "red": 0.05,
        "green": 0.05,
        "pink": 0.02,
        "yellow": 0.02,
        # Material quality indicators
        "premium": 0.2,
        "deluxe": 0.15,
        "standard": 0.0,
        "basic": -0.1,
        "cotton": 0.1,
        "leather": 0.15,
        "silk": 0.1,
        "nylon": 0.05,
    }

    # Apply bonuses based on SKU content
    sku_bonus = sum(bonus for keyword, bonus in importance_indicators.items() if keyword in sku_suffix)

    # Normalize final score
    final_score = base_score + position_bonus + sku_bonus
    return max(0.5, min(1.5, final_score))  # Clamp between 0.5 and 1.5


def _calculate_intelligent_variant_distribution(variants: list[dict], available_photos: int, min_images: int, max_images: int) -> list[int]:
    """
    Intelligently distribute available photos across variants based on importance.
    Returns list of image counts for each variant.
    """
    if not variants or available_photos <= 0:
        return [0] * len(variants)

    # Calculate importance scores for each variant
    importance_scores = [_analyze_variant_importance(variant, idx, len(variants)) for idx, variant in enumerate(variants)]

    # Calculate total weighted importance
    total_importance = sum(importance_scores)

    # Distribute images based on importance, ensuring minimums
    distribution = []
    remaining_photos = available_photos

    # First pass: ensure minimum images for each variant
    for _ in range(len(importance_scores)):
        min_allocation = min(min_images, remaining_photos // len(variants), remaining_photos)
        distribution.append(min_allocation)
        remaining_photos -= min_allocation

    # Second pass: distribute remaining photos based on importance
    if remaining_photos > 0:
        for idx, score in enumerate(importance_scores):
            if remaining_photos <= 0:
                break

            # Calculate bonus images based on importance
            weight = score / total_importance
            bonus_images = int(remaining_photos * weight)

            # Respect maximum limits
            current_total = distribution[idx] + bonus_images
            max_allowed = min(max_images, remaining_photos + distribution[idx])
            final_allocation = min(current_total, max_allowed)

            bonus_to_add = final_allocation - distribution[idx]
            distribution[idx] += bonus_to_add
            remaining_photos -= bonus_to_add

    # Final pass: distribute any remaining photos to highest importance variants
    while remaining_photos > 0:
        allocated = False
        for idx in sorted(range(len(variants)), key=lambda i: importance_scores[i], reverse=True):
            if distribution[idx] < max_images and remaining_photos > 0:
                distribution[idx] += 1
                remaining_photos -= 1
                allocated = True
                break
        if not allocated:  # Safety break if no variant can take more images
            break

    return distribution


async def _generate_variant_image_set(available_photos: list[dict], start_index: int, image_count: int, product_name: str, variant_sku: str, variant_position: int) -> list[dict]:
    """
    Generate an optimized image set for a single variant with diversity checks.
    """
    if start_index >= len(available_photos) or image_count <= 0:
        return []

    variant_images = []
    used_photo_ids = set()

    # Select photos with diversity in mind
    for img_idx in range(image_count):
        photo_index = start_index + img_idx
        if photo_index >= len(available_photos):
            break

        photo = available_photos[photo_index]
        photo_id = photo.get("id")

        # Skip if we've already used this photo (shouldn't happen with current logic, but safety check)
        if photo_id in used_photo_ids:
            continue

        used_photo_ids.add(photo_id)

        # Create enhanced variant image with quality scoring
        variant_image = {
            "id": photo_id,
            "url": photo.get("src", {}).get("large") or photo.get("src", {}).get("original"),  # Use large or fallback to original
            "medium_url": photo.get("src", {}).get("medium"),
            "small_url": photo.get("src", {}).get("small"),
            "photographer": photo.get("photographer"),  # Pexels uses "photographer"
            "photographer_url": photo.get("photographer_url"),
            "alt": (
                f"{product_name} - {variant_sku.replace('-', ' ').title()} variant"
                if img_idx == 0
                else f"{product_name} - {variant_sku.replace('-', ' ').title()} variant image {img_idx + 1}"
            ),
            "width": photo.get("width"),  # Pexels uses "width" and "height"
            "height": photo.get("height"),
            "position": variant_position,
            "sku_suffix": variant_sku,
            "image_index": img_idx + 1,
            "quality_score": _calculate_image_quality_score(photo),
            "_source_photo": photo,  # Temporary field for tracking
        }
        variant_images.append(variant_image)

    # Sort images by quality score (best first) while maintaining some randomness
    variant_images.sort(key=lambda x: x["quality_score"] + random.random() * 0.2, reverse=True)

    # Re-index after sorting and regenerate alt text with correct numbering
    for idx, img in enumerate(variant_images):
        img["image_index"] = idx + 1
        # Regenerate alt text with correct index after sorting
        variant_sku = img.get("sku_suffix", "")
        if idx == 0:
            img["alt"] = f"{product_name} - {variant_sku.replace('-', ' ').title()} variant"
        else:
            img["alt"] = f"{product_name} - {variant_sku.replace('-', ' ').title()} variant image {idx + 1}"

    return variant_images


async def _process_single_product(
    product: dict, pexels: PexelsAPI, keyword_cache: dict, api_calls_made: list, cache_hits: list, min_images: int, max_images: int, semaphore: asyncio.Semaphore
) -> tuple[dict | None, dict]:
    """Process a single product with semaphore control."""
    async with semaphore:
        product_id = product.get("id")
        product_name = product.get("name", "Unknown")
        image_keywords = product.get("image_keywords", [])
        variants = product.get("variants", [])

        if not image_keywords:
            logger.warning(f"No image keywords found for product {product_id}: {product_name}")
            return None, product

        try:
            # Generate search queries by combining 2 random keywords
            photos = []
            search_query = ""

            # Create different combinations to try
            search_attempts = []

            if len(image_keywords) >= 2:
                # Try multiple combinations of 2 random keywords
                for _ in range(min(5, len(image_keywords))):  # Try up to 5 combinations
                    two_keywords = random.sample(image_keywords, 2)
                    combined_query = " ".join(two_keywords)
                    if combined_query not in search_attempts:
                        search_attempts.append(combined_query)
            else:
                # Fall back to individual keywords if less than 2 available
                search_attempts = image_keywords[:3]  # Try first 3 keywords

            # Also add individual keywords as fallback
            search_attempts.extend(image_keywords[:2])  # Add first 2 individual keywords as backup

            for query in search_attempts:
                # Check cache first to minimize API calls
                if query in keyword_cache:
                    photos = keyword_cache[query]
                    search_query = query
                    cache_hits[0] += 1
                    logger.info(f"💾 Using cached results for query: '{query}' ({len(photos)} photos)")
                    break

                # Calculate needed photos: master images + (each variant x min_images to max_images) + description images
                needed_photos = min_images + len(variants) * max_images if variants else max_images
                needed_photos += 3  # Add 3 more for description images

                result = await pexels.search_photos(
                    query=query,
                    per_page=min(needed_photos + 2, 80),  # Get extra for variety, max 80 per page
                    orientation="landscape",  # Pexels uses "landscape"
                )

                api_calls_made[0] += 1

                # Extract photos from the search result
                photos = []
                if result.get("status_code") == 200 and result.get("photos"):
                    photos = result["photos"]

                if photos:
                    search_query = query
                    keyword_cache[query] = photos  # Cache for future use

                    break
                else:
                    logger.info(f"⚠️ No photos found for query: '{query}', trying next...")

            if not photos:
                logger.warning(f"No photos found for any search query. Tried combinations and individual keywords from: {', '.join(image_keywords)}")
                return None, product

            # === GENERATE IMAGES.JSON DATA ===
            product_images = {
                "product_id": product_id,
                "product_name": product_name,
                "successful_search_keyword": search_query,  # The keyword that actually found images
                "attempted_keywords": image_keywords,  # All keywords that were tried
                "main_images": [],
                "variant_images": {},
            }

            # Randomly shuffle photos to avoid duplicates across products using same keywords
            available_photos = photos.copy()
            random.shuffle(available_photos)

            selected_photos = []
            photo_index = 0

            # Generate master variant images
            master_image_count = min(min_images, len(available_photos))
            for i in range(master_image_count):
                if photo_index >= len(available_photos):
                    break
                photo = available_photos[photo_index]
                selected_photos.append(photo)
                photo_index += 1

                main_image = {
                    "id": photo.get("id"),
                    "url": photo.get("src", {}).get("large") or photo.get("src", {}).get("original"),  # Use large or fallback to original
                    "medium_url": photo.get("src", {}).get("medium"),
                    "small_url": photo.get("src", {}).get("small"),
                    "alt": f"{product_name} - Main product image" if i == 0 else f"{product_name} - Product image {i + 1}",
                    "width": photo.get("width"),  # Pexels uses "width" and "height"
                    "height": photo.get("height"),
                }
                product_images["main_images"].append(main_image)

            # Generate variant images
            if variants:
                variant_distribution = _calculate_intelligent_variant_distribution(variants, len(available_photos) - photo_index, min_images, max_images)

                for variant_idx, variant in enumerate(variants):
                    variant_sku = variant.get("sku_suffix", f"variant_{variant_idx}")
                    variant_position = variant.get("position", variant_idx + 1)
                    allocated_images = variant_distribution[variant_idx]

                    if allocated_images <= 0:
                        logger.warning(f"    ⚠️ No images allocated for variant {variant_position} ({variant_sku})")
                        continue

                    # Generate optimized image set for this variant
                    variant_images = await _generate_variant_image_set(available_photos, photo_index, allocated_images, product_name, variant_sku, variant_position)

                    photo_index += len(variant_images)
                    selected_photos.extend([img["_source_photo"] for img in variant_images])

                    # Clean up internal fields and store
                    for img in variant_images:
                        img.pop("_source_photo", None)

                    product_images["variant_images"][str(variant_position)] = variant_images

            # === UPDATE PRODUCT DESCRIPTION ===
            updated_product = product.copy()

            # Check if product has marketing description with placeholders
            # Try marketing_description first (new structure), fall back to description (legacy)
            marketing_description = updated_product.get("marketing_description") or updated_product.get("description", "")
            if IMAGE_TAG_PLACEHOLDER in marketing_description:
                # Use remaining photos for description images (medium size)
                description_images = []
                remaining_photos = available_photos[photo_index : photo_index + 3]  # Get up to 3 more images

                for photo in remaining_photos:
                    medium_url = photo.get("src", {}).get("medium")  # Use Pexels medium-sized image URL
                    alt_text = f"{product_name} - Product image"
                    img_tag = f'<img src="{medium_url}" alt="{alt_text}" class="product-image" loading="lazy" style="width: 100%; padding-bottom: 1rem" />'
                    description_images.append(img_tag)

                if description_images:
                    # Replace image placeholders with actual image tags
                    updated_description = marketing_description
                    placeholder_count = marketing_description.count(IMAGE_TAG_PLACEHOLDER)

                    # Replace each placeholder with an image (cycle through available images)
                    for i in range(placeholder_count):
                        image_tag = description_images[i % len(description_images)]
                        updated_description = updated_description.replace(IMAGE_TAG_PLACEHOLDER, image_tag, 1)

                    # Save back to the correct field (prefer marketing_description if it exists)
                    if updated_product.get("marketing_description"):
                        updated_product["marketing_description"] = updated_description
                    else:
                        updated_product["description"] = updated_description

                else:
                    logger.warning(f"No images available for description update for product {product_id}")

            # Count total variant images
            total_variant_images = 0
            for variant_image_list in product_images["variant_images"].values():
                if isinstance(variant_image_list, list):
                    total_variant_images += len(variant_image_list)
                else:
                    total_variant_images += 1

            return product_images, updated_product

        except Exception as e:
            logger.error(f"❌ Failed to process product {product_id}: {e}")
            return None, product


def _calculate_image_quality_score(photo: dict) -> float:
    """
    Calculate a quality score for an image based on various factors.
    Returns a score between 0.0 and 1.0.
    """
    score = 0.5  # Base score

    # Resolution scoring (higher resolution = better)
    width = photo.get("width", 0)  # Pexels uses width and height
    height = photo.get("height", 0)
    total_pixels = width * height

    if total_pixels >= 2000000:  # 2MP+
        score += 0.2
    elif total_pixels >= 1000000:  # 1MP+
        score += 0.1
    elif total_pixels < 500000:  # Less than 0.5MP
        score -= 0.1

    # Aspect ratio scoring (prefer landscape for product images)
    if width > 0 and height > 0:
        aspect_ratio = width / height
        if 1.2 <= aspect_ratio <= 1.8:  # Good landscape ratio
            score += 0.15
        elif 0.8 <= aspect_ratio <= 1.2:  # Square-ish (acceptable)
            score += 0.05
        else:  # Too wide or too tall
            score -= 0.05

    # Alt text quality (Pexels uses "alt" field for alt text)
    alt_text = photo.get("alt", "")
    if len(alt_text) > 50:
        score += 0.1
    elif len(alt_text) > 20:
        score += 0.05

    # Photographer reputation (Pexels uses "photographer" field)
    photographer = photo.get("photographer", "")
    if photographer and len(photographer) > 3:  # Has credited photographer
        score += 0.05

    return max(0.0, min(1.0, score))
