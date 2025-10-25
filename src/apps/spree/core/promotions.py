"""Promotion categories and promotions generation and seeding for Spree."""

import json
from datetime import datetime, timedelta
from pathlib import Path

from faker import Faker
from pydantic import BaseModel, Field

from apps.spree.config.settings import settings
from apps.spree.utils.ai import instructor_client
from apps.spree.utils.constants import PROMOTIONS_FILE
from apps.spree.utils.database import db_client
from common.logger import Logger


fake = Faker()
logger = Logger()


class PromotionCategory(BaseModel):
    """Promotion category model."""

    id: int = Field(description="Unique identifier for the promotion category")  # noqa: A003, RUF100
    name: str = Field(description="Name of the promotion category")
    code: str = Field(description="Code for the promotion category")
    created_at: datetime = Field(description="Creation timestamp")
    updated_at: datetime = Field(description="Last update timestamp")


class PromotionCategoryForGeneration(BaseModel):
    """Model for generating promotion categories (without IDs and timestamps)."""

    name: str = Field(description="Name of the promotion category")
    code: str = Field(description="Code for the promotion category")


class PromotionCategoryResponse(BaseModel):
    """Response format for generated promotion categories."""

    promotion_categories: list[PromotionCategoryForGeneration]


async def generate_promotion_categories(number_of_promotion_categories: int):
    """Generate promotion categories.

    Args:
        number_of_promotion_categories: Number of promotion categories to generate

    Returns:
        Dictionary with generated promotion categories
    """
    logger.info(f"Generating {number_of_promotion_categories} promotion categories...")

    system_prompt = f"""Generate {number_of_promotion_categories} realistic promotion categories for an e-commerce site {settings.SPREE_STORE_NAME}, a {settings.DATA_THEME_SUBJECT}.
    
    Examples of promotion categories:
    - Seasonal Sales (code: SEASONAL)
    - Holiday Specials (code: HOLIDAY)
    - Customer Loyalty (code: LOYALTY)
    - New Customer Offers (code: NEWCUST)
    - Product Launch (code: LAUNCH)
    - Clearance (code: CLEAR)
    
    The code should be a short, uppercase alphanumeric string, preferably related to the category name.
    """

    user_prompt = f"""Generate exactly {number_of_promotion_categories} promotion categories for {settings.SPREE_STORE_NAME}.
    
    For each category provide:
    - name: Descriptive name for the promotion category
    - code: Short uppercase code for the category (5-10 characters)
    """

    try:
        response = await instructor_client.chat.completions.create(
            model="claude-3-5-haiku-latest",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            response_model=PromotionCategoryResponse,
            temperature=0.3,
            max_tokens=4096,
        )

        if not response or not response.promotion_categories:
            logger.error("Failed to generate promotion categories")
            return None

        promotion_categories = []
        current_time = datetime.now()

        for i, category in enumerate(response.promotion_categories):
            promotion_category = {
                "id": i + 1,
                "name": category.name,
                "code": category.code,
                # Store timestamps as strings for JSON serialization
                "created_at": current_time.isoformat(),
                "updated_at": current_time.isoformat(),
            }
            promotion_categories.append(promotion_category)

            # Prepare data for saving to file
        promotion_data = {"promotion_categories": promotion_categories, "promotions": []}

        # Check if file exists and has promotions data
        if PROMOTIONS_FILE.exists():
            try:
                with Path.open(PROMOTIONS_FILE, encoding="utf-8") as f:
                    existing_data = json.load(f)
                    if "promotions" in existing_data:
                        promotion_data["promotions"] = existing_data["promotions"]
                        logger.info(f"Preserved {len(existing_data['promotions'])} existing promotions")
            except Exception as e:
                logger.warning(f"Could not load existing promotions file: {e}")

        # Save to file
        settings.DATA_PATH.mkdir(parents=True, exist_ok=True)
        PROMOTIONS_FILE.parent.mkdir(parents=True, exist_ok=True)
        with Path.open(PROMOTIONS_FILE, "w", encoding="utf-8") as f:
            json.dump(promotion_data, f, indent=2, ensure_ascii=False)

        logger.succeed(f"Successfully generated and saved {len(promotion_categories)} promotion categories to {PROMOTIONS_FILE}")

        return promotion_data

    except Exception as e:
        logger.error(f"Error generating promotion categories: {e}")
        raise


