import asyncio

from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from apps.medusa.config.constants import (
    CATEGORIES_BATCH_SIZE,
    CATEGORIES_FILEPATH,
    DEFAULT_CATEGORIES_COUNT,
)
from apps.medusa.config.settings import settings
from apps.medusa.core.generate.prompts.generate_categories_prompts import (
    EXISTING_CONTEXT_TEMPLATE,
    SYSTEM_PROMPT,
    USER_PROMPT,
    VARIETY_INSTRUCTION_TEMPLATE,
)
from apps.medusa.utils.data_utils import format_items_context, load_existing_data
from common.anthropic_client import make_anthropic_request, parse_anthropic_response, validate_anthropic_config
from common.logger import logger
from common.save_to_json import save_to_json


class APIOverloadError(Exception):
    """Raised when API returns overload error."""

    pass


def load_existing_categories():
    existing = load_existing_data(filepath=CATEGORIES_FILEPATH, unique_fields=["handle", "name"], track_all=True)

    return {
        "used_handles": existing["used_identifiers"].get("handle", set()),
        "used_names": existing["used_identifiers"].get("name", set()),
        "generated_categories": existing["items"],
        "all_generated_categories": existing["items"].copy() if existing["items"] else [],
    }


def create_categories_prompt(all_generated_categories: list[dict], batch_size: int, attempt: int = 1) -> str:
    """Create prompt with context of previously generated categories."""
    existing_context = ""
    if all_generated_categories:
        categories_context = format_items_context(items=all_generated_categories, primary_field="name", secondary_field="handle", max_items=40)
        existing_context = EXISTING_CONTEXT_TEMPLATE.format(categories_context=categories_context, total_count=len(all_generated_categories))

    variety_instruction = ""
    if attempt > 1:
        variety_instruction = VARIETY_INSTRUCTION_TEMPLATE.format(attempt=attempt)

    user_prompt = USER_PROMPT.format(batch_size=batch_size, existing_context=existing_context, variety_instruction=variety_instruction)

    return f"{SYSTEM_PROMPT}\n\n{user_prompt}"


@retry(wait=wait_exponential(multiplier=2, min=4, max=30), stop=stop_after_attempt(5), retry=retry_if_exception_type(APIOverloadError), reraise=True)
async def generate_realistic_categories(all_generated_categories: list[dict], used_names: set[str], used_handles: set[str], batch_size: int | None = None, attempt: int = 1) -> dict:
    """Generate realistic category data using Anthropic API."""
    batch_size = batch_size or CATEGORIES_BATCH_SIZE

    prompt = create_categories_prompt(all_generated_categories, batch_size, attempt)
    response_data = await make_anthropic_request(prompt=prompt, api_key=settings.ANTHROPIC_API_KEY, max_tokens=4000)

    if not response_data:
        raise Exception("Failed to get response from Anthropic API")

    if "error" in response_data:
        error_type = response_data["error"].get("type", "")
        error_message = response_data["error"].get("message", "")

        if error_type == "api_error" and "overload" in error_message.lower():
            logger.warning("API overloaded, will retry with backoff...")
            raise APIOverloadError(error_message)

        raise Exception(f"API error: {error_type} - {error_message}")

    categories = parse_anthropic_response(response_data)

    if not categories:
        raise Exception("Invalid category data format from Anthropic")

    unique_categories = []
    duplicates_found = []
    new_used_names = used_names.copy()
    new_used_handles = used_handles.copy()
    new_all_categories = all_generated_categories.copy()

    for category in categories:
        if not category.get("name"):
            continue

        name = category["name"].strip()
        name_lower = name.lower()

        if name_lower in new_used_names:
            duplicates_found.append(name)
            continue

        handle = category.get("handle", "").strip()
        handle_lower = handle.lower()

        if handle and handle_lower in new_used_handles:
            duplicates_found.append(handle)
            continue

        new_used_names.add(name_lower)
        if handle:
            new_used_handles.add(handle_lower)

        category.setdefault("is_active", True)
        category.setdefault("is_internal", False)

        unique_categories.append(category)
        new_all_categories.append(category)

    if duplicates_found:
        logger.warning(f"Filtered {len(duplicates_found)} duplicates: {', '.join(duplicates_found[:5])}")

    if not unique_categories:
        raise Exception("No unique categories generated")

    logger.info(f"Generated {len(unique_categories)} unique categories")

    return {
        "unique_categories": unique_categories,
        "updated_used_names": new_used_names,
        "updated_used_handles": new_used_handles,
        "updated_all_categories": new_all_categories,
    }


