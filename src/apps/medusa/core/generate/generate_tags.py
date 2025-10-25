import asyncio

from tenacity import retry, stop_after_attempt, wait_exponential

from apps.medusa.config.constants import (
    DEFAULT_TAGS_COUNT,
    TAGS_BATCH_SIZE,
    TAGS_FILEPATH,
)
from apps.medusa.config.settings import settings
from apps.medusa.core.generate.prompts.generate_tags_prompts import (
    EXISTING_CONTEXT_TEMPLATE,
    USER_PROMPT,
    VARIETY_INSTRUCTION_TEMPLATE,
)
from apps.medusa.utils.data_utils import format_items_context, load_existing_data
from common.anthropic_client import make_anthropic_request, parse_anthropic_response, validate_anthropic_config
from common.logger import logger
from common.save_to_json import save_to_json


def load_existing_tags():
    """Load existing tags to prevent duplicates."""
    existing = load_existing_data(filepath=TAGS_FILEPATH, unique_fields=["value"], track_all=True)

    return {
        "used_values": existing["used_identifiers"].get("value", set()),
        "generated_tags": existing["items"],
        "all_generated_tags": existing["items"].copy() if existing["items"] else [],
    }


def create_tag_prompt(all_generated_tags: list[dict], batch_size: int, attempt: int = 1) -> str:
    """Create prompt for tag generation."""
    existing_context = ""
    if all_generated_tags:
        tags_context = format_items_context(items=all_generated_tags, primary_field="value", secondary_field="description", max_items=50)
        existing_context = EXISTING_CONTEXT_TEMPLATE.format(tags_context=tags_context, total_count=len(all_generated_tags))

    variety_instruction = ""
    if attempt > 1:
        variety_instruction = VARIETY_INSTRUCTION_TEMPLATE.format(attempt=attempt)

    return USER_PROMPT.format(batch_size=batch_size, existing_context=existing_context, variety_instruction=variety_instruction)


@retry(wait=wait_exponential(multiplier=1, min=2, max=10), stop=stop_after_attempt(2), reraise=True)
async def generate_realistic_tags(all_generated_tags: list[dict], used_values: set[str], batch_size: int | None = None, attempt: int = 1) -> dict:
    """Generate realistic tag data using Anthropic API."""
    batch_size = batch_size or TAGS_BATCH_SIZE

    prompt = create_tag_prompt(all_generated_tags, batch_size, attempt)
    response_data = await make_anthropic_request(prompt=prompt, api_key=settings.ANTHROPIC_API_KEY, max_tokens=4000)

    if not response_data:
        raise Exception("Failed to get response from Anthropic API")

    tags = parse_anthropic_response(response_data)

    if not tags:
        raise Exception("Invalid tag data format from Anthropic")

    unique_tags: list[dict] = []
    duplicates_found: list[str] = []
    new_used_values = used_values.copy()
    new_all_tags = all_generated_tags.copy()

    for tag in tags:
        if not tag.get("value") or not tag.get("description"):
            continue

        value = tag["value"].lower().strip()

        if value in new_used_values:
            duplicates_found.append(value)
            continue

        new_used_values.add(value)
        tag["value"] = value
        tag["description"] = tag["description"].strip()

        unique_tags.append(tag)
        new_all_tags.append(tag)

    if duplicates_found:
        logger.warning(f"Filtered {len(duplicates_found)} duplicates (attempt {attempt})")

    if not unique_tags:
        raise Exception("No unique tags generated")

    logger.info(f"Generated {len(unique_tags)} unique tags (attempt {attempt})")

    return {
        "unique_tags": unique_tags,
        "updated_used_values": new_used_values,
        "updated_all_tags": new_all_tags,
    }


async def generate_tags(count: int | None = None) -> dict:
    """Generate tags and save to file."""
    target_count = count or DEFAULT_TAGS_COUNT
    logger.info(f"Starting tags generation - Target: {target_count}, Batch size: {TAGS_BATCH_SIZE}")

    settings.DATA_PATH.mkdir(parents=True, exist_ok=True)
    validate_anthropic_config(settings.ANTHROPIC_API_KEY)

    existing_data = load_existing_tags()
    generated_tags = existing_data["generated_tags"]
    all_generated_tags = existing_data["all_generated_tags"]
    used_values = existing_data["used_values"]

    try:
        total_generated = 0
        total_processed = 0
        attempt = 1
        max_attempts = 7

        while total_processed < target_count:
            remaining_count = target_count - total_processed
            if attempt == 1:
                current_batch_size = min(TAGS_BATCH_SIZE, remaining_count)
            elif attempt == 2:
                current_batch_size = min(TAGS_BATCH_SIZE * 2, remaining_count * 2)
            else:
                current_batch_size = min(TAGS_BATCH_SIZE * 4, 50)

            logger.info(f"Requesting {current_batch_size} tags (attempt {attempt}, need {remaining_count} more)")

            try:
                generation_result = await generate_realistic_tags(all_generated_tags=all_generated_tags, used_values=used_values, batch_size=current_batch_size, attempt=attempt)

                unique_tags = generation_result["unique_tags"]
                generated_tags.extend(unique_tags)
                all_generated_tags = generation_result["updated_all_tags"]
                used_values = generation_result["updated_used_values"]

                total_generated += len(unique_tags)
                total_processed += len(unique_tags)

                if len(unique_tags) >= current_batch_size * 0.3:
                    attempt = 1
                    logger.info("Good batch yield, resetting attempt counter")
                else:
                    logger.info("Low yield batch, maintaining attempt counter")

            except Exception as e:
                error_msg = str(e)

                if "No unique tags generated" in error_msg:
                    attempt += 1

                    logger.warning(f"Batch produced no unique tags. Retry attempt {attempt}/{max_attempts} with more variety")

                    if attempt > max_attempts:
                        logger.error(f"Reached max retry attempts ({max_attempts}). Unable to generate more unique tags.")
                        break

                    continue
                else:
                    logger.error(f"Batch failed with error: {e}")
                    break

        if generated_tags:
            save_to_json(generated_tags, TAGS_FILEPATH)
            logger.info(f"Saved {len(generated_tags)} tags to {TAGS_FILEPATH}")

        if total_generated > 0:
            success_rate = (total_processed / total_generated) * 100
            logger.info(f"Generated {total_processed}/{total_generated} tags - Success rate: {success_rate:.1f}%")
        else:
            logger.warning("No tags were generated")

        return {
            "total_processed": total_processed,
            "total_generated": total_generated,
            "tags": generated_tags,
        }

    except Exception as error:
        logger.error(f"Fatal error during generation: {error}")
        if generated_tags:
            save_to_json(generated_tags, TAGS_FILEPATH)
        raise


async def tags(count: int | None = None):
    result = await generate_tags(count)
    logger.info(f"Generated {result['total_processed']} tags successfully")
    return result


if __name__ == "__main__":
    import sys

    count = int(sys.argv[1]) if len(sys.argv) > 1 else None
    asyncio.run(tags(count))
