import asyncio
import json
import logging
import random
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import urlparse

from elasticsearch import Elasticsearch
from openai import AsyncOpenAI
from pydantic import BaseModel, Field

from apps.gumroad.config.settings import settings
from apps.gumroad.utils.faker import faker
from apps.gumroad.utils.mysql import AsyncMySQLClient
from common.logger import logger


openai_client = AsyncOpenAI()
logging.getLogger("httpx").setLevel(logging.WARNING)

# Constants
REVIEW_PROBABILITY = 0.7
GUMROAD_FEE_RATE = 0.05
GUMROAD_FIXED_FEE_CENTS = 30
MESSAGE_PROBABILITY = 0.8
PRICE_RANGE_CENTS = (500, 50000)  # $5 to $500
REVIEW_TIME_RANGE_DAYS = (0, 14)

# Review messages by rating
REVIEW_MESSAGES = {
    "positive": [
        "Great product! Highly recommend.",
        "Excellent quality, exactly what I needed.",
        "Amazing value for money.",
        "Perfect! Will buy again.",
        "Outstanding work, very satisfied.",
        "Fantastic resource, very helpful.",
        "Exceeded my expectations!",
        "Top quality product.",
        "Wonderful, thank you!",
        "Brilliant work, love it!",
        "Super useful and well made.",
        "Exactly what I was looking for.",
        "High quality, fast delivery.",
        "Very happy with this purchase.",
        "Professional and polished.",
    ],
    "neutral": [
        "Good product overall.",
        "Does what it says on the tin.",
        "Decent quality for the price.",
        "It's okay, nothing special.",
        "Works as expected.",
        "Average product, decent value.",
        "Not bad, could be better.",
        "Satisfactory purchase.",
        "It's fine, does the job.",
        "Reasonable quality.",
    ],
    "negative": [
        "Not quite what I expected.",
        "Could use some improvements.",
        "Okay but has some issues.",
        "Not worth the price.",
        "Disappointing quality.",
        "Had some problems with it.",
        "Not as described.",
        "Could be better for the price.",
    ],
}

# Rating distribution weights (higher ratings more common)
RATING_WEIGHTS = [5, 10, 15, 35, 35]  # For ratings 1-5

# Reviews cache file path
REVIEWS_CACHE_FILE = settings.DATA_PATH / "generated" / "reviews.json"

# Global concurrency controls
_reviews_cache = None
_cache_lock = asyncio.Lock()
_openai_semaphore = asyncio.Semaphore(512)  # Limit concurrent OpenAI calls
_slug_locks = {}  # Per-slug locks to prevent duplicate GPT calls
_cache_building_mode = False  # Track if we're in cache building mode


class ProductReview(BaseModel):
    rating: int = Field(..., description="Rating from 1-5 stars", ge=1, le=5)
    message: str = Field(
        ...,
        description="Review message, 10-100 words, authentic and specific to the product",
    )


