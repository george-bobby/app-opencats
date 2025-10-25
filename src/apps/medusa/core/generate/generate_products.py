import asyncio
import json
import random
import re
import traceback

from tenacity import (
    after_log,
    before_sleep_log,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from apps.medusa.config.constants import (
    CATEGORIES_FILEPATH,
    COLLECTIONS_FILEPATH,
    DEFAULT_CATEGORY_NAME,
    DEFAULT_ORIGIN_COUNTRY,
    DEFAULT_PRODUCT_TYPE,
    DEFAULT_PRODUCTS_COUNT,
    DEFAULT_SHIPPING_PROFILE,
    HS_CODE_MAP,
    KEYWORD_EXTRACT_FIELDS,
    MATERIAL_KEYWORDS,
    MAX_API_TOKENS,
    MAX_PRODUCTS_PER_BATCH,
    MAX_RETRIES,
    MIN_KEYWORD_LENGTH,
    PRODUCT_TYPE_DIMENSIONS,
    PRODUCTS_FILEPATH,
    RECENT_PRODUCTS_CONTEXT_LIMIT,
    RELEVANT_COLLECTIONS_SAMPLE_SIZE,
    RELEVANT_TAGS_LIMIT,
    RELEVANT_TAGS_SAMPLE_SIZE,
    RELEVANT_TYPES_LIMIT,
    RELEVANT_TYPES_SAMPLE_SIZE,
    REQUIRED_VARIANT_ATTRIBUTES,
    SALES_CHANNEL_PROBABILITY,
    SALES_CHANNELS,
    SIZE_MULTIPLIERS,
    TAGS_FILEPATH,
    TYPE_MATERIAL_MAP,
    TYPES_FILEPATH,
)
from apps.medusa.config.settings import settings
from apps.medusa.core.generate.prompts.generate_products_prompts import (
    EXISTING_PRODUCTS_CONTEXT_TEMPLATE,
    SYSTEM_PROMPT,
    USER_PROMPT,
)
from apps.medusa.utils.data_utils import load_json_file
from common.anthropic_client import make_anthropic_request, validate_anthropic_config
from common.logger import logger
from common.save_to_json import save_to_json


def load_catalog_data() -> dict:
    catalog_files = {
        "categories": CATEGORIES_FILEPATH,
        "collections": COLLECTIONS_FILEPATH,
        "product_types": TYPES_FILEPATH,
        "tags": TAGS_FILEPATH,
    }

    catalog_data = {}
    for attr_name, filepath in catalog_files.items():
        if filepath.exists():
            catalog_data[attr_name] = load_json_file(filepath, default=[])
            logger.info(f"Loaded {len(catalog_data[attr_name])} {attr_name}")
        else:
            logger.warning(f"File not found: {filepath}")
            catalog_data[attr_name] = []

    return catalog_data


def extract_keywords(data: dict, fields: list[str] | None = None) -> set[str]:
    if fields is None:
        fields = KEYWORD_EXTRACT_FIELDS

    keywords = set()
    for field in fields:
        value = data.get(field, "")
        if value:
            words = value.lower().replace("-", " ").replace("_", " ").split()
            keywords.update(word for word in words if len(word) > MIN_KEYWORD_LENGTH)

    return keywords


def find_relevant_types(category: dict, product_types: list[dict]) -> list[dict]:
    if not product_types:
        return []

    category_keywords = extract_keywords(category)
    relevant = []
    generic_types = []

    for ptype in product_types:
        type_value = ptype.get("value", "").lower()
        type_words = set(type_value.replace("-", " ").split())

        if any(keyword in type_value for keyword in category_keywords) or any(keyword in category_keywords for keyword in type_words):
            relevant.append(ptype)
        else:
            generic_types.append(ptype)

    if relevant:
        return relevant

    if generic_types:
        sample_size = min(RELEVANT_TYPES_SAMPLE_SIZE, len(generic_types))
        return random.sample(generic_types, sample_size)

    return []


def find_relevant_collections(category: dict, collections: list[dict]) -> list[dict]:
    if not collections:
        return []

    category_keywords = extract_keywords(category)
    relevant = []
    generic_collections = []

    for collection in collections:
        collection_keywords = extract_keywords(collection, ["title", "handle"])

        if any(keyword in collection_keywords for keyword in category_keywords):
            relevant.append(collection)
        else:
            generic_collections.append(collection)

    if relevant:
        return relevant

    if generic_collections:
        sample_size = min(RELEVANT_COLLECTIONS_SAMPLE_SIZE, len(generic_collections))
        return random.sample(generic_collections, sample_size)

    return []


def find_relevant_tags(category: dict, tags: list[dict]) -> list[dict]:
    if not tags:
        return []

    category_keywords = extract_keywords(category)
    relevant = []
    generic_tags = []

    for tag in tags:
        tag_value = tag.get("value", "").lower()
        tag_words = set(tag_value.replace("-", " ").split())

        if any(keyword in tag_words for keyword in category_keywords) or any(keyword in category_keywords for keyword in tag_value.split()):
            relevant.append(tag)
        else:
            generic_tags.append(tag)

    if relevant:
        return relevant

    if generic_tags:
        sample_size = min(RELEVANT_TAGS_SAMPLE_SIZE, len(generic_tags))
        return random.sample(generic_tags, sample_size)

    return []


def find_relevant_category_for_collection(collection: dict, categories: list[dict]) -> dict:
    if not categories:
        return {}

    collection_keywords = extract_keywords(collection, ["title", "handle", "description"])

    best_match = None
    best_score = 0

    for category in categories:
        category_keywords = extract_keywords(category, ["name", "description", "handle"])
        overlap = len(collection_keywords & category_keywords)
        if overlap > best_score:
            best_score = overlap
            best_match = category

    if not best_match:
        best_match = random.choice(categories)

    return best_match


def build_collection_context_data(collection: dict, category: dict, product_types: list[dict], tags: list[dict]) -> dict:
    relevant_types = find_relevant_types(category, product_types)
    relevant_tags = find_relevant_tags(category, tags)

    return {
        "collection": collection,
        "category": category,
        "types": relevant_types,
        "tags": relevant_tags,
    }


def build_category_context_data(category: dict, product_types: list[dict], collections: list[dict], tags: list[dict]) -> dict:
    relevant_types = find_relevant_types(category, product_types)
    relevant_collections = find_relevant_collections(category, collections)
    relevant_tags = find_relevant_tags(category, tags)

    return {
        "category": category,
        "types": relevant_types,
        "collections": relevant_collections,
        "tags": relevant_tags,
    }


def create_category_only_plan(categories: list[dict], product_types: list[dict], collections: list[dict], tags: list[dict], total_products: int) -> list[dict]:
    num_categories = len(categories)
    plan = []

    for category in categories:
        products_for_category = total_products // num_categories
        num_batches = (products_for_category + MAX_PRODUCTS_PER_BATCH - 1) // MAX_PRODUCTS_PER_BATCH

        for batch_num in range(num_batches):
            batch_size = min(MAX_PRODUCTS_PER_BATCH, products_for_category - (batch_num * MAX_PRODUCTS_PER_BATCH))
            if batch_size > 0:
                context_data = build_category_context_data(category, product_types, collections, tags)
                context_data["batch_size"] = batch_size
                context_data["batch_number"] = batch_num + 1
                context_data["total_batches"] = num_batches
                plan.append(context_data)

    return plan


def create_collection_based_plan(categories: list[dict], collections: list[dict], product_types: list[dict], tags: list[dict], total_products: int) -> list[dict]:
    num_collections = len(collections)
    plan = []

    for collection in collections:
        category = find_relevant_category_for_collection(collection, categories)
        products_for_collection = total_products // num_collections
        num_batches = (products_for_collection + MAX_PRODUCTS_PER_BATCH - 1) // MAX_PRODUCTS_PER_BATCH

        for batch_num in range(num_batches):
            batch_size = min(MAX_PRODUCTS_PER_BATCH, products_for_collection - (batch_num * MAX_PRODUCTS_PER_BATCH))
            if batch_size > 0:
                context_data = build_collection_context_data(collection, category, product_types, tags)
                context_data["batch_size"] = batch_size
                context_data["batch_number"] = batch_num + 1
                context_data["total_batches"] = num_batches
                plan.append(context_data)

    return plan


def create_distribution_plan(categories: list[dict], collections: list[dict], product_types: list[dict], tags: list[dict], total_products: int) -> list[dict]:
    if not categories:
        logger.warning("No categories available. Using default category.")
        categories = [{"name": DEFAULT_CATEGORY_NAME, "handle": "general", "description": "General products"}]

    if collections:
        logger.info(f"📋 Creating collection-based distribution plan for {len(collections)} collections")
        return create_collection_based_plan(categories, collections, product_types, tags, total_products)
    else:
        logger.info(f"📋 Creating category-only distribution plan for {len(categories)} categories")
        return create_category_only_plan(categories, product_types, collections, tags, total_products)


def determine_material(product_type: str) -> str:
    product_type_lower = product_type.lower()
    for ptype, material in TYPE_MATERIAL_MAP.items():
        if ptype in product_type_lower:
            return material

    for keyword, material in MATERIAL_KEYWORDS.items():
        if keyword in product_type_lower:
            return material

    return "General Materials"


def determine_hs_code(material: str) -> str:
    return HS_CODE_MAP.get(material, "6307.90.98")


def get_product_dimensions(product_type: str) -> dict:
    product_type_lower = product_type.lower()
    for key, dimensions in PRODUCT_TYPE_DIMENSIONS.items():
        if key in product_type_lower:
            return dimensions

    return PRODUCT_TYPE_DIMENSIONS["default"]


def select_sales_channels() -> list[str]:
    if random.random() < SALES_CHANNEL_PROBABILITY:
        num_channels = random.randint(1, len(SALES_CHANNELS))
        return random.sample(SALES_CHANNELS, num_channels)
    return []


def add_variant_attributes(product: dict) -> dict:
    product_type = product.get("type", "")
    material = determine_material(product_type)
    hs_code = determine_hs_code(material)
    dimensions = get_product_dimensions(product_type)

    for variant in product.get("variants", []):
        for attr in REQUIRED_VARIANT_ATTRIBUTES:
            if attr not in variant or not variant[attr]:
                if attr == "sku":
                    variant[attr] = f"SKU-{random.randint(10000, 99999)}"
                elif attr == "price":
                    variant[attr] = round(random.uniform(5, 100), 2)
                elif attr == "inventory_quantity":
                    variant[attr] = random.randint(10, 500)
                elif attr == "weight":
                    variant[attr] = round(random.uniform(0.1, 5.0), 2)
                elif attr == "material":
                    variant[attr] = material
                elif attr == "hs_code":
                    variant[attr] = hs_code
                elif attr == "origin_country":
                    variant[attr] = DEFAULT_ORIGIN_COUNTRY

        if "length" not in variant or not variant["length"]:
            variant["length"] = dimensions["length"]
        if "width" not in variant or not variant["width"]:
            variant["width"] = dimensions["width"]
        if "height" not in variant or not variant["height"]:
            variant["height"] = dimensions["height"]

        options = variant.get("options", {})
        size = options.get("Size", "Medium")
        if size in SIZE_MULTIPLIERS:
            multiplier = SIZE_MULTIPLIERS[size]
            variant["length"] = round(variant["length"] * multiplier, 2)
            variant["width"] = round(variant["width"] * multiplier, 2)
            variant["height"] = round(variant["height"] * multiplier, 2)
            variant["weight"] = round(variant["weight"] * multiplier, 2)

    if "sales_channels" not in product or not product["sales_channels"]:
        product["sales_channels"] = select_sales_channels()

    if "shipping_profile" not in product or not product["shipping_profile"]:
        product["shipping_profile"] = DEFAULT_SHIPPING_PROFILE

    return product


def validate_and_deduplicate(products: list[dict], used_titles: set[str], used_handles: set[str], used_skus: set[str]) -> dict:
    validated_products = []
    skipped_count = 0

    for product in products:
        title = product.get("title", "")
        handle = product.get("handle", "")

        if not title or not handle:
            skipped_count += 1
            continue

        if title.lower() in {t.lower() for t in used_titles}:
            skipped_count += 1
            continue

        if handle.lower() in {h.lower() for h in used_handles}:
            skipped_count += 1
            continue

        variants = product.get("variants", [])
        product_skus = [v.get("sku", "") for v in variants if v.get("sku")]

        if any(sku in used_skus for sku in product_skus):
            skipped_count += 1
            continue

        validated_products.append(product)
        used_titles.add(title)
        used_handles.add(handle)
        used_skus.update(product_skus)

    if skipped_count > 0:
        logger.info(f"⚠️ Skipped {skipped_count} duplicate/invalid products")

    return {
        "validated_products": validated_products,
        "updated_used_titles": used_titles,
        "updated_used_handles": used_handles,
        "updated_used_skus": used_skus,
        "skipped_count": skipped_count,
    }


def track_coverage(
    validated_products: list[dict],
    plan_item: dict,
    category_coverage: dict,
    collection_coverage: dict,
    type_coverage: dict,
    tag_coverage: dict,
) -> dict:
    for product in validated_products:
        category_name = product.get("category", "Unknown")
        collection_name = product.get("collection", "Unknown")
        product_type = product.get("type", "Unknown")
        tags = product.get("tags", [])

        category_coverage[category_name] = category_coverage.get(category_name, 0) + 1
        collection_coverage[collection_name] = collection_coverage.get(collection_name, 0) + 1
        type_coverage[product_type] = type_coverage.get(product_type, 0) + 1

        for tag in tags:
            tag_coverage[tag] = tag_coverage.get(tag, 0) + 1

    return {
        "category_coverage": category_coverage,
        "collection_coverage": collection_coverage,
        "type_coverage": type_coverage,
        "tag_coverage": tag_coverage,
    }


def build_existing_products_context(recent_products: list[dict]) -> str:
    if not recent_products:
        return ""

    context_products = recent_products[-RECENT_PRODUCTS_CONTEXT_LIMIT:]
    products_summary = []

    for product in context_products:
        title = product.get("title", "Unknown")
        product_type = product.get("type", "Unknown")
        tags = product.get("tags", [])
        tags_str = ", ".join(tags[:5]) if tags else "None"
        products_summary.append(f"- {title} (Type: {product_type}, Tags: {tags_str})")

    products_list = "\n".join(products_summary)
    return EXISTING_PRODUCTS_CONTEXT_TEMPLATE.format(products_list=products_list)


def build_context_prompt(plan_item: dict, existing_products_context: str = "") -> str:
    collection = plan_item.get("collection", {})
    category = plan_item.get("category", {})
    types = plan_item.get("types", [])
    tags = plan_item.get("tags", [])

    collection_title = collection.get("title", "General Collection")
    collection_description = collection.get("description", "")
    category_name = category.get("name", "General")
    category_description = category.get("description", "")

    types_list = [t.get("value", "") for t in types[:RELEVANT_TYPES_LIMIT]]
    tags_list = [t.get("value", "") for t in tags[:RELEVANT_TAGS_LIMIT]]

    context_parts = [f"Collection: {collection_title}"]
    if collection_description:
        context_parts.append(f"Collection Description: {collection_description}")

    context_parts.append(f"Category: {category_name}")
    if category_description:
        context_parts.append(f"Category Description: {category_description}")

    if types_list:
        context_parts.append(f"Relevant Product Types: {', '.join(types_list)}")

    if tags_list:
        context_parts.append(f"Relevant Tags: {', '.join(tags_list)}")

    if existing_products_context:
        context_parts.append(existing_products_context)

    return "\n".join(context_parts)


def parse_products_from_response(response_text: str) -> list[dict]:
    try:
        json_match = re.search(r"```json\s*(.*?)\s*```", response_text, re.DOTALL)
        if json_match:
            json_str = json_match.group(1)
            data = json.loads(json_str)
            if isinstance(data, dict) and "products" in data:
                return data["products"]
            elif isinstance(data, list):
                return data
            else:
                logger.warning("Unexpected JSON structure")
                return []
        else:
            logger.warning("No JSON block found in response")
            return []
    except json.JSONDecodeError as e:
        logger.error(f"JSON parsing error: {e}")
        logger.error(f"Response text: {response_text[:500]}")
        return []
    except Exception as e:
        logger.error(f"Error parsing products: {e}")
        return []


# Apply tenacity retry decorator to the main API call function
@retry(
    stop=stop_after_attempt(MAX_RETRIES),
    wait=wait_exponential(multiplier=1, min=1, max=10),
    retry=retry_if_exception_type((ConnectionError, TimeoutError, Exception)),
    before_sleep=before_sleep_log(logger, "WARNING"),
    after=after_log(logger, "INFO"),
    reraise=True,
)
async def generate_complete_products(batch_size: int, plan_item: dict, existing_products: list[dict]) -> list[dict]:
    """
    Generate products with automatic retry using tenacity decorator.

    Args:
        batch_size: Number of products to generate
        plan_item: Context data for generation
        existing_products: Recently generated products for context

    Returns:
        List of generated and processed products
    """
    collection = plan_item.get("collection", {})
    category = plan_item.get("category", {})
    collection_title = collection.get("title", "General Collection")
    category_name = category.get("name", "General")

    logger.info(f"🎯 Generating {batch_size} products for {collection_title} ({category_name})")

    existing_context = build_existing_products_context(existing_products)
    context_prompt = build_context_prompt(plan_item, existing_context)
    user_prompt = USER_PROMPT.format(context=context_prompt, count=batch_size)

    logger.info("📤 Sending request to Anthropic API...")
    response = await make_anthropic_request(
        system_prompt=SYSTEM_PROMPT,
        user_prompt=user_prompt,
        max_tokens=MAX_API_TOKENS,
    )

    response_text = response.get("content", [{}])[0].get("text", "")

    if not response_text:
        logger.error("Empty response from API")
        return []

    logger.info("📥 Parsing API response...")
    products = parse_products_from_response(response_text)

    if not products:
        logger.warning("No products parsed from response")
        return []

    logger.info(f"✨ Processing {len(products)} products...")
    processed_products = []

    for idx, product in enumerate(products):
        try:
            if "category" not in product or not product["category"]:
                product["category"] = category_name

            if "collection" not in product or not product["collection"] or isinstance(product.get("collection"), list):
                product["collection"] = collection_title

            if "type" not in product or not product["type"]:
                relevant_types = plan_item.get("types", [])
                if relevant_types:
                    product["type"] = random.choice(relevant_types).get("value", "")
                else:
                    product["type"] = DEFAULT_PRODUCT_TYPE

            if "tags" not in product or not isinstance(product["tags"], list):
                product["tags"] = []

            product = add_variant_attributes(product)
            processed_products.append(product)

        except Exception as e:
            logger.warning(f"⚠️ Error processing product {idx + 1}: {e}")
            continue

    logger.info(f"✅ Generated {len(processed_products)}/{batch_size} products for {collection_title}")
    return processed_products


def log_coverage_summary(
    category_coverage: dict,
    collection_coverage: dict,
    type_coverage: dict,
    tag_coverage: dict,
    total_categories: int,
    total_collections: int,
    total_types: int,
    total_tags: int,
) -> None:
    logger.info("\n" + "=" * 60)
    logger.info("📊 COVERAGE SUMMARY")
    logger.info("=" * 60)

    logger.info(f"\n📁 CATEGORY COVERAGE ({len(category_coverage)}/{total_categories} categories):")
    for cat_name, count in sorted(category_coverage.items(), key=lambda x: x[1], reverse=True):
        logger.info(f"  • {cat_name}: {count} products")

    if collection_coverage:
        logger.info(f"\n📚 COLLECTION COVERAGE ({len(collection_coverage)}/{total_collections} collections):")
        for coll_name, count in sorted(collection_coverage.items(), key=lambda x: x[1], reverse=True):
            logger.info(f"  • {coll_name}: {count} products")

    if type_coverage:
        logger.info(f"\n🏷️  TYPE COVERAGE ({len(type_coverage)}/{total_types} types):")
        for type_name, count in sorted(type_coverage.items(), key=lambda x: x[1], reverse=True)[:20]:
            logger.info(f"  • {type_name}: {count} products")

    if tag_coverage:
        logger.info(f"\n🏷️  TAG USAGE ({len(tag_coverage)}/{total_tags} tags used):")
        top_tags = sorted(tag_coverage.items(), key=lambda x: x[1], reverse=True)[:20]
        for tag_name, count in top_tags:
            logger.info(f"  • {tag_name}: {count} products")

    logger.info("\n" + "=" * 60)


# Apply retry decorator to the main generation function for additional resilience
@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=2, min=4, max=30),
    retry=retry_if_exception_type(Exception),
    before_sleep=before_sleep_log(logger, "WARNING"),
    reraise=True,
)
async def generate_products(n_products: int | None = None) -> dict:
    target_count = n_products or DEFAULT_PRODUCTS_COUNT
    logger.info(f"🚀 Starting product generation - Target: {target_count}")

    settings.DATA_PATH.mkdir(parents=True, exist_ok=True)
    validate_anthropic_config(settings.ANTHROPIC_API_KEY)

    catalog_data = load_catalog_data()
    categories = catalog_data["categories"]
    collections = catalog_data["collections"]
    product_types = catalog_data["product_types"]
    tags = catalog_data["tags"]

    logger.info(f"📊 Catalog: {len(categories)} categories, {len(product_types)} types, {len(collections)} collections, {len(tags)} tags")

    generated_products: list[dict] = []
    used_handles: set[str] = set()
    used_skus: set[str] = set()
    used_titles: set[str] = set()
    category_coverage: dict[str, int] = {}
    collection_coverage: dict[str, int] = {}
    type_coverage: dict[str, int] = {}
    tag_coverage: dict[str, int] = {}

    try:
        distribution_plan = create_distribution_plan(categories, collections, product_types, tags, target_count)

        total_generated = 0

        for idx, plan_item in enumerate(distribution_plan, 1):
            collection = plan_item.get("collection", {})
            category = plan_item.get("category", {})
            collection_title = collection.get("title", "General Collection")
            category_name = category.get("name", "General")
            batch_size = plan_item.get("batch_size", 0)
            batch_num = plan_item.get("batch_number", 1)
            total_batches = plan_item.get("total_batches", 1)

            if batch_size == 0:
                continue

            logger.info(f"\n{'=' * 60}")
            logger.info(f"📦 Batch {idx}/{len(distribution_plan)}: {collection_title} ({batch_num}/{total_batches})")
            logger.info(f"   Category: {category_name}")
            logger.info(f"   Target: {batch_size} products")
            logger.info(f"   Types: {len(plan_item.get('types', []))}")
            logger.info(f"   Tags: {len(plan_item.get('tags', []))}")
            logger.info(f"{'=' * 60}")

            try:
                # The retry logic is now handled by the @retry decorator
                products = await generate_complete_products(batch_size, plan_item, generated_products)

                if products:
                    validation_result = validate_and_deduplicate(products, used_titles, used_handles, used_skus)
                    validated = validation_result["validated_products"]
                    used_titles = validation_result["updated_used_titles"]
                    used_handles = validation_result["updated_used_handles"]
                    used_skus = validation_result["updated_used_skus"]

                    if validated:
                        coverage_result = track_coverage(validated, plan_item, category_coverage, collection_coverage, type_coverage, tag_coverage)
                        category_coverage = coverage_result["category_coverage"]
                        collection_coverage = coverage_result["collection_coverage"]
                        type_coverage = coverage_result["type_coverage"]
                        tag_coverage = coverage_result["tag_coverage"]

                        generated_products.extend(validated)
                        total_generated += len(validated)
                        logger.info(f"✅ Batch {idx} completed: {len(validated)} products added (Total: {total_generated})")
                    else:
                        logger.warning("⚠️ All products were duplicates")
                else:
                    logger.warning("⚠️ No products generated")

            except Exception as e:
                logger.error(f"⚠️ Batch {idx} failed after all retries: {type(e).__name__}: {e}")
                continue

        if generated_products:
            logger.info("🔀 Shuffling products before saving...")
            random.shuffle(generated_products)

            save_to_json(generated_products, PRODUCTS_FILEPATH)
            logger.info(f"💾 Saved {len(generated_products)} shuffled products to {PRODUCTS_FILEPATH}")

        log_coverage_summary(
            category_coverage,
            collection_coverage,
            type_coverage,
            tag_coverage,
            len(categories),
            len(collections),
            len(product_types),
            len(tags),
        )

        success_rate = (total_generated / target_count * 100) if target_count > 0 else 0
        logger.info("\n✅ GENERATION COMPLETE")
        logger.info(f"   Total Generated: {total_generated}/{target_count}")
        logger.info(f"   Success Rate: {success_rate:.1f}%")
        logger.info(f"   Unique Handles: {len(used_handles)}")
        logger.info(f"   Unique SKUs: {len(used_skus)}")

        return {
            "total_generated": total_generated,
            "target_count": target_count,
            "success_rate": success_rate,
            "products": generated_products,
            "categories_covered": len(category_coverage),
            "types_covered": len(type_coverage),
            "collections_covered": len(collection_coverage),
            "tags_used": len(tag_coverage),
            "unique_handles": len(used_handles),
            "unique_skus": len(used_skus),
            "coverage_details": {
                "categories": category_coverage,
                "types": type_coverage,
                "collections": collection_coverage,
                "tags": tag_coverage,
            },
        }

    except Exception as e:
        logger.error(f"❌ Fatal error during generation: {e}")
        logger.error(f"Traceback:\n{traceback.format_exc()}")

        if generated_products:
            logger.info("💾 Saving partial results...")
            random.shuffle(generated_products)
            save_to_json(generated_products, PRODUCTS_FILEPATH)
            logger.info(f"💾 Saved {len(generated_products)} partial products")

        raise


async def products(n_products: int | None = None):
    try:
        result = await generate_products(n_products)
        logger.info(f"✅ Generated {result['total_generated']} products successfully")
        return result
    except Exception as e:
        logger.error(f"❌ Fatal error: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(products())
