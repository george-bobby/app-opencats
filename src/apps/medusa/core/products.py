import asyncio
from typing import Any

from tenacity import retry, stop_after_attempt, wait_exponential

from apps.medusa.config.settings import settings
from apps.medusa.utils.api_auth import get_medusa_auth_headers, get_medusa_base_url
from apps.medusa.utils.api_utils import MedusaAPIUtils
from apps.medusa.utils.data_utils import load_json_file
from common.logger import logger


def load_products_data() -> list[dict[str, Any]]:
    """Load products data from JSON file."""
    products_filepath = settings.DATA_PATH / "products.json"
    logger.info(f"Loading products from: {products_filepath}")

    products = load_json_file(products_filepath, default=[])
    if not isinstance(products, list) or not products:
        logger.warning("No products found in products.json or invalid format")
        return []

    logger.info(f"Successfully loaded {len(products)} products from file")
    return products


async def load_medusa_data() -> dict[str, list[dict[str, Any]]]:
    """Load all required data from Medusa."""
    try:
        logger.info("Fetching reference data from Medusa API...")
        async with MedusaAPIUtils() as api_utils:
            categories = await api_utils.fetch_categories()
            sales_channels = await api_utils.fetch_sales_channels()
            shipping_profiles = await api_utils.fetch_shipping_profiles()
            collections = await api_utils.fetch_collections()
            tags = await api_utils.fetch_tags()
            product_types = await api_utils.fetch_product_types()

        logger.info(
            f"Successfully fetched reference data - "
            f"Categories: {len(categories)}, "
            f"Sales Channels: {len(sales_channels)}, "
            f"Shipping Profiles: {len(shipping_profiles)}, "
            f"Collections: {len(collections)}, "
            f"Tags: {len(tags)}, "
            f"Product Types: {len(product_types)}"
        )

        return {
            "categories": categories,
            "sales_channels": sales_channels,
            "shipping_profiles": shipping_profiles,
            "collections": collections,
            "tags": tags,
            "product_types": product_types,
        }
    except Exception as e:
        logger.error(f"Error loading Medusa data: {e}")
        raise


def build_mapping_dictionaries(medusa_data: dict[str, list[dict[str, Any]]]) -> dict[str, dict[str, str]]:
    """Build mapping dictionaries from Medusa data."""
    logger.info("Building mapping dictionaries from Medusa data...")

    category_map: dict[str, str] = {}
    collection_map: dict[str, str] = {}
    tag_map: dict[str, str] = {}
    type_map: dict[str, str] = {}
    sales_channel_map: dict[str, str] = {}
    shipping_profile_map: dict[str, str] = {}

    for category in medusa_data.get("categories", []):
        name = category.get("name", "").lower()
        if name and category.get("id"):
            category_map[name] = category["id"]

    for collection in medusa_data.get("collections", []):
        title = collection.get("title", "").lower()
        if title and collection.get("id"):
            collection_map[title] = collection["id"]

    for tag in medusa_data.get("tags", []):
        value = tag.get("value", tag.get("name", "")).lower()
        if value and tag.get("id"):
            tag_map[value] = tag["id"]

    for ptype in medusa_data.get("product_types", []):
        value = ptype.get("value", ptype.get("name", "")).lower()
        if value and ptype.get("id"):
            type_map[value] = ptype["id"]

    for channel in medusa_data.get("sales_channels", []):
        name = channel.get("name", "").lower()
        if name and channel.get("id"):
            sales_channel_map[name] = channel["id"]

    for profile in medusa_data.get("shipping_profiles", []):
        name = profile.get("name", "").lower()
        if name and profile.get("id"):
            shipping_profile_map[name] = profile["id"]

    logger.info(
        f"Mapping dictionaries built - "
        f"Categories: {len(category_map)}, "
        f"Collections: {len(collection_map)}, "
        f"Tags: {len(tag_map)}, "
        f"Types: {len(type_map)}, "
        f"Sales Channels: {len(sales_channel_map)}, "
        f"Shipping Profiles: {len(shipping_profile_map)}"
    )

    return {
        "category_map": category_map,
        "collection_map": collection_map,
        "tag_map": tag_map,
        "type_map": type_map,
        "sales_channel_map": sales_channel_map,
        "shipping_profile_map": shipping_profile_map,
    }