async def generate_sales(number_of_sales: int) -> str:
    """Generate sales data and save to JSON file."""
    global _cache_building_mode

    # Check if we need to build cache at the start
    _cache_building_mode = not REVIEWS_CACHE_FILE.exists()
    if _cache_building_mode:
        logger.info("Cache building mode: Will generate fresh GPT reviews")
    else:
        logger.info("Cache exists: Will use cached reviews")

    # Read products from JSON file
    products_file = settings.DATA_PATH / "generated" / "products.json"
    if not products_file.exists():
        raise FileNotFoundError(f"Products file not found: {products_file}. Please generate products first.")

    with products_file.open(encoding="utf-8") as f:
        products_data = json.load(f)

    products = products_data.get("products", [])
    logger.info(f"Loaded {len(products)} products from {products_file}")

    logger.info(f"Generating {number_of_sales} random sales data...")

    # Generate sales data
    sales_data = []

    # Create tasks for concurrent execution
    async def create_single_sale_data(sale_index: int):
        product = faker.random_element(elements=products)
        purchase_data = generate_random_purchase(product)

        # Generate review data (70% chance)
        review_data = None
        if _should_generate_review():
            review_data = await generate_random_review(
                purchase_id=sale_index + 1,  # Temporary ID for generation
                product=product,
                created_at=datetime.strptime(purchase_data["created_at"], "%Y-%m-%d %H:%M:%S"),
            )

        return {"purchase": purchase_data, "review": review_data, "product_slug": product.get("slug")}

    # Execute all sales data generation concurrently with limited batch size
    batch_size = 20
    for i in range(0, number_of_sales, batch_size):
        batch_end = min(i + batch_size, number_of_sales)
        batch_tasks = [create_single_sale_data(j) for j in range(i, batch_end)]

        # Execute batch concurrently
        batch_results = await asyncio.gather(*batch_tasks, return_exceptions=True)

        # Collect results
        for result in batch_results:
            if isinstance(result, Exception):
                logger.error(f"Error in sale data generation: {result}")
            else:
                sales_data.append(result)

        # Log progress every 5 batches or at the end
        batch_num = i // batch_size + 1
        total_batches = (number_of_sales + batch_size - 1) // batch_size
        if batch_num % 5 == 0 or batch_num == total_batches:
            logger.info(f"Generated batch {batch_num}/{total_batches} ({len(sales_data)} sales completed)")

    # Save reviews cache at the end if we were in cache building mode
    if _cache_building_mode:
        await _save_reviews_to_cache()
        logger.info("Cache building complete: Saved reviews to cache file")

    # Save sales data to JSON file
    output_dir = settings.DATA_PATH / "generated"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_file = output_dir / "sales.json"

    with output_file.open("w", encoding="utf-8") as f:
        json.dump(sales_data, f, indent=2, ensure_ascii=False, default=str)

    logger.info(f"Successfully generated {len(sales_data)} sales data records and saved to {output_file}")
    return str(output_file)


async def seed_sales(index_to_elasticsearch: bool = True):
    """Read sales data from JSON file and insert into database."""
    logger.start("Seeding sales...")
    # Load sales data from JSON file
    sales_file = settings.DATA_PATH / "generated" / "sales.json"

    if not sales_file.exists():
        raise FileNotFoundError(f"Sales data file not found: {sales_file}. Please run generate_sales() first.")

    with Path.open(sales_file, encoding="utf-8") as f:
        sales_data = json.load(f)

    logger.info(f"Loading {len(sales_data)} sales from {sales_file}")

    # Get all products from Gumroad API to resolve slugs to IDs
    from apps.gumroad.utils.gumroad import GumroadAPI

    async with GumroadAPI() as gumroad:
        products = await gumroad.get_all_products()

    # Create a mapping of slug to product
    # Debug: log the first product to see what fields are available
    if products:
        logger.info(f"Sample product fields: {list(products[0].keys())}")

    # Try different possible slug fields
    slug_to_product = {}
    for product in products:
        # Try multiple possible slug fields
        slug = product.get("slug") or product.get("unique_permalink") or product.get("url") or product.get("short_url")

        if slug:
            # Extract just the slug part if it's a full URL
            if "/" in slug:
                slug = slug.split("/")[-1]
            slug_to_product[slug] = product

    logger.info(f"Loaded {len(slug_to_product)} products from Gumroad API")
    if slug_to_product:
        logger.info(f"Sample slugs: {list(slug_to_product.keys())[:5]}")

    sql_client = AsyncMySQLClient()
    await sql_client.connect()

    try:
        es_client = _create_elasticsearch_client_if_needed(index_to_elasticsearch)
        products_with_reviews = set()

        # Create tasks for concurrent execution
        async def insert_single_sale(sale_data: dict, _sale_index: int):
            purchase_data = sale_data["purchase"]
            review_data = sale_data["review"]
            product_slug = sale_data["product_slug"]

            # Resolve product slug to actual product
            product = slug_to_product.get(product_slug)
            if not product:
                logger.error(f"Product not found for slug: {product_slug}")
                return None

            # Update purchase data with actual product ID
            purchase_data["link_id"] = product["id"]

            # Insert purchase
            purchase_id = await sql_client.insert("purchases", purchase_data)

            # Insert review if exists
            if review_data:
                review_data["purchase_id"] = purchase_id  # Update with actual purchase ID
                review_data["link_id"] = product["id"]  # Update with actual product ID
                _review_id = await sql_client.insert("product_reviews", review_data)
                return product["id"]  # Return product ID for tracking

            # Index in Elasticsearch if enabled
            if es_client:
                await _index_purchase_in_elasticsearch(es_client, purchase_data, purchase_id, product)

            return None

        # Execute all sales insertion concurrently with limited batch size
        batch_size = 20
        for i in range(0, len(sales_data), batch_size):
            batch_end = min(i + batch_size, len(sales_data))
            batch_tasks = [insert_single_sale(sales_data[j], j) for j in range(i, batch_end)]

            # Execute batch concurrently
            batch_results = await asyncio.gather(*batch_tasks, return_exceptions=True)

            # Collect products that received reviews
            for result in batch_results:
                if isinstance(result, Exception):
                    logger.error(f"Error in sale insertion: {result}")
                elif result is not None:
                    products_with_reviews.add(result)

            # Log progress every 5 batches or at the end
            batch_num = i // batch_size + 1
            total_batches = (len(sales_data) + batch_size - 1) // batch_size
            if batch_num % 5 == 0 or batch_num == total_batches:
                logger.info(f"Seeded batch {batch_num}/{total_batches} ({i + len(batch_tasks)} sales inserted)")

        # Update product review stats for products that received reviews
        if products_with_reviews:
            await update_product_review_stats(sql_client, products_with_reviews)

        logger.info(f"Successfully seeded {len(sales_data)} sales into database")

    except Exception as e:
        logger.error(f"Error seeding sales: {e}")
        raise
    finally:
        await sql_client.disconnect()
    logger.succeed("Sales seeded successfully")


