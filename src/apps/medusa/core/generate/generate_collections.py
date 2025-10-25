from tenacity import retry, stop_after_attempt, wait_exponential

from apps.medusa.config.constants import (
    COLLECTIONS_BATCH_SIZE,
    COLLECTIONS_FILEPATH,
    DEFAULT_COLLECTIONS_COUNT,
)
from apps.medusa.config.settings import settings
from apps.medusa.core.generate.prompts.generate_collections_prompts import (
    EXISTING_CONTEXT_TEMPLATE,
    USER_PROMPT,
    VARIETY_INSTRUCTION_TEMPLATE,
)
from apps.medusa.utils.data_utils import format_items_context, load_existing_data
from common.anthropic_client import make_anthropic_request, parse_anthropic_response, validate_anthropic_config
from common.logger import logger
from common.save_to_json import save_to_json


def load_existing_collections():
    existing = load_existing_data(filepath=COLLECTIONS_FILEPATH, unique_fields=["handle"], track_all=True)

    return {
        "used_handles": existing["used_identifiers"].get("handle", set()),
        "generated_collections": existing["items"],
        "all_generated_collections": existing["items"].copy() if existing["items"] else [],
    }


def create_collections_prompt(all_generated_collections: list[dict], batch_size: int, attempt: int = 1) -> str:
    """Create prompt with context of previously generated collections."""
    existing_context = ""
    if all_generated_collections:
        collections_context = format_items_context(items=all_generated_collections, primary_field="title", secondary_field="handle", max_items=40)
        existing_context = EXISTING_CONTEXT_TEMPLATE.format(collections_context=collections_context, total_count=len(all_generated_collections))

    variety_instruction = ""
    if attempt > 1:
        variety_instruction = VARIETY_INSTRUCTION_TEMPLATE.format(attempt=attempt)

    return USER_PROMPT.format(batch_size=batch_size, existing_context=existing_context, variety_instruction=variety_instruction)


@retry(wait=wait_exponential(multiplier=1, min=2, max=10), stop=stop_after_attempt(3))
async def generate_realistic_collections(all_generated_collections: list[dict], used_handles: set[str], batch_size: int | None = None, max_attempts: int = 3) -> dict:
    """Generate realistic collection data using Anthropic API."""
    batch_size = batch_size or COLLECTIONS_BATCH_SIZE

    for attempt in range(1, max_attempts + 1):
        try:
            prompt = create_collections_prompt(all_generated_collections, batch_size, attempt)
            response_data = await make_anthropic_request(prompt=prompt, api_key=settings.ANTHROPIC_API_KEY, max_tokens=4000)

            if not response_data:
                raise Exception("Failed to get response from Anthropic API")

            collections = parse_anthropic_response(response_data)

            if not collections:
                raise Exception("Invalid collection data format from Anthropic")

            unique_collections = []
            duplicates_found = []
            new_used_handles = used_handles.copy()
            new_all_collections = all_generated_collections.copy()

            for collection in collections:
                if not collection.get("title") or not collection.get("handle"):
                    continue

                handle = collection["handle"].lower().strip()
                if handle in new_used_handles:
                    duplicates_found.append(handle)
                    continue

                new_used_handles.add(handle)
                collection["handle"] = handle
                unique_collections.append(collection)
                new_all_collections.append(collection)

            if duplicates_found:
                logger.warning(f"Filtered {len(duplicates_found)} duplicates")

            if not unique_collections:
                raise Exception("No unique collections generated")

            logger.info(f"Generated {len(unique_collections)} unique collections")

            return {
                "unique_collections": unique_collections,
                "updated_used_handles": new_used_handles,
                "updated_all_collections": new_all_collections,
            }

        except Exception as error:
            if attempt < max_attempts:
                logger.warning(f"Attempt {attempt} failed: {error}. Retrying...")
            else:
                logger.error(f"All attempts failed: {error}")
                raise

    raise Exception("Failed to generate collections after all attempts")


def process_collections(collections: list[dict], generated_collections: list[dict]) -> dict:
    """Process generated collection data."""
    processed_collections = []
    new_generated_collections = generated_collections.copy()

    for collection in collections:
        processed_collection = {"title": collection["title"], "handle": collection["handle"]}
        processed_collections.append(processed_collection)
        new_generated_collections.append(processed_collection)

    return {
        "processed": len(processed_collections),
        "collections": processed_collections,
        "updated_generated_collections": new_generated_collections,
    }


async def generate_collections(count: int | None = None) -> dict:
    """Generate collections and save to file."""
    target_count = count or DEFAULT_COLLECTIONS_COUNT
    logger.info(f"Starting collections generation - Target: {target_count}, Batch size: {COLLECTIONS_BATCH_SIZE}")

    settings.DATA_PATH.mkdir(parents=True, exist_ok=True)
    validate_anthropic_config(settings.ANTHROPIC_API_KEY)

    existing_data = load_existing_collections()
    generated_collections = existing_data["generated_collections"]
    all_generated_collections = existing_data["all_generated_collections"]
    used_handles = existing_data["used_handles"]

    try:
        total_generated = 0
        total_processed = 0
        consecutive_failures = 0
        max_consecutive_failures = 3

        while total_processed < target_count:
            remaining_count = target_count - total_processed
            current_batch_size = min(COLLECTIONS_BATCH_SIZE, remaining_count)
            batch_num = (total_processed // COLLECTIONS_BATCH_SIZE) + 1

            logger.info(f"Batch {batch_num}: Generating {current_batch_size} collections")

            try:
                generation_result = await generate_realistic_collections(all_generated_collections=all_generated_collections, used_handles=used_handles, batch_size=current_batch_size)

                process_result = process_collections(collections=generation_result["unique_collections"], generated_collections=generated_collections)

                generated_collections = process_result["updated_generated_collections"]
                all_generated_collections = generation_result["updated_all_collections"]
                used_handles = generation_result["updated_used_handles"]

                total_generated += len(generation_result["unique_collections"])
                total_processed += process_result["processed"]
                consecutive_failures = 0

            except Exception as e:
                consecutive_failures += 1
                logger.warning(f"Batch {batch_num} failed: {e}")

                if consecutive_failures >= max_consecutive_failures:
                    logger.error("Too many consecutive failures. Stopping generation.")
                    break

                if current_batch_size > 1:
                    current_batch_size = max(1, current_batch_size // 2)
                    logger.info(f"Retrying with smaller batch size: {current_batch_size}")
                    continue

        if generated_collections:
            save_to_json(generated_collections, COLLECTIONS_FILEPATH)
            logger.info(f"Saved {len(generated_collections)} collections to {COLLECTIONS_FILEPATH}")

        logger.info(f"Generated {total_processed}/{total_generated} collections - Success rate: {(total_processed / total_generated) * 100:.1f}%")

        return {
            "total_processed": total_processed,
            "total_generated": total_generated,
            "collections": generated_collections,
        }

    except Exception as error:
        logger.error(f"Fatal error during generation: {error}")
        if generated_collections:
            save_to_json(generated_collections, COLLECTIONS_FILEPATH)
        raise


async def collections(count: int | None = None):
    result = await generate_collections(count)
    logger.info(f"Generated {result['total_processed']} collections successfully")
    return result


if __name__ == "__main__":
    import asyncio
    import sys

    count = int(sys.argv[1]) if len(sys.argv) > 1 else None
    asyncio.run(collections(count))