async def seed_promotion_categories():
    """Seed promotion categories into the database."""
    logger.start("Inserting promotion categories into spree_promotion_categories table...")

    try:
        # Load promotion categories from JSON file
        if not PROMOTIONS_FILE.exists():
            logger.error(f"Promotions file not found at {PROMOTIONS_FILE}. Run generate command first.")
            raise FileNotFoundError("Promotions file not found")

        with Path.open(PROMOTIONS_FILE, encoding="utf-8") as f:
            data = json.load(f)

        promotion_categories = data.get("promotion_categories", [])
        logger.info(f"Loaded {len(promotion_categories)} promotion categories from {PROMOTIONS_FILE}")

        current_time = datetime.now()

        for category in promotion_categories:
            # Check if promotion category already exists
            existing_category = await db_client.fetchrow("SELECT id FROM spree_promotion_categories WHERE name = $1", category["name"])

            if existing_category:
                logger.info(f"Found existing promotion category: {category['name']}")
                continue

            # Insert new promotion category
            await db_client.execute(
                """
                INSERT INTO spree_promotion_categories (name, code, created_at, updated_at)
                VALUES ($1, $2, $3, $4)
                """,
                category["name"],
                category["code"],
                current_time,
                current_time,
            )

        logger.succeed("Successfully seeded promotion categories")

    except Exception as e:
        logger.error(f"Error seeding promotion categories: {e}")
        raise


class Promotion(BaseModel):
    """Promotion model."""

    id: int = Field(description="Unique identifier for the promotion")  # noqa: A003, RUF100
    description: str = Field(description="Detailed description of the promotion")
    expires_at: datetime = Field(description="Expiration timestamp")
    starts_at: datetime = Field(description="Start timestamp")
    name: str = Field(description="Name of the promotion")
    type: str | None = Field(description="Type of promotion", default=None)  # noqa: A003, RUF100
    usage_limit: int | None = Field(description="Maximum usage limit", default=None)
    match_policy: str = Field(description="Match policy for promotion rules", default="all")
    code: str = Field(description="Promotion code")
    advertise: bool = Field(description="Whether to advertise the promotion", default=False)
    path: str | None = Field(description="URL path for the promotion", default=None)
    created_at: datetime = Field(description="Creation timestamp")
    updated_at: datetime = Field(description="Last update timestamp")
    promotion_category_id: int | None = Field(description="ID of the promotion category", default=None)


class PromotionForGeneration(BaseModel):
    """Promotion model for AI generation (without IDs and timestamps)."""

    description: str = Field(description="Detailed description of the promotion")
    name: str = Field(description="Name of the promotion")
    code: str = Field(description="Promotion code")
    advertise: bool = Field(description="Whether to advertise the promotion", default=False)
    path: str | None = Field(description="URL path for the promotion", default=None)
    usage_limit: int | None = Field(description="Maximum usage limit", default=None)
    match_policy: str = Field(description="Match policy for promotion rules", default="all")
    promotion_category_name: str = Field(description="Name of the associated promotion category")


class PromotionResponse(BaseModel):
    """Response format for generated promotions."""

    promotions: list[PromotionForGeneration]


