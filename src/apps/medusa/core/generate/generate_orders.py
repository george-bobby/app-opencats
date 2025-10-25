import asyncio
import random
from typing import Any

from apps.medusa.config.constants import ORDERS_FILEPATH, SALES_CHANNELS, US_ADDRESS_TEMPLATES
from apps.medusa.config.settings import settings
from apps.medusa.utils.api_utils import MedusaAPIUtils
from apps.medusa.utils.data_utils import load_json_file
from common.logger import logger
from common.save_to_json import save_to_json


async def load_order_dependencies() -> dict[str, Any]:
    """Load customers, customer groups, and products."""
    customers_filepath = settings.DATA_PATH / "customers.json"
    customer_groups_filepath = settings.DATA_PATH / "customer_groups.json"

    try:
        customers = load_json_file(customers_filepath, [])
        customer_groups = load_json_file(customer_groups_filepath, [])

        async with MedusaAPIUtils() as api_utils:
            products = await api_utils.fetch_products(limit=1000)

        if not customers:
            raise ValueError("No customers found. Please generate customers first.")
        if not products:
            raise ValueError("No products found in Medusa. Please seed products first.")
        if not customer_groups:
            raise ValueError("No customer groups found. Please generate customer groups first.")

        logger.info(f"Loaded {len(customers)} customers, {len(customer_groups)} groups, {len(products)} products")

        return {
            "customers": customers,
            "customer_groups": customer_groups,
            "products": products,
        }

    except FileNotFoundError as e:
        raise ValueError(f"Required data file not found: {e}")
    except Exception as e:
        raise ValueError(f"Error loading data: {e}")


def get_orders_count_for_group(group_name: str) -> int:
    """Get order count range based on customer group."""
    group_mapping = {
        "Diamond Group": (15, 20),
        "Platinum Group": (10, 15),
        "Gold Group": (8, 12),
        "Silver Group": (5, 8),
    }
    min_orders, max_orders = group_mapping.get(group_name, (1, 3))
    return random.randint(min_orders, max_orders)


def select_sales_channel() -> str:
    """Select a sales channel with 75% bias towards Official Website."""
    if random.random() < 0.75:
        return "Official Website"
    other_channels = [ch for ch in SALES_CHANNELS if ch != "Official Website"]
    return random.choice(other_channels)


def select_random_items(products: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Select random product items for an order."""
    if not products:
        raise ValueError("No products available to select items from")

    valid_products = [p for p in products if p.get("variants")]

    if not valid_products:
        raise ValueError("No products with variants found")

    num_items = random.randint(1, min(4, len(valid_products)))
    selected_products = random.sample(valid_products, num_items)

    items = []
    for product in selected_products:
        variant = random.choice(product.get("variants", []))
        items.append(
            {
                "product_title": product.get("title"),
                "variant_title": variant.get("title"),
                "quantity": random.randint(1, 3),
            }
        )

    return items


def generate_phone_number() -> str:
    """Generate a random US phone number."""
    pattern = random.choice(["(###) ###-####", "###-###-####", "###.###.####"])
    return "".join(str(random.randint(0, 9)) if char == "#" else char for char in pattern)


def generate_address(first_name: str | None = None, last_name: str | None = None) -> dict[str, Any]:
    """Generate a random US address."""

    region_key = random.choice(list(US_ADDRESS_TEMPLATES.keys()))
    template = US_ADDRESS_TEMPLATES[region_key]
    city_index = random.randint(0, len(template["cities"]) - 1)

    postal_pattern = random.choice(["#####", "#####-####"])
    postal_code = "".join(str(random.randint(0, 9)) if char == "#" else char for char in postal_pattern)

    street_names = ["Main Street", "Oak Street", "Park Avenue", "First Avenue", "Broadway", "Washington Street"]
    address_1 = f"{random.randint(1, 9999)} {random.choice(street_names)}"
    address_2 = f"Apt {random.randint(1, 999)}" if random.random() < 0.3 else ""

    companies = ["", "TechCorp Inc", "Fashion House LLC", "Style Solutions", "American Apparel Co"]

    return {
        "first_name": first_name or "John",
        "last_name": last_name or "Doe",
        "address_1": address_1,
        "address_2": address_2,
        "city": template["cities"][city_index],
        "province": template["states"][city_index],
        "postal_code": postal_code,
        "country_code": "us",
        "company": random.choice(companies),
        "phone": generate_phone_number(),
    }


def generate_order_data(customer_email: str | None, customers: list[dict[str, Any]], products: list[dict[str, Any]]) -> dict[str, Any]:
    """Generate a single order data structure."""
    customer = next((c for c in customers if c.get("email") == customer_email), None)

    first_name = customer.get("first_name") if customer else "John"
    last_name = customer.get("last_name") if customer else "Doe"

    billing_address = generate_address(first_name, last_name)
    shipping_address = billing_address.copy() if random.random() < 0.8 else generate_address(first_name, last_name)

    return {
        "customer_email": customer_email,
        "sales_channel": select_sales_channel(),
        "items": select_random_items(products),
        "billing_address": billing_address,
        "shipping_address": shipping_address,
    }


def generate_orders_data(customers: list[dict[str, Any]], customer_groups: list[dict[str, Any]], products: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Generate orders for all customers based on their groups."""
    orders = []
    customers_with_orders = set()

    for group in customer_groups:
        group_name = group.get("name", "")
        customer_emails = group.get("customer_emails", [])

        if not customer_emails:
            continue

        orders_count = get_orders_count_for_group(group_name)

        for customer_email in customer_emails:
            customers_with_orders.add(customer_email)
            for _ in range(orders_count):
                orders.append(generate_order_data(customer_email, customers, products))

    all_customer_emails = {c.get("email") for c in customers if c.get("email")}
    remaining_customers = all_customer_emails - customers_with_orders

    if remaining_customers:
        for customer_email in remaining_customers:
            orders.append(generate_order_data(customer_email, customers, products))

    logger.info(f"Generated {len(orders)} orders")
    return orders


async def orders() -> dict[str, Any]:
    """Main function to generate orders."""
    logger.info("Starting orders generation")

    settings.DATA_PATH.mkdir(parents=True, exist_ok=True)

    generated_orders: list[dict[str, Any]] = []

    try:
        dependencies = await load_order_dependencies()

        generated_orders = generate_orders_data(customers=dependencies["customers"], customer_groups=dependencies["customer_groups"], products=dependencies["products"])

        if generated_orders:
            save_to_json(generated_orders, ORDERS_FILEPATH)
            logger.info(f"Saved {len(generated_orders)} orders to {ORDERS_FILEPATH}")

        total_items = sum(len(order.get("items", [])) for order in generated_orders)

        return {
            "total_processed": len(generated_orders),
            "total_items": total_items,
            "orders": generated_orders,
        }

    except Exception as error:
        logger.error(f"Fatal error during generation: {error}")
        if generated_orders:
            save_to_json(generated_orders, ORDERS_FILEPATH)
        raise


if __name__ == "__main__":
    asyncio.run(orders())
