import json
import random
from datetime import timedelta
from pathlib import Path

from apps.gumroad.config.settings import settings
from apps.gumroad.utils.faker import faker
from apps.gumroad.utils.gumroad import GumroadAPI
from common.logger import logger


# File paths
DISCOUNTS_FILE = settings.DATA_PATH / "generated" / "discounts.json"


async def generate_discounts(number_of_discounts: int):
    """Generate fake discount data and save to JSON file."""
    discounts = []

    # Discount code prefixes and names for variety
    discount_types = [
        ("WELCOME", "Welcome"),
        ("SUMMER", "Summer Sale"),
        ("WINTER", "Winter Special"),
        ("SPRING", "Spring Offer"),
        ("FALL", "Fall Promo"),
        ("BUNDLE", "Bundle Deal"),
        ("VIP", "VIP Access"),
        ("LOYALTY", "Loyalty Reward"),
        ("FLASH", "Flash Sale"),
        ("WEEKEND", "Weekend Special"),
        ("HOLIDAY", "Holiday Discount"),
        ("NEWBIE", "New Customer"),
        ("COMEBACK", "Comeback Offer"),
        ("PREMIUM", "Premium Access"),
        ("EXCLUSIVE", "Exclusive Deal"),
    ]

    # Product categories for non-universal discounts
    product_categories = [
        "photo_bundles",
        "lightroom_presets",
        "landscape_collections",
        "portrait_packs",
        "seasonal_packs",
        "premium_filters",
        "editing_tools",
        "stock_photos",
        "digital_art",
        "templates",
    ]

    for _ in range(number_of_discounts):
        # Random discount type
        discount_prefix, discount_name = faker.random_element(discount_types)

        # Generate discount percentage (5-50%)
        discount_percentage = faker.random_element([5, 10, 15, 20, 25, 30, 35, 40, 45, 50])

        # Create discount code
        discount_code = f"{discount_prefix}{discount_percentage}"
        if faker.boolean(chance_of_getting_true=30):  # 30% chance to add random suffix
            discount_code += str(faker.random_int(min=1, max=99))

        # Create discount name
        full_name = f"{discount_name} {discount_percentage}"

        # Determine if universal (70% chance of being universal)
        is_universal = faker.boolean(chance_of_getting_true=70)

        discount = {"name": full_name, "code": discount_code, "amount_percentage": discount_percentage, "universal": is_universal}

        # Add product selection for non-universal discounts
        if not is_universal:
            num_products = faker.random_int(min=1, max=3)
            selected_products = faker.random_elements(elements=product_categories, length=num_products, unique=True)
            discount["selected_product_ids"] = selected_products

        # Add validity dates (50% chance)
        if faker.boolean(chance_of_getting_true=50):
            # Valid from date (within next 30 days)
            valid_from = faker.date_time_between(start_date="now", end_date="+30d")
            discount["valid_at"] = valid_from.isoformat() + "Z"

            # Expires date (30-90 days after valid date)
            expires_at = valid_from + timedelta(days=faker.random_int(min=30, max=90))
            discount["expires_at"] = expires_at.isoformat() + "Z"
        else:
            discount["valid_at"] = None
            discount["expires_at"] = None

        # Add notes
        notes_options = [
            "Limited time offer for new customers",
            "Seasonal promotion with limited availability",
            "Exclusive discount for loyal customers",
            "Special bundle pricing incentive",
            "Flash sale for premium content",
            "Weekend special promotion",
            "Holiday celebration discount",
            "New product launch promotion",
            "Customer appreciation offer",
            "Limited quantity discount code",
        ]
        discount["notes"] = faker.random_element(notes_options)

        discounts.append(discount)

    # Save to generated data file
    DISCOUNTS_FILE.parent.mkdir(parents=True, exist_ok=True)

    with Path.open(DISCOUNTS_FILE, "w") as f:
        json.dump(discounts, f, indent=4)

    logger.info(f"Generated {number_of_discounts} discounts and saved to {DISCOUNTS_FILE}")
    return discounts


async def seed_discounts():
    async with GumroadAPI() as gumroad:
        logger.start("Seeding discounts...")
        # First, get available products to select from for non-universal discounts
        products = await gumroad.get_all_products()
        available_products = []

        if products:
            # Extract product IDs from the products list
            available_products = [str(product["id"]) for product in products if product.get("id")]
        else:
            logger.warning("Could not fetch products, will use original product IDs")

        with Path.open(DISCOUNTS_FILE) as f:
            discounts = json.load(f)

        for discount in discounts:
            try:
                # For non-universal discounts, randomly select products if available
                if not discount.get("universal", True) and available_products:
                    # Randomly select 1-3 products for the discount
                    num_products = random.randint(1, min(3, len(available_products)))
                    selected_products = random.sample(available_products, num_products)
                    discount["selected_product_ids"] = selected_products
                    logger.info(f"Selected random products for discount '{discount.get('name')}': {selected_products}")

                # Filter out unsupported parameters (like 'notes')
                supported_params = {
                    "name",
                    "code",
                    "amount_percentage",
                    "amount_cents",
                    "selected_product_ids",
                    "universal",
                    "max_purchase_count",
                    "currency_type",
                    "valid_at",
                    "expires_at",
                    "minimum_quantity",
                    "duration_in_billing_cycles",
                    "minimum_amount_cents",
                }
                filtered_discount = {k: v for k, v in discount.items() if k in supported_params}
                # logger.info(
                #     f"Filtered discount: {json.dumps(filtered_discount, indent=4)}"
                # )

                await gumroad.add_discount(**filtered_discount)
                logger.info(f"Successfully created discount: {discount.get('name', 'Unknown')}")
            except Exception as e:
                logger.error(f"Failed to create discount {discount.get('name', 'Unknown')}: {e!s}")
        logger.succeed("Discounts seeded successfully")


async def update_checkout_form():
    async with GumroadAPI() as gumroad:
        logger.start("Updating checkout form...")
        # Load checkout form configuration from JSON file
        with Path.open(settings.DATA_PATH / "checkout_form.json") as f:
            form_config = json.load(f)

        user_settings = form_config.get("user_settings", {})
        custom_fields = form_config.get("custom_fields", [])

        try:
            result = await gumroad.set_checkout_form(user_settings=user_settings, custom_fields=custom_fields)

            if result.get("status_code") in [200, 201]:
                logger.info("Successfully updated checkout form configuration")
                logger.info(f"Applied {len(custom_fields)} custom fields")
                for field in custom_fields:
                    logger.info(f"  - {field['name']} ({'required' if field['required'] else 'optional'})")
            else:
                logger.error(f"Failed to update checkout form: {result}")

        except Exception as e:
            logger.error(f"Error updating checkout form: {e!s}")
    logger.succeed("Checkout form updated successfully")