async def insert_sales(number_of_sales: int, index_to_elasticsearch: bool = True):
    """Generate and insert random sales data into the purchases table and optionally Elasticsearch.

    This function combines both generation and seeding for backward compatibility.
    For separate operations, use generate_sales() and seed_sales() instead.
    """
    logger.info(f"Generating and inserting {number_of_sales} sales...")

    # Generate sales data
    output_file = await generate_sales(number_of_sales)
    logger.info(f"Generated sales data saved to {output_file}")

    # Seed sales data into database
    await seed_sales(index_to_elasticsearch)

    logger.info(f"Successfully generated and inserted {number_of_sales} sales")


def _create_elasticsearch_client_if_needed(index_to_elasticsearch: bool):
    """Create Elasticsearch client if indexing is enabled."""
    return Elasticsearch(settings.ELASTICSEARCH_URL) if index_to_elasticsearch else None


def _should_generate_review() -> bool:
    """Determine if a review should be generated."""
    return random.random() < REVIEW_PROBABILITY


async def _insert_product_review(sql_client, purchase_id: int, product: dict, purchase_data: dict):
    """Generate and insert a product review."""
    review_data = await generate_random_review(
        purchase_id=purchase_id,
        product=product,
        created_at=datetime.strptime(purchase_data["created_at"], "%Y-%m-%d %H:%M:%S"),
    )
    review_id = await sql_client.insert("product_reviews", review_data)
    logger.info(f"Inserted review with ID: {review_id} for purchase {purchase_id}")


async def _index_purchase_in_elasticsearch(es_client, purchase_data: dict, purchase_id: int, product: dict):
    """Index purchase in Elasticsearch."""
    try:
        es_doc = transform_purchase_for_elasticsearch(purchase_data, purchase_id, product)
        result = es_client.index(index="purchases", id=purchase_id, body=es_doc)

        if result.get("result") not in ["created", "updated"]:
            logger.warning(f"Unexpected Elasticsearch result for purchase {purchase_id}: {result}")
    except Exception as e:
        logger.error(f"Failed to index purchase {purchase_id} in Elasticsearch: {e!s}")


