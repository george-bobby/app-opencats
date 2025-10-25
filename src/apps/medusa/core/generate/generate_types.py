import asyncio

from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from apps.medusa.config.constants import (
    DEFAULT_TYPES_COUNT,
    TYPES_BATCH_SIZE,
    TYPES_FILEPATH,
)
from apps.medusa.config.settings import settings
from apps.medusa.core.generate.prompts.generate_types_prompts import (
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


def load_existing_types():
    """Load existing types to prevent duplicates."""
    existing = load_existing_data(filepath=TYPES_FILEPATH, unique_fields=["value"], track_all=True)

    return {
        "used_values": existing["used_identifiers"].get("value", set()),
        "generated_types": existing["items"],
        "all_generated_types": existing["items"].copy() if existing["items"] else [],
    }


def create_types_prompt(all_generated_types: list[dict], batch_size: int, attempt: int = 1) -> str:
    """Create prompt for type generation."""
    existing_context = ""
    if all_generated_types:
        types_context = format_items_context(items=all_generated_types, primary_field="value", secondary_field=None, max_items=50)
        existing_context = EXISTING_CONTEXT_TEMPLATE.format(types_context=types_context, total_count=len(all_generated_types))

    variety_instruction = ""
    if attempt > 1:
        variety_instruction = VARIETY_INSTRUCTION_TEMPLATE.format(attempt=attempt)

    user_prompt = USER_PROMPT.format(batch_size=batch_size, existing_context=existing_context, variety_instruction=variety_instruction)

    return f"{SYSTEM_PROMPT}\n\n{user_prompt}"


@retry(wait=wait_exponential(multiplier=2, min=4, max=30), stop=stop_after_attempt(5), retry=retry_if_exception_type(APIOverloadError), reraise=True)
async def generate_realistic_types(all_generated_types: list[dict], used_values: set[str], batch_size: int | None = None, attempt: int = 1) -> dict:
    """Generate realistic type data using Anthropic API."""
    batch_size = batch_size or TYPES_BATCH_SIZE

    prompt = create_types_prompt(all_generated_types, batch_size, attempt)
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

    types = parse_anthropic_response(response_data)

    if not types:
        raise Exception("Invalid type data format from Anthropic")

    unique_types: list[dict] = []
    duplicates_found: list[str] = []
    new_used_values = used_values.copy()
    new_all_types = all_generated_types.copy()

    for ptype in types:
        if not ptype.get("value"):
            continue

        value = ptype["value"].strip()
        value_lower = value.lower()

        if value_lower in new_used_values:
            duplicates_found.append(value)
            continue

        new_used_values.add(value_lower)
        ptype["value"] = value

        unique_types.append(ptype)
        new_all_types.append(ptype)

    if duplicates_found:
        logger.warning(f"Filtered {len(duplicates_found)} duplicates: {', '.join(duplicates_found[:5])}")

    if not unique_types:
        raise Exception("No unique types generated")

    logger.info(f"Generated {len(unique_types)} unique types")

    return {
        "unique_types": unique_types,
        "updated_used_values": new_used_values,
        "updated_all_types": new_all_types,
    }


async def generate_types(count: int | None = None) -> dict:
    """Generate types and save to file."""
    target_count = count or DEFAULT_TYPES_COUNT
    logger.info(f"Starting types generation - Target: {target_count}, Batch size: {TYPES_BATCH_SIZE}")

    settings.DATA_PATH.mkdir(parents=True, exist_ok=True)
    validate_anthropic_config(settings.ANTHROPIC_API_KEY)

    existing_data = load_existing_types()
    generated_types = existing_data["generated_types"]
    all_generated_types = existing_data["all_generated_types"]
    used_values = existing_data["used_values"]

    try:
        total_generated = 0
        total_processed = 0
        batch_count = 0

        while total_processed < target_count:
            batch_count += 1
            remaining_count = target_count - total_processed
            current_batch_size = min(TYPES_BATCH_SIZE, remaining_count)

            logger.info(f"Processing batch {batch_count} - Requesting {current_batch_size} types")

            try:
                generation_result = await generate_realistic_types(all_generated_types=all_generated_types, used_values=used_values, batch_size=current_batch_size, attempt=batch_count)

                unique_types = generation_result["unique_types"]
                generated_types.extend(unique_types)
                all_generated_types = generation_result["updated_all_types"]
                used_values = generation_result["updated_used_values"]

                total_generated += len(unique_types)
                total_processed += len(unique_types)

                logger.info(f"Batch {batch_count} complete - Generated {len(unique_types)} types. Progress: {total_processed}/{target_count}")

            except APIOverloadError as e:
                logger.error(f"Batch {batch_count} failed after retries (API overloaded): {e}")
                break
            except Exception as e:
                logger.error(f"Batch {batch_count} failed: {e}")
                break

        if generated_types:
            save_to_json(generated_types, TYPES_FILEPATH)
            logger.info(f"Saved {len(generated_types)} types to {TYPES_FILEPATH}")

        success_rate = (total_processed / total_generated * 100) if total_generated > 0 else 0
        logger.info(f"Generation complete - Processed: {total_processed}/{total_generated} types - Success rate: {success_rate:.1f}%")

        return {
            "total_processed": total_processed,
            "total_generated": total_generated,
            "types": generated_types,
        }

    except Exception as error:
        logger.error(f"Fatal error during generation: {error}")
        if generated_types:
            save_to_json(generated_types, TYPES_FILEPATH)
            logger.info(f"Saved {len(generated_types)} types before exit")
        raise


async def types(count: int | None = None):
    """Main entry point for types generation."""
    result = await generate_types(count)
    logger.info(f"Generated {result['total_processed']} types successfully")
    return result


if __name__ == "__main__":
    import sys

    count = int(sys.argv[1]) if len(sys.argv) > 1 else None
    asyncio.run(types(count))