async def generate_promotions(number_of_promotions: int):
    """Generate promotions.

    Args:
        number_of_promotions: Number of promotions to generate

    Returns:
        Dictionary with generated promotions and their usage counts
    """
    logger.info(f"Generating {number_of_promotions} promotions...")

    # First, load promotion categories to associate with promotions
    if not PROMOTIONS_FILE.exists():
        logger.error(f"Promotions file not found at {PROMOTIONS_FILE}. Run generate command first.")
        raise FileNotFoundError("Promotions file not found")

    try:
        with Path.open(PROMOTIONS_FILE, encoding="utf-8") as f:
            promotion_data = json.load(f)

        promotion_categories = promotion_data.get("promotion_categories", [])
        if not promotion_categories:
            logger.error("No promotion categories found. Generate promotion categories first.")
            return None

        logger.info(f"Loaded {len(promotion_categories)} promotion categories to associate with promotions")

        # Extract category names for reference in the prompt
        category_names = [category["name"] for category in promotion_categories]
        category_names_str = ", ".join(f"'{name}'" for name in category_names)

        # Define prompts for AI generation
        system_prompt = f"""Generate {number_of_promotions} realistic promotions for an e-commerce site {settings.SPREE_STORE_NAME}, a {settings.DATA_THEME_SUBJECT}.
        
        Examples of promotions:
        - 10% Off All Orders (code: SAVE10)
        - Free Shipping on Orders Over $50 (code: FREESHIP50)
        - Buy One Get One Free (code: BOGO)
        - New Customer Discount (code: WELCOME)
        - Weekend Sale (code: WEEKEND25)
        
        The code should be a short, uppercase alphanumeric string, preferably related to the promotion name.
        
        Available promotion categories: {category_names_str}
        """

        user_prompt = f"""Generate exactly {number_of_promotions} promotions for {settings.SPREE_STORE_NAME}.
        
        For each promotion provide:
        - name: Clear, concise promotion name
        - description: Detailed description of the promotion
        - code: Promotion code (5-15 uppercase characters)
        - advertise: Whether to show this promotion in ads (true/false)
        - path: URL path for the promotion (can be null)
        - usage_limit: Maximum number of times this promotion can be used (50-500)
        - match_policy: One of "all", "any" (default "all")
        - promotion_category_name: ONE of the following categories: {category_names_str}
        """

        response = await instructor_client.chat.completions.create(
            model="claude-3-5-haiku-latest",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            response_model=PromotionResponse,
            temperature=0.3,
            max_tokens=4096,
        )

        if not response or not response.promotions:
            logger.error("Failed to generate promotions")
            return None

        # Build a map of category names to IDs for lookup
        category_map = {category["name"]: category["id"] for category in promotion_categories}

        # Generate promotions with appropriate timestamps
        promotions = []
        current_time = datetime.now()

        for i, promo in enumerate(response.promotions):
            # Generate random start/end dates
            start_date = current_time + timedelta(days=fake.random_int(min=1, max=10))
            end_date = start_date + timedelta(days=fake.random_int(min=14, max=90))

            # Look up category ID from name
            category_id = category_map.get(promo.promotion_category_name)
            if not category_id:
                logger.warning(f"Category '{promo.promotion_category_name}' not found, using first available")
                category_id = next(iter(category_map.values()), None)

            # Generate random usage count if usage_limit is set
            usage_count = None
            if promo.usage_limit:
                # Generate a usage count between 30-80% of the limit for more realistic data
                min_usage = int(promo.usage_limit * 0.3)  # At least 30% used
                max_usage = int(promo.usage_limit * 0.8)  # Up to 80% used
                usage_count = fake.random_int(min=min_usage, max=max_usage)

            promotion = {
                "id": i + 1,
                "description": promo.description,
                "expires_at": end_date.isoformat(),
                "starts_at": start_date.isoformat(),
                "name": promo.name,
                "type": None,
                "usage_limit": promo.usage_limit,
                "match_policy": promo.match_policy,
                "code": promo.code,
                "advertise": promo.advertise,
                "path": promo.path or "/",
                "created_at": current_time.isoformat(),
                "updated_at": current_time.isoformat(),
                "promotion_category_id": category_id,
                "usage_count": usage_count,
            }
            promotions.append(promotion)

        # Update existing promotions data
        promotion_data["promotions"] = promotions

        settings.DATA_PATH.mkdir(parents=True, exist_ok=True)
        PROMOTIONS_FILE.parent.mkdir(parents=True, exist_ok=True)
        with Path.open(PROMOTIONS_FILE, "w", encoding="utf-8") as f:
            json.dump(promotion_data, f, indent=2, ensure_ascii=False)

        logger.succeed(f"Successfully generated and saved {len(promotions)} promotions to {PROMOTIONS_FILE}")

        return promotion_data

    except Exception as e:
        logger.error(f"Error generating promotions: {e}")
        raise