def generate_random_purchase(product: dict) -> dict:
    """Generate a random purchase record based on a product."""
    created_at = faker.date_time_between(start_date="-1y", end_date="now")
    price_cents = _calculate_price_cents(product)
    fee_cents = _calculate_gumroad_fee(price_cents)
    buyer_info = _generate_buyer_info()

    return {
        "seller_id": 1,
        "created_at": created_at.strftime("%Y-%m-%d %H:%M:%S"),
        "updated_at": created_at.strftime("%Y-%m-%d %H:%M:%S"),
        "fee_cents": fee_cents,
        "link_id": None,  # Will be set during seeding
        "email": buyer_info["email"],
        "price_cents": price_cents,
        "displayed_price_cents": price_cents,
        "displayed_price_currency_type": "usd",
        "rate_converted_to_usd": "1.0",
        "street_address": None,
        "city": faker.city() if random.choice([True, False]) else None,
        "state": faker.state_abbr() if random.choice([True, False]) else None,
        "zip_code": faker.zipcode() if random.choice([True, False]) else None,
        "country": buyer_info["country"],
        "full_name": buyer_info["full_name"],
        "credit_card_id": None,
        "purchaser_id": None,
        "purchaser_type": "User",
        "session_id": faker.md5(),
        "ip_address": faker.ipv4(),
        "is_mobile": random.choice([0, 1]),
        "stripe_refunded": None,
        "stripe_transaction_id": None,
        "stripe_fingerprint": None,
        "stripe_card_id": None,
        "can_contact": random.choice([0, 1]),
        "referrer": "direct",
        "stripe_status": None,
        "variants": None,
        "chargeback_date": None,
        "webhook_failed": 0,
        "failed": 0,
        "card_type": None,
        "card_visual": None,
        "purchase_state": "successful",
        "processor_fee_cents": None,
        "succeeded_at": created_at.strftime("%Y-%m-%d %H:%M:%S"),
        "card_country": faker.country_code(),
        "stripe_error_code": None,
        "browser_guid": str(uuid.uuid4()),
        "error_code": None,
        "card_bin": None,
        "custom_fields": None,
        "ip_country": buyer_info["country"],
        "ip_state": faker.state_abbr() if random.choice([True, False]) else None,
        "purchase_success_balance_id": None,
        "purchase_chargeback_balance_id": None,
        "purchase_refund_balance_id": None,
        "flags": 0,
        "offer_code_id": None,
        "subscription_id": None,
        "preorder_id": None,
        "card_expiry_month": None,
        "card_expiry_year": None,
        "tax_cents": 0,
        "affiliate_credit_cents": 0,
        "credit_card_zipcode": None,
        "json_data": "{}",
        "card_data_handling_mode": None,
        "charge_processor_id": "paypal",
        "total_transaction_cents": price_cents,
        "gumroad_tax_cents": 0,
        "zip_tax_rate_id": None,
        "quantity": 1,
        "merchant_account_id": None,
        "shipping_cents": 0,
        "affiliate_id": None,
        "processor_fee_cents_currency": "usd",
        "stripe_partially_refunded": 0,
        "paypal_order_id": None,
        "rental_expired": None,
        "processor_payment_intent_id": None,
        "processor_setup_intent_id": None,
        "price_id": None,
        "recommended_by": "",
        "deleted_at": None,
    }


def _calculate_price_cents(product: dict) -> int:
    """Calculate price in cents for the product."""
    if product.get("price_cents"):
        return product["price_cents"]
    return random.randint(*PRICE_RANGE_CENTS)


def _calculate_gumroad_fee(price_cents: int) -> int:
    """Calculate Gumroad fee (5% + 30 cents)."""
    return int(price_cents * GUMROAD_FEE_RATE) + GUMROAD_FIXED_FEE_CENTS


def _generate_buyer_info() -> dict:
    """Generate random buyer information."""
    full_name = faker.name()
    nickname = "".join(c for c in full_name if c.isalnum())
    email_domain = faker.free_email_domain()
    email = f"{nickname.lower()}@{email_domain}"
    country = "United States"

    return {"full_name": full_name, "email": email, "country": country}


async def _load_reviews_cache() -> dict:
    """Load cached reviews from JSON file (thread-safe)"""
    global _reviews_cache

    async with _cache_lock:
        if _reviews_cache is not None:
            return _reviews_cache

        try:
            if REVIEWS_CACHE_FILE.exists():
                with REVIEWS_CACHE_FILE.open(encoding="utf-8") as f:
                    _reviews_cache = json.load(f)
                    logger.info(f"Loaded reviews cache with {len(_reviews_cache)} product slugs")
            else:
                _reviews_cache = {}
                logger.info("No existing reviews cache found, starting with empty cache")
        except (json.JSONDecodeError, FileNotFoundError) as e:
            logger.warning(f"Error loading reviews cache: {e}")
            _reviews_cache = {}

        return _reviews_cache


