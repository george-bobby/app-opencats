import asyncio
import random
from typing import Any

import aiohttp
from tenacity import retry, stop_after_attempt, wait_exponential

from apps.medusa.config.constants import PROMOTIONS_FILEPATH
from apps.medusa.utils.api_utils import MedusaAPIUtils
from apps.medusa.utils.data_utils import load_json_file
from common.logger import logger


def load_promotions_data() -> list[dict[str, Any]]:
    promotions = load_json_file(PROMOTIONS_FILEPATH, default=[])
    if not isinstance(promotions, list) or not promotions:
        logger.warning("No promotions data found")
        return []
    return promotions


def build_rules(promo_config: dict, customer_groups: list[dict], sales_channels: list[dict], regions: list[dict]) -> list[dict]:
    """Build promotion rules."""
    rules = []
    target_type = promo_config.get("target_type")
    is_automatic = promo_config.get("is_automatic", False)

    if is_automatic and target_type == "order":
        return []

    if customer_groups and random.random() < 0.5:
        group = random.choice(customer_groups)
        rules.append({"operator": "eq", "attribute": "customer.groups.id", "values": group["id"]})

    if sales_channels and random.random() < 0.3:
        channel = random.choice(sales_channels)
        rules.append({"operator": "in", "attribute": "sales_channel_id", "values": [channel["id"]]})

    if target_type == "shipping_methods" and regions:
        region = random.choice(regions)
        rules.append({"operator": "in", "attribute": "region.id", "values": [region["id"]]})

    if random.random() < 0.3:
        rules.append({"operator": "eq", "attribute": "shipping_address.country_code", "values": "us"})

    return rules


def build_target_rules(promo_config: dict, products: list[dict], categories: list[dict], product_types: list[dict]) -> list[dict]:
    """Build target rules for promotions."""
    target_rules = []
    target_type = promo_config.get("target_type")
    is_buyget = promo_config.get("is_buyget", False)

    if is_buyget and target_type == "items":
        if products and random.random() < 0.6:
            product = random.choice(products)
            target_rules.append({"operator": "eq", "attribute": "items.product.id", "values": product["id"]})
        elif categories:
            category = random.choice(categories)
            target_rules.append({"operator": "eq", "attribute": "items.product.categories.id", "values": category["id"]})

    elif target_type == "items" and not is_buyget:
        if categories and random.random() < 0.7:
            category = random.choice(categories)
            target_rules.append({"operator": "eq", "attribute": "items.product.categories.id", "values": category["id"]})
        elif product_types and random.random() < 0.3:
            ptype = random.choice(product_types)
            target_rules.append({"operator": "eq", "attribute": "items.product.type_id", "values": ptype["id"]})

    elif target_type == "shipping_methods":
        target_rules.append(
            {
                "operator": "eq",
                "attribute": "shipping_methods.shipping_option.shipping_option_type_id",
                "values": f"sotype_{''.join([random.choice('0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ') for _ in range(26)])}",
            }
        )

    return target_rules


def build_buy_rules(promo_config: dict, products: list[dict], categories: list[dict]) -> list[dict]:
    """Build buy rules for buy-get promotions."""
    if not promo_config.get("is_buyget"):
        return []

    buy_rules = []
    if products and random.random() < 0.6:
        product = random.choice(products)
        buy_rules.append({"operator": "eq", "attribute": "items.product.id", "values": product["id"]})
    elif categories:
        category = random.choice(categories)
        buy_rules.append({"operator": "eq", "attribute": "items.product.categories.id", "values": category["id"]})

    return buy_rules


def build_application_method(promo_config: dict, products: list[dict], categories: list[dict], product_types: list[dict]) -> dict:
    """Build application method for promotion."""
    app_method = {
        "allocation": promo_config["allocation"],
        "value": promo_config["value"],
        "type": promo_config["value_type"],
        "target_type": promo_config["target_type"],
        "target_rules": build_target_rules(promo_config, products, categories, product_types),
        "buy_rules": build_buy_rules(promo_config, products, categories),
    }

    if promo_config.get("needs_currency"):
        app_method["currency_code"] = "usd"

    app_method["max_quantity"] = promo_config.get("max_quantity", random.randint(1, 10)) if promo_config["allocation"] == "each" else None

    if promo_config.get("is_buyget"):
        app_method["apply_to_quantity"] = promo_config.get("apply_to_quantity", 1)
        app_method["buy_rules_min_quantity"] = promo_config.get("buy_rules_min_quantity", 2)

    return app_method