async def create_promotion_usage_records(promotion_id, usage_count):
    """Create order promotion records to simulate usage.

    Args:
        promotion_id: ID of the promotion to create usage records for
        usage_count: Number of usage records to create

    Returns:
        Number of records created
    """
    if usage_count <= 0:
        return 0

    # We need to get some order IDs to associate with the promotion
    # First, check if we have enough orders to meet usage_count
    order_count = await db_client.fetchval("SELECT COUNT(*) FROM spree_orders WHERE state = 'complete'")

    if not order_count or order_count == 0:
        logger.warning("No completed orders found to associate with promotions")
        return 0

    # Get order IDs to use
    orders = await db_client.fetch(
        """
        SELECT id FROM spree_orders 
        WHERE state = 'complete'
        ORDER BY RANDOM() 
        LIMIT $1
        """,
        min(int(order_count), usage_count),
    )

    order_ids = [order["id"] for order in orders]

    # If we don't have enough orders, we'll reuse some
    if len(order_ids) < usage_count:
        # Repeat order IDs as needed to reach usage_count
        order_ids = (order_ids * (usage_count // len(order_ids) + 1))[:usage_count]

    # Current timestamp
    current_time = datetime.now()

    # Create order promotion records
    created_count = 0
    for order_id in order_ids[:usage_count]:
        try:
            # Check if this order-promotion combination already exists
            existing = await db_client.fetchval(
                """
                SELECT id FROM spree_order_promotions 
                WHERE order_id = $1 AND promotion_id = $2
                """,
                order_id,
                promotion_id,
            )

            if existing:
                continue

            # Insert the order promotion record and adjust order total
            await db_client.execute(
                """
                WITH inserted AS (
                    INSERT INTO spree_order_promotions (order_id, promotion_id, created_at, updated_at)
                    VALUES ($1, $2, $3, $4)
                    RETURNING id
                )
                UPDATE spree_orders 
                SET updated_at = $3
                WHERE id = $1
                """,
                order_id,
                promotion_id,
                current_time,
                current_time,
            )
            created_count += 1

        except Exception as e:
            logger.warning(f"Error creating order promotion record: {e}")

    return created_count


async def seed_promotions():
    """Seed promotions into the database."""
    logger.start("Inserting promotions into spree_promotions table...")

    try:
        # Load promotions from JSON file
        if not PROMOTIONS_FILE.exists():
            logger.error(f"Promotions file not found at {PROMOTIONS_FILE}. Run generate command first.")
            raise FileNotFoundError("Promotions file not found")

        with Path.open(PROMOTIONS_FILE, encoding="utf-8") as f:
            data = json.load(f)

        promotions = data.get("promotions", [])
        logger.info(f"Loaded {len(promotions)} promotions from {PROMOTIONS_FILE}")

        # Current timestamp for created_at/updated_at
        current_time = datetime.now()

        for promotion in promotions:
            # Check if promotion already exists
            existing_promotion = await db_client.fetchrow("SELECT id FROM spree_promotions WHERE code = $1", promotion["code"])

            if existing_promotion:
                logger.info(f"Found existing promotion: {promotion['name']} ({promotion['code']})")

                # Create usage records immediately for existing promotions
                usage_count = promotion.get("usage_count")
                if usage_count and usage_count > 0 and promotion.get("usage_limit"):
                    await create_promotion_usage_records(existing_promotion["id"], usage_count)

                continue

            # Parse timestamps from ISO format
            try:
                starts_at = datetime.fromisoformat(promotion["starts_at"])
                expires_at = datetime.fromisoformat(promotion["expires_at"])
            except (ValueError, TypeError):
                # Fallback to generated timestamps if parsing fails
                starts_at = current_time
                expires_at = current_time + timedelta(days=30)
                logger.warning(f"Failed to parse timestamps for promotion {promotion['name']}, using defaults")

            # Insert new promotion
            promotion_id = await db_client.fetchval(
                """
                INSERT INTO spree_promotions (
                    description, expires_at, starts_at, name, type,
                    usage_limit, match_policy, code, advertise, path,
                    created_at, updated_at, promotion_category_id
                )
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13)
                RETURNING id
                """,
                promotion["description"],
                expires_at,
                starts_at,
                promotion["name"],
                promotion["type"],
                promotion["usage_limit"],
                promotion["match_policy"],
                promotion["code"],
                promotion["advertise"],
                promotion["path"],
                current_time,
                current_time,
                promotion["promotion_category_id"],
            )

            # Get store ID - default to 1 if not found
            store_id = await db_client.fetchval("SELECT id FROM spree_stores LIMIT 1") or 1

            # Associate promotion with store (required for promotions to show up in admin)
            await db_client.execute(
                """
                INSERT INTO spree_promotions_stores (promotion_id, store_id, created_at, updated_at)
                VALUES ($1, $2, $3, $4)
                ON CONFLICT (promotion_id, store_id) DO NOTHING
                """,
                promotion_id,
                store_id,
                current_time,
                current_time,
            )

            # Create usage records immediately after inserting promotion
            usage_count = promotion.get("usage_count")
            if usage_count is not None and usage_count > 0 and promotion.get("usage_limit"):
                await create_promotion_usage_records(promotion_id, usage_count)

        logger.succeed("Successfully seeded promotions")

    except Exception as e:
        logger.error(f"Error seeding promotions: {e}")
        raise