async def _save_reviews_to_cache():
    """Save reviews cache to JSON file (thread-safe)"""
    global _reviews_cache

    if _reviews_cache is None:
        return

    try:
        # Ensure the data directory exists
        REVIEWS_CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)

        async with _cache_lock:
            with REVIEWS_CACHE_FILE.open("w", encoding="utf-8") as f:
                json.dump(_reviews_cache, f, indent=2, ensure_ascii=False)

        logger.info(f"Saved reviews cache with {len(_reviews_cache)} product slugs")
    except Exception as e:
        logger.error(f"Error saving reviews cache: {e}")


async def _get_slug_lock(slug: str) -> asyncio.Lock:
    """Get or create a lock for a specific product slug"""
    if slug not in _slug_locks:
        _slug_locks[slug] = asyncio.Lock()
    return _slug_locks[slug]


async def _generate_gpt_review_message(product: dict, rating: int) -> str:
    """Generate a review message using GPT based on product and rating (with semaphore)."""
    async with _openai_semaphore:  # Limit concurrent OpenAI calls
        try:
            # Determine sentiment based on rating
            if rating >= 4:
                sentiment = "very positive and enthusiastic"
            elif rating == 3:
                sentiment = "neutral and balanced"
            else:
                sentiment = "disappointed or critical"

            product_name = product.get("name", "this product")
            product_description = product.get("description", "")

            response = await openai_client.beta.chat.completions.parse(
                model="gpt-4o-mini",
                messages=[
                    {
                        "role": "system",
                        "content": """You are writing authentic product reviews for Gumroad products. 
                        Write like a real customer who purchased and used the product.
                        """,
                    },
                    {
                        "role": "user",
                        "content": f"""Write a {sentiment} review for this product:
                        Product: {product_name}
                        Description: {product_description[:300]}...
                        Rating: {rating}/5 stars
                        
                        Requirements:
                        - Sound like a real customer who actually used the product
                        - Be specific about what you liked/disliked 
                        - 10-50 words
                        - Match the rating sentiment
                        - Don't mention the rating number itself
                        - Use natural, conversational language
                        - Avoid overly promotional language""",
                    },
                ],
                response_format=ProductReview,
            )

            parsed_response = response.choices[0].message.parsed
            if parsed_response and parsed_response.message:
                return parsed_response.message
            return _generate_review_message(rating) or "Great product!"

        except Exception as e:
            logger.error(f"Error generating GPT review: {e}")
            # Fallback to static message
            return _generate_review_message(rating) or "Great product!"


async def generate_random_review(purchase_id: int, product: dict, created_at: datetime) -> dict:
    """Generate a realistic product review using GPT with caching by slug."""
    try:
        slug = product.get("url_without_protocol", product.get("slug", f"product-{product.get('name', 'unknown')}"))

        # Generate weighted rating
        rating = random.choices([1, 2, 3, 4, 5], weights=RATING_WEIGHTS)[0]

        # 20% chance of rating-only review (no message)
        if random.random() < 0.2:
            message = None
        else:
            # Get per-slug lock to prevent duplicate GPT calls for same product
            slug_lock = await _get_slug_lock(slug)

            async with slug_lock:
                # Load cache
                reviews_cache = await _load_reviews_cache()

                # Use cache building mode to determine behavior
                if not _cache_building_mode and slug in reviews_cache and reviews_cache[slug]:
                    # Use cached review when not in cache building mode
                    cached_review = random.choice(reviews_cache[slug])
                    message = cached_review["message"]
                    rating = cached_review["rating"]  # Use cached rating too
                elif _cache_building_mode:
                    # Generate new review when in cache building mode
                    message = await _generate_gpt_review_message(product, rating)

                    # Add to cache (but don't save to file yet)
                    if slug not in reviews_cache:
                        reviews_cache[slug] = []
                    reviews_cache[slug].append({"message": message, "rating": rating})
                else:
                    # Cache exists but no reviews for this slug - use fallback
                    message = _generate_review_message(rating)

        review_created_at = _calculate_review_date(created_at)

        return {
            "purchase_id": purchase_id,
            "rating": rating,
            "created_at": review_created_at.strftime("%Y-%m-%d %H:%M:%S"),
            "updated_at": review_created_at.strftime("%Y-%m-%d %H:%M:%S"),
            "link_id": None,  # Will be set during seeding
            "message": message,
            "deleted_at": None,
        }

    except Exception as e:
        logger.error(f"Error generating GPT review, falling back to static message: {e}")
        # Fallback to original method if GPT fails
        rating = random.choices([1, 2, 3, 4, 5], weights=RATING_WEIGHTS)[0]
        message = _generate_review_message(rating)
        review_created_at = _calculate_review_date(created_at)

        return {
            "purchase_id": purchase_id,
            "rating": rating,
            "created_at": review_created_at.strftime("%Y-%m-%d %H:%M:%S"),
            "updated_at": review_created_at.strftime("%Y-%m-%d %H:%M:%S"),
            "link_id": None,  # Will be set during seeding
            "message": message,
            "deleted_at": None,
        }