def prepare_payload(
    promo_data: dict,
    customer_groups: list[dict],
    sales_channels: list[dict],
    regions: list[dict],
    products: list[dict],
    categories: list[dict],
    product_types: list[dict],
) -> dict:
    """Prepare promotion payload."""
    promo_config = promo_data["promotion_config"]

    payload = {
        "code": promo_data["code"],
        "type": promo_data["type"],
        "is_automatic": promo_data.get("is_automatic", False),
    }

    if payload["is_automatic"]:
        payload["status"] = "draft"
    else:
        rand = random.random()
        payload["status"] = "active" if rand < 0.85 else "draft" if rand < 0.95 else "inactive"

    if promo_data.get("campaign"):
        campaign = promo_data["campaign"].copy()
        if "budget" in campaign and isinstance(campaign["budget"], dict):
            budget = campaign["budget"].copy()
            if "limit" in budget and budget["limit"] is not None:
                budget["limit"] = budget["limit"] / 100
            campaign["budget"] = budget
        payload["campaign"] = campaign

    if "is_tax_inclusive" in promo_data:
        payload["is_tax_inclusive"] = promo_data["is_tax_inclusive"]

    promo_config["is_automatic"] = payload["is_automatic"]
    payload["rules"] = build_rules(promo_config, customer_groups, sales_channels, regions)
    payload["application_method"] = build_application_method(promo_config, products, categories, product_types)

    return payload


async def promotion_exists(code: str, session: aiohttp.ClientSession, auth, base_url: str) -> bool:
    """Check if a promotion with given code already exists."""
    try:
        url = f"{base_url}/admin/promotions?code={code}"
        headers = auth.get_auth_headers()

        async with session.get(url, headers=headers) as response:
            if response.status == 200:
                data = await response.json()
                promotions = data.get("promotions", [])
                return len(promotions) > 0
    except Exception:
        pass

    return False


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=10))
async def create_promotion(
    promo_data: dict[str, Any],
    customer_groups: list[dict],
    sales_channels: list[dict],
    regions: list[dict],
    products: list[dict],
    categories: list[dict],
    product_types: list[dict],
    session: aiohttp.ClientSession,
    auth,
    base_url: str,
) -> bool:
    """Create a single promotion in Medusa."""
    code = promo_data.get("code")
    if not code:
        return False

    try:
        if await promotion_exists(code, session, auth, base_url):
            return True

        payload = prepare_payload(promo_data, customer_groups, sales_channels, regions, products, categories, product_types)
        url = f"{base_url}/admin/promotions"
        headers = auth.get_auth_headers()

        async with session.post(url, json=payload, headers=headers) as response:
            return response.status in (200, 201)

    except Exception:
        raise


async def load_medusa_dependencies() -> dict[str, Any]:
    """Load all required Medusa dependencies for promotion seeding."""
    async with MedusaAPIUtils() as api_utils:
        if not api_utils.auth:
            logger.error("Authentication failed")
            return {}

        customer_data = await api_utils.fetch_all_customer_data()
        catalog_data = await api_utils.fetch_all_catalog_data()
        products = await api_utils.fetch_products(limit=1000)
        regions = await api_utils.fetch_regions()

        usd_us_regions = [r for r in regions if r.get("currency_code", "").upper() == "USD" and any(c.get("iso_2", "").lower() == "us" for c in r.get("countries", []))]

        return {
            "customer_groups": customer_data["customer_groups"],
            "categories": catalog_data["categories"],
            "product_types": catalog_data["product_types"],
            "sales_channels": catalog_data["sales_channels"],
            "products": products,
            "regions": usd_us_regions,
            "auth": api_utils.auth,
            "base_url": api_utils.base_url,
        }


async def seed_promotions_internal(
    promotions_data: list[dict[str, Any]],
    dependencies: dict[str, Any],
    session: aiohttp.ClientSession,
) -> dict[str, int]:
    """Internal function to seed promotions."""
    logger.info(f"Seeding {len(promotions_data)} promotions")

    successful = 0
    failed = 0

    for promo_data in promotions_data:
        try:
            result = await create_promotion(
                promo_data,
                dependencies["customer_groups"],
                dependencies["sales_channels"],
                dependencies["regions"],
                dependencies["products"],
                dependencies["categories"],
                dependencies["product_types"],
                session,
                dependencies["auth"],
                dependencies["base_url"],
            )

            if result:
                successful += 1
            else:
                failed += 1
        except Exception:
            failed += 1

    logger.info(f"Promotions seeded: {successful} successful, {failed} failed")

    return {"total": len(promotions_data), "successful": successful, "failed": failed}


async def seed_promotions() -> dict[str, int]:
    promotions_data = load_promotions_data()

    if not promotions_data:
        return {"total": 0, "successful": 0, "failed": 0}

    dependencies = await load_medusa_dependencies()

    if not dependencies:
        return {"total": 0, "successful": 0, "failed": 0}

    async with aiohttp.ClientSession() as session:
        return await seed_promotions_internal(promotions_data, dependencies, session)


if __name__ == "__main__":
    asyncio.run(seed_promotions())
