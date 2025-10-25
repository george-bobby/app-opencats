import asyncio
import json
from pathlib import Path

from apps.medusa.config.constants import CATEGORIES_FILEPATH, MAPPING_BATCH_SIZE, PRODUCTS_FILEPATH
from apps.medusa.config.settings import settings
from apps.medusa.core.generate.prompts.product_mapping_prompt import (
    EXAMPLES_SECTION,
    FALLBACK_MAPPING_RULES,
    SYSTEM_PROMPT,
    USER_PROMPT,
)
from common.anthropic_client import make_anthropic_request, parse_anthropic_response, validate_anthropic_config
from common.logger import logger
from common.save_to_json import save_to_json


def load_json_file(filepath: Path) -> list[dict]:
    if not filepath.exists():
        logger.error(f"File not found: {filepath}")
        return []

    try:
        with filepath.open(encoding="utf-8") as f:
            data = json.load(f)
            logger.info(f"Loaded {len(data)} items from {filepath}")
            return data
    except Exception as e:
        logger.error(f"Error loading {filepath}: {e}")
        return []


def ensure_product_ids(products: list[dict]) -> list[dict]:
    for i, product in enumerate(products):
        if not product.get("id") and not product.get("product_id"):
            title = product.get("title") or product.get("name", f"product_{i}")
            product["id"] = f"temp_{i}_{title[:20].replace(' ', '_').lower()}"
            logger.debug(f"Generated temporary ID for product: {product['id']}")
    return products


def create_mapping_prompt(categories: list[dict], products_batch: list[dict]) -> str:
    category_names = [cat.get("name") for cat in categories if cat.get("name") and cat.get("is_active", True)]

    categories_list = "\n".join(f"- {cat}" for cat in sorted(category_names))

    products_list = ""
    for product in products_batch:
        product_id = product.get("id") or product.get("product_id")
        product_type = product.get("type", "Unknown")
        name = product.get("title") or product.get("name", "")

        products_list += f"""Product ID: {product_id}
Product Type: {product_type}
Name: {name}

"""

    user_prompt = USER_PROMPT.format(categories_list=categories_list, products_list=products_list.strip())

    return f"{SYSTEM_PROMPT}\n\n{EXAMPLES_SECTION}\n\n{user_prompt}"


def apply_fallback_mapping(product: dict, valid_categories: set[str]) -> str | None:
    product_type = (product.get("type", "") or "").lower()
    product_name = (product.get("title") or product.get("name", "")).lower()
    search_text = f"{product_type} {product_name}"

    sorted_rules = sorted(FALLBACK_MAPPING_RULES.items(), key=lambda x: len(x[0]), reverse=True)

    for keyword, category in sorted_rules:
        if keyword in search_text and category in valid_categories:
            return category

    return None


async def map_products_batch(categories: list[dict], products_batch: list[dict]) -> list[dict]:
    logger.info(f"Creating prompt for {len(products_batch)} products...")
    prompt = create_mapping_prompt(categories, products_batch)

    logger.debug(f"Prompt length: {len(prompt)} characters")

    logger.info("Sending request to Anthropic API...")
    response_data = await make_anthropic_request(prompt=prompt, api_key=settings.ANTHROPIC_API_KEY, max_tokens=4000, temperature=0.3)

    if not response_data:
        logger.error("No response received from Anthropic API")
        raise Exception("Failed to get response from Anthropic API")

    if "error" in response_data:
        error_type = response_data["error"].get("type", "")
        error_message = response_data["error"].get("message", "")
        logger.error(f"API returned error - Type: {error_type}, Message: {error_message}")
        raise Exception(f"API error: {error_type} - {error_message}")

    logger.info("Parsing response from Anthropic...")
    mappings = parse_anthropic_response(response_data)

    if not mappings:
        logger.error("Failed to parse mappings from response")
        raise Exception("Invalid mapping data format from Anthropic")

    logger.info(f"✓ Successfully received {len(mappings)} mappings from API")

    return mappings


def validate_mappings(mappings: list[dict], valid_categories: set[str], products_batch: list[dict]) -> list[dict]:
    logger.info(f"Validating {len(mappings)} mappings...")

    validated = []
    mapping_dict = {str(m.get("product_id")): m.get("category") for m in mappings}

    for product in products_batch:
        product_id = str(product.get("id") or product.get("product_id"))
        category = mapping_dict.get(product_id)

        if category and category in valid_categories:
            validated.append({"product_id": product_id, "category": category})
        else:
            if category:
                logger.warning(f"Invalid category '{category}' for product {product_id}, trying fallback")

            fallback_category = apply_fallback_mapping(product, valid_categories)

            if fallback_category:
                logger.info(f"✓ Fallback mapped product {product_id} → {fallback_category}")
                validated.append({"product_id": product_id, "category": fallback_category})
            else:
                logger.warning(f"⚠️  Could not map product {product_id}: {product.get('type', 'N/A')}")

    logger.info(f"✓ Validated {len(validated)}/{len(products_batch)} mappings")

    category_usage = {}
    for mapping in validated:
        cat = mapping["category"]
        category_usage[cat] = category_usage.get(cat, 0) + 1

    logger.info("Category usage in this batch:")
    for cat, count in sorted(category_usage.items(), key=lambda x: x[1], reverse=True)[:10]:
        percentage = (count / len(validated) * 100) if validated else 0
        logger.info(f"  {cat}: {count} products ({percentage:.1f}%)")

    return validated