def _generate_review_message(rating: int) -> str | None:
    """Generate a review message based on rating."""
    # 80% chance of having a message
    if random.random() > MESSAGE_PROBABILITY:
        return None

    if rating >= 4:
        return random.choice(REVIEW_MESSAGES["positive"])
    elif rating == 3:
        return random.choice(REVIEW_MESSAGES["neutral"])
    else:
        return random.choice(REVIEW_MESSAGES["negative"])


def _calculate_review_date(purchase_date: datetime) -> datetime:
    """Calculate review creation date (0-14 days after purchase)."""
    return purchase_date + timedelta(
        days=random.randint(*REVIEW_TIME_RANGE_DAYS),
        hours=random.randint(0, 23),
        minutes=random.randint(0, 59),
    )


async def update_product_review_stats(sql_client: AsyncMySQLClient, product_ids: set):
    """Update product_review_stats table for products that received new reviews."""
    logger.info(f"Updating review stats for {len(product_ids)} products...")

    for product_id in product_ids:
        try:
            stats = await _fetch_product_review_stats(sql_client, product_id)
            if stats:
                await _upsert_product_review_stats(sql_client, product_id, stats)
        except Exception as e:
            logger.error(f"Failed to update review stats for product {product_id}: {e!s}")


async def _fetch_product_review_stats(sql_client: AsyncMySQLClient, product_id: int) -> dict | None:
    """Fetch review statistics for a product."""
    query = """
        SELECT 
            COUNT(*) as reviews_count,
            AVG(rating) as average_rating,
            SUM(CASE WHEN rating = 1 THEN 1 ELSE 0 END) as ratings_of_one_count,
            SUM(CASE WHEN rating = 2 THEN 1 ELSE 0 END) as ratings_of_two_count,
            SUM(CASE WHEN rating = 3 THEN 1 ELSE 0 END) as ratings_of_three_count,
            SUM(CASE WHEN rating = 4 THEN 1 ELSE 0 END) as ratings_of_four_count,
            SUM(CASE WHEN rating = 5 THEN 1 ELSE 0 END) as ratings_of_five_count
        FROM product_reviews 
        WHERE link_id = %s AND deleted_at IS NULL
    """

    result = await sql_client.fetch_dict_all(query, (product_id,))
    return result[0] if result else None


async def _upsert_product_review_stats(sql_client: AsyncMySQLClient, product_id: int, stats: dict):
    """Insert or update product review stats."""
    stats_data = _prepare_stats_data(product_id, stats)

    # Check if record exists
    existing_query = "SELECT id FROM product_review_stats WHERE link_id = %s"
    existing = await sql_client.fetch_dict_all(existing_query, (product_id,))

    if existing:
        # Update existing record
        stats_data.pop("created_at")  # Don't update created_at
        await sql_client.update("product_review_stats", stats_data, f"link_id = {product_id}")
    else:
        # Insert new record
        await sql_client.insert("product_review_stats", stats_data)


def _prepare_stats_data(product_id: int, stats: dict) -> dict:
    """Prepare stats data for database insertion/update."""
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    return {
        "link_id": product_id,
        "reviews_count": int(stats["reviews_count"]),
        "average_rating": round(float(stats["average_rating"]), 1) if stats["average_rating"] else 0,
        "ratings_of_one_count": int(stats["ratings_of_one_count"]),
        "ratings_of_two_count": int(stats["ratings_of_two_count"]),
        "ratings_of_three_count": int(stats["ratings_of_three_count"]),
        "ratings_of_four_count": int(stats["ratings_of_four_count"]),
        "ratings_of_five_count": int(stats["ratings_of_five_count"]),
        "created_at": now,
        "updated_at": now,
    }