def prepare_product_payload(product_data: dict[str, Any], mappings: dict[str, dict[str, str]]) -> dict[str, Any]:
    """Prepare product payload for Medusa API."""
    excluded_fields = {"id", "created_at", "updated_at", "deleted_at", "profile_id", "category", "collection", "tags", "type", "sales_channels", "shipping_profile"}

    payload = {k: v for k, v in product_data.items() if k not in excluded_fields}

    if not payload.get("title"):
        raise ValueError("Product missing title")

    # Convert category name to ID
    category_name = product_data.get("category")
    if category_name:
        category_id = mappings["category_map"].get(category_name.lower())
        if category_id:
            payload["categories"] = [{"id": category_id}]

    # Convert collection title to ID
    collection_name = product_data.get("collection")
    if collection_name:
        collection_id = mappings["collection_map"].get(collection_name.lower())
        if collection_id:
            payload["collection_id"] = collection_id

    # Convert tag values to IDs
    tag_values = product_data.get("tags")
    if tag_values and isinstance(tag_values, list):
        tag_ids = []
        for tag_value in tag_values:
            tag_id = mappings["tag_map"].get(str(tag_value).lower())
            if tag_id:
                tag_ids.append({"id": tag_id})
        if tag_ids:
            payload["tags"] = tag_ids

    # Convert type value to ID
    type_value = product_data.get("type")
    if type_value:
        type_id = mappings["type_map"].get(type_value.lower())
        if type_id:
            payload["type_id"] = type_id

    # Convert sales channel names to IDs
    channel_names = product_data.get("sales_channels")
    if not channel_names or not isinstance(channel_names, list):
        official_id = mappings["sales_channel_map"].get("official website")
        if official_id:
            payload["sales_channels"] = [{"id": official_id}]
        else:
            payload["sales_channels"] = []
    else:
        channel_ids = []
        for channel_name in channel_names:
            channel_id = mappings["sales_channel_map"].get(str(channel_name).lower())
            if channel_id:
                channel_ids.append({"id": channel_id})
        if not channel_ids:
            official_id = mappings["sales_channel_map"].get("official website")
            if official_id:
                channel_ids.append({"id": official_id})
        payload["sales_channels"] = channel_ids

    # Convert shipping profile name to ID
    profile_name = product_data.get("shipping_profile")
    if not profile_name:
        shipping_profile_id = mappings["shipping_profile_map"].get("standard shipping")
    else:
        profile_id = mappings["shipping_profile_map"].get(profile_name.lower())
        shipping_profile_id = profile_id if profile_id else mappings["shipping_profile_map"].get("standard shipping")
    if shipping_profile_id:
        payload["shipping_profile_id"] = shipping_profile_id

    if "variants" in payload:
        cleaned_variants = []
        for variant in payload["variants"]:
            cleaned = {k: v for k, v in variant.items() if k not in {"id", "created_at", "updated_at", "deleted_at", "product_id", "inventory_items"}}

            if cleaned.get("prices"):
                cleaned["prices"] = [{k: v for k, v in price.items() if k in {"currency_code", "amount"}} for price in cleaned["prices"]]

            cleaned_variants.append(cleaned)
        payload["variants"] = cleaned_variants

    if "options" in payload:
        payload["options"] = [{k: v for k, v in opt.items() if k not in {"id", "created_at", "updated_at", "deleted_at", "product_id"}} for opt in payload["options"]]

    if "images" in payload and not payload["images"]:
        del payload["images"]

    return payload


@retry(wait=wait_exponential(multiplier=1, min=2, max=10), stop=stop_after_attempt(3))
async def create_product(session: Any, product_data: dict[str, Any], mappings: dict[str, dict[str, str]]) -> bool:
    """Create a product in Medusa."""
    if not session:
        return False

    try:
        payload = prepare_product_payload(product_data, mappings)

        base_url = get_medusa_base_url()
        url = f"{base_url}/admin/products"
        headers = get_medusa_auth_headers()

        async with session.post(url, json=payload, headers=headers) as response:
            if response.status in (200, 201):
                return True
            else:
                response_data = await response.json()
                return bool(response_data.get("type") == "invalid_data" and "already exists" in response_data.get("message", "").lower())

    except Exception:
        return False


async def seed_products_internal(session: Any, products: list[dict[str, Any]], mappings: dict[str, dict[str, str]]) -> dict[str, int]:
    """Internal function to seed products."""
    if not products:
        logger.warning("No products to seed")
        return {"total": 0, "successful": 0, "failed": 0}

    total = len(products)
    logger.info(f"Starting product seeding process - Total products: {total}")

    successful = 0
    failed = 0

    for idx, product in enumerate(products, 1):
        product_title = product.get("title", "Unknown")
        logger.info(f"[{idx}/{total}] Seeding product: '{product_title}'")

        result = await create_product(session, product, mappings)

        if result:
            successful += 1
            logger.info(f"[{idx}/{total}] ✓ Successfully seeded: '{product_title}'")
        else:
            failed += 1
            logger.error(f"[{idx}/{total}] ✗ Failed to seed: '{product_title}'")

    logger.info(f"Product seeding completed - Total: {total}, Successful: {successful}, Failed: {failed}, Success Rate: {(successful / total * 100):.1f}%")

    return {"total": total, "successful": successful, "failed": failed}


async def seed_products():
    """Seed products into Medusa."""
    import aiohttp

    logger.info("=" * 60)
    logger.info("Starting Product Seeding Script")
    logger.info("=" * 60)

    products = load_products_data()
    if not products:
        logger.warning("No products to seed. Exiting.")
        return {"total": 0, "successful": 0, "failed": 0}

    medusa_data = await load_medusa_data()
    mappings = build_mapping_dictionaries(medusa_data)

    async with aiohttp.ClientSession() as session:
        result = await seed_products_internal(session, products, mappings)

    logger.info("=" * 60)
    logger.info("Product Seeding Script Completed")
    logger.info("=" * 60)

    return result


if __name__ == "__main__":
    asyncio.run(seed_products())