def update_products_with_mappings(products: list[dict], mappings: list[dict]) -> tuple[list[dict], int]:
    mapping_dict = {}
    for mapping in mappings:
        product_id = mapping.get("product_id")
        category = mapping.get("category")
        if product_id and category:
            mapping_dict[str(product_id)] = category

    updated_count = 0

    for product in products:
        product_id = str(product.get("id") or product.get("product_id"))

        if product_id in mapping_dict:
            product["category"] = mapping_dict[product_id]
            updated_count += 1

    return products, updated_count


async def map_products_to_categories_ai() -> dict:
    logger.info("=" * 80)
    logger.info("🤖 Starting AI-powered product-category mapping process")
    logger.info("=" * 80)

    settings.DATA_PATH.mkdir(parents=True, exist_ok=True)
    validate_anthropic_config(settings.ANTHROPIC_API_KEY)

    products = load_json_file(PRODUCTS_FILEPATH)
    categories = load_json_file(CATEGORIES_FILEPATH)

    if not products:
        logger.error("No products found to map")
        return {"total_mapped": 0, "total_products": 0}

    logger.info("Ensuring all products have IDs...")
    products = ensure_product_ids(products)

    if not categories:
        logger.error("No categories found for mapping")
        return {"total_mapped": 0, "total_products": len(products)}

    logger.info(f"📦 Loaded {len(products)} products and {len(categories)} categories")

    valid_categories = {cat.get("name") for cat in categories if cat.get("name") and cat.get("is_active", True)}
    logger.info(f"✓ {len(valid_categories)} active categories available")
    logger.info(f"✓ Loaded {len(FALLBACK_MAPPING_RULES)} fallback mapping rules")

    logger.info(f"📊 Batch size: {MAPPING_BATCH_SIZE} products per API call")
    logger.info(f"📊 Total batches to process: {(len(products) + MAPPING_BATCH_SIZE - 1) // MAPPING_BATCH_SIZE}")

    try:
        total_mapped = 0
        batch_count = 0
        all_mappings = []

        for i in range(0, len(products), MAPPING_BATCH_SIZE):
            batch_count += 1
            batch = products[i : i + MAPPING_BATCH_SIZE]

            logger.info("")
            logger.info(f"{'=' * 60}")
            logger.info(f"📦 BATCH {batch_count}/{(len(products) + MAPPING_BATCH_SIZE - 1) // MAPPING_BATCH_SIZE}")
            logger.info(f"{'=' * 60}")
            logger.info(f"Processing products {i + 1} to {min(i + MAPPING_BATCH_SIZE, len(products))}")

            try:
                mappings = await map_products_batch(categories, batch)
                validated_mappings = validate_mappings(mappings, valid_categories, batch)

                all_mappings.extend(validated_mappings)
                total_mapped += len(validated_mappings)

                logger.info(f"✓ Batch {batch_count} complete - Mapped {len(validated_mappings)}/{len(batch)} products")
                logger.info(f"📊 Overall progress: {total_mapped}/{len(products)} products mapped ({total_mapped / len(products) * 100:.1f}%)")

            except Exception as e:
                logger.error(f"❌ Batch {batch_count} failed: {e}")

                logger.info("Attempting fallback mapping for failed batch...")
                fallback_mappings = []
                for product in batch:
                    product_id = str(product.get("id") or product.get("product_id"))
                    fallback_category = apply_fallback_mapping(product, valid_categories)
                    if fallback_category:
                        fallback_mappings.append({"product_id": product_id, "category": fallback_category})

                if fallback_mappings:
                    logger.info(f"✓ Fallback mapped {len(fallback_mappings)}/{len(batch)} products")
                    all_mappings.extend(fallback_mappings)
                    total_mapped += len(fallback_mappings)

                continue

        logger.info("")
        logger.info("=" * 80)
        logger.info("📊 FINAL RESULTS")
        logger.info("=" * 80)

        if all_mappings:
            logger.info(f"✓ Total mappings generated: {len(all_mappings)}")

            updated_products, update_count = update_products_with_mappings(products, all_mappings)

            logger.info(f"💾 Saving {update_count} updated products to {PRODUCTS_FILEPATH}")
            save_to_json(updated_products, PRODUCTS_FILEPATH)
            logger.info("✓ Successfully saved updated products")

            logger.info("")
            logger.info(f"✅ SUCCESS: Updated {update_count}/{len(products)} products ({update_count / len(products) * 100:.1f}%)")
            logger.info(f"⚠️  Unmapped: {len(products) - update_count} products")

            return {
                "total_mapped": total_mapped,
                "total_updated": update_count,
                "total_products": len(products),
                "unmapped_products": len(products) - update_count,
                "success_rate": f"{update_count / len(products) * 100:.1f}%",
            }
        else:
            logger.error("❌ No mappings were generated")
            return {"total_mapped": 0, "total_updated": 0, "total_products": len(products), "unmapped_products": len(products), "success_rate": "0.0%"}

    except Exception as error:
        logger.error(f"💥 Fatal error during mapping: {error}")
        import traceback

        logger.error(f"Full error trace: {traceback.format_exc()}")
        raise


async def products_mapping():
    result = await map_products_to_categories_ai()
    logger.info(f"Mapping complete - Updated {result.get('total_updated', 0)}/{result.get('total_products', 0)} products")
    logger.info(f"Success rate: {result.get('success_rate', '0.0%')}")
    return result


if __name__ == "__main__":
    asyncio.run(products_mapping())