def transform_purchase_for_elasticsearch(purchase_data, purchase_id, product):
    """Transform MySQL purchase data to Elasticsearch document format for new purchases."""

    # Helper function to safely extract domain from referrer
    def extract_referrer_domain(referrer):
        if not referrer or referrer == "direct":
            return "direct"

        if "://" in referrer:
            try:
                return urlparse(referrer).netloc.lower()
            except (ValueError, AttributeError):
                return referrer.lower()
        return referrer.lower()

    # Helper function to safely extract domain from email
    def extract_email_domain(email):
        if email and "@" in email:
            return email.lower().split("@")[1]
        return None

    # Helper function to convert MySQL datetime to ISO format
    def mysql_datetime_to_iso(dt_str):
        if dt_str is None:
            return None
        if isinstance(dt_str, str):
            try:
                # Parse MySQL datetime format: "2025-02-09 10:42:37"
                dt = datetime.strptime(dt_str, "%Y-%m-%d %H:%M:%S")
                # Convert to ISO format with UTC timezone
                return dt.strftime("%Y-%m-%dT%H:%M:%S.000Z")
            except ValueError:
                try:
                    # Try parsing if it's already in ISO format
                    return datetime.fromisoformat(dt_str.replace("Z", "+00:00")).isoformat()
                except (ValueError, AttributeError):
                    return dt_str
        return dt_str.isoformat() if hasattr(dt_str, "isoformat") else str(dt_str)

    # Create the Elasticsearch document
    es_doc = {
        "id": purchase_id,
        "can_contact": bool(purchase_data.get("can_contact", False)),
        "country_or_ip_country": purchase_data.get("country") or purchase_data.get("ip_country"),
        "created_at": mysql_datetime_to_iso(purchase_data["created_at"]),
        "latest_charge_date": mysql_datetime_to_iso(purchase_data.get("succeeded_at") or purchase_data["created_at"]),
        "email": purchase_data.get("email", "").lower() if purchase_data.get("email") else None,
        "email_domain": extract_email_domain(purchase_data.get("email")),
        "fee_cents": purchase_data.get("fee_cents", 0) or 0,
        "full_name": purchase_data.get("full_name"),
        "not_chargedback_or_chargedback_reversed": True,  # New purchases are not chargedback
        "not_refunded_except_subscriptions": True,  # New purchases are not refunded
        "not_subscription_or_original_subscription_purchase": purchase_data.get("subscription_id") is None,
        "successful_authorization_or_without_preorder": purchase_data.get("purchase_state")
        in [
            "successful",
            "preorder_authorization_successful",
            "preorder_concluded_successfully",
        ]
        or purchase_data.get("preorder_id") is None,
        "price_cents": purchase_data.get("price_cents", 0) or 0,
        "purchase_state": purchase_data.get("purchase_state", "failed"),
        "amount_refunded_cents": 0,
        "fee_refunded_cents": 0,
        "tax_refunded_cents": 0,
        "selected_flags": [],
        "stripe_refunded": False,
        "tax_cents": purchase_data.get("tax_cents", 0) or 0,
        "monthly_recurring_revenue": 0.0,
        "ip_country": purchase_data.get("ip_country"),
        "ip_state": purchase_data.get("ip_state"),
        "referrer_domain": extract_referrer_domain(purchase_data.get("referrer")),
        "variant_ids": [],
        "product_ids_from_same_seller_purchased_by_purchaser": [],
        "variant_ids_from_same_seller_purchased_by_purchaser": [],
        "affiliate_credit_amount_cents": purchase_data.get("affiliate_credit_cents", 0) or 0,
        "affiliate_credit_fee_cents": 0,
        "affiliate_credit_amount_partially_refunded_cents": 0,
        "affiliate_credit_fee_partially_refunded_cents": 0,
        "product_id": purchase_data.get("link_id"),
        "product_unique_permalink": product.get("unique_permalink"),
        "product_name": product.get("name"),
        "seller_id": purchase_data.get("seller_id", 1),
        "seller_name": "Seller",  # Default name - you might want to fetch this from users table
        "purchaser_id": purchase_data.get("purchaser_id"),
        "subscription_id": purchase_data.get("subscription_id"),
        "taxonomy_id": product.get("taxonomy_id") if isinstance(product, dict) else None,
    }

    # Remove None values to keep the document clean
    return {k: v for k, v in es_doc.items() if v is not None}