def process_categories(categories: list[dict], generated_categories: list[dict]) -> dict:
    """Process generated category data and add required fields."""
    processed_categories = []
    new_generated_categories = generated_categories.copy()

    for category in categories:
        processed_category = {
            "name": category["name"],
            "is_active": category.get("is_active", True),
            "is_internal": category.get("is_internal", False),
        }

        if category.get("description"):
            processed_category["description"] = category["description"]

        if category.get("handle"):
            processed_category["handle"] = category["handle"]

        processed_categories.append(processed_category)
        new_generated_categories.append(processed_category)

    return {
        "processed": len(processed_categories),
        "categories": processed_categories,
        "updated_generated_categories": new_generated_categories,
    }


async def generate_categories(count: int | None = None) -> dict:
    """Generate categories and save to file."""
    target_count = count or DEFAULT_CATEGORIES_COUNT
    logger.info(f"Starting categories generation - Target: {target_count}, Batch size: {CATEGORIES_BATCH_SIZE}")

    settings.DATA_PATH.mkdir(parents=True, exist_ok=True)
    validate_anthropic_config(settings.ANTHROPIC_API_KEY)

    existing_data = load_existing_categories()
    generated_categories = existing_data["generated_categories"]
    all_generated_categories = existing_data["all_generated_categories"]
    used_names = existing_data["used_names"]
    used_handles = existing_data["used_handles"]

    try:
        total_generated = 0
        total_processed = 0
        batch_count = 0

        while total_processed < target_count:
            batch_count += 1
            remaining_count = target_count - total_processed
            current_batch_size = min(CATEGORIES_BATCH_SIZE, remaining_count)

            logger.info(f"Processing batch {batch_count} - Requesting {current_batch_size} categories")

            try:
                generation_result = await generate_realistic_categories(
                    all_generated_categories=all_generated_categories, used_names=used_names, used_handles=used_handles, batch_size=current_batch_size, attempt=batch_count
                )

                process_result = process_categories(categories=generation_result["unique_categories"], generated_categories=generated_categories)

                generated_categories = process_result["updated_generated_categories"]
                all_generated_categories = generation_result["updated_all_categories"]
                used_names = generation_result["updated_used_names"]
                used_handles = generation_result["updated_used_handles"]

                total_generated += len(generation_result["unique_categories"])
                total_processed += process_result["processed"]

                logger.info(f"Batch {batch_count} complete - Generated {process_result['processed']} categories. Progress: {total_processed}/{target_count}")

            except APIOverloadError as e:
                logger.error(f"Batch {batch_count} failed after retries (API overloaded): {e}")
                break
            except Exception as e:
                logger.error(f"Batch {batch_count} failed: {e}")
                break

        if generated_categories:
            save_to_json(generated_categories, CATEGORIES_FILEPATH)
            logger.info(f"Saved {len(generated_categories)} categories to {CATEGORIES_FILEPATH}")

        success_rate = (total_processed / total_generated * 100) if total_generated > 0 else 0
        logger.info(f"Generation complete - Processed: {total_processed}/{total_generated} categories - Success rate: {success_rate:.1f}%")

        return {
            "total_processed": total_processed,
            "total_generated": total_generated,
            "categories": generated_categories,
        }

    except Exception as error:
        logger.error(f"Fatal error during generation: {error}")
        if generated_categories:
            save_to_json(generated_categories, CATEGORIES_FILEPATH)
            logger.info(f"Saved {len(generated_categories)} categories before exit")
        raise


async def categories(count: int | None = None):
    result = await generate_categories(count)
    logger.info(f"Generated {result['total_processed']} categories successfully")
    return result


if __name__ == "__main__":
    import sys

    count = int(sys.argv[1]) if len(sys.argv) > 1 else None
    asyncio.run(categories(count))
