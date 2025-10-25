"""Generate saved lists data for OpenCATS using AI."""

import asyncio
import random
from typing import Any

from tenacity import retry, stop_after_attempt, wait_exponential

from apps.opencats.config.constants import (
    CANDIDATES_FILEPATH,
    COMPANIES_FILEPATH,
    CONTACTS_FILEPATH,
    DEFAULT_LISTS_COUNT,
    JOBORDERS_FILEPATH,
    LIST_NAMES,
    LISTS_BATCH_SIZE,
    LISTS_FILEPATH,
    OpenCATSDataItemType,
)
from apps.opencats.config.settings import settings
from apps.opencats.utils.data_utils import load_existing_data
from common.anthropic_client import make_anthropic_request, parse_anthropic_response, validate_anthropic_config
from common.logger import logger
from common.save_to_json import save_to_json


def load_existing_lists():
    """Load existing lists to prevent duplicates."""
    existing_data = load_existing_data(LISTS_FILEPATH)

    used_names = set()

    for list_item in existing_data:
        if list_item.get("description"):
            used_names.add(list_item["description"].lower())

    return {
        "used_names": used_names,
        "generated_lists": existing_data,
    }


def load_data_for_lists():
    """Load all data types that can be added to lists."""
    candidates = load_existing_data(CANDIDATES_FILEPATH)
    companies = load_existing_data(COMPANIES_FILEPATH)
    contacts = load_existing_data(CONTACTS_FILEPATH)
    joborders = load_existing_data(JOBORDERS_FILEPATH)

    return {
        "candidates": candidates,
        "companies": companies,
        "contacts": contacts,
        "joborders": joborders,
    }


def create_lists_prompt(used_names: set, data_counts: dict[str, int], batch_size: int) -> str:
    """Create prompt for list generation."""
    excluded_names_text = ""
    if used_names:
        recent_names = list(used_names)[-10:]
        excluded_names_text = f"\n\nDo not use these list names (already exist): {', '.join(recent_names)}"

    # Data item types information
    data_types_info = []
    for data_type in OpenCATSDataItemType:
        type_name = data_type.name.lower().replace("_", " ")
        count = data_counts.get(type_name + "s", 0)  # Add 's' for plural
        data_types_info.append(f"{data_type.value}: {data_type.name.replace('_', ' ').title()} ({count} available)")

    data_types_text = "\n".join(data_types_info)

    sample_names = random.sample(LIST_NAMES, min(8, len(LIST_NAMES)))

    prompt = f"""Generate {batch_size} realistic saved lists for {settings.DATA_THEME_SUBJECT}.

Data item types available:
{data_types_text}

Sample list names for inspiration: {", ".join(sample_names)}

Each list should have:
- description: List name/description (be creative but professional)
- dataItemType: Data item type ID (100=Candidate, 200=Company, 300=Contact, 400=Job Order)
- itemIds: Array of 3-8 item IDs to add to the list (use IDs 1 to available count for each type)

Create diverse lists covering different business needs:
- Candidate lists (hot prospects, skill-based groups, etc.)
- Company lists (priority clients, industry groups, etc.)  
- Contact lists (decision makers, technical contacts, etc.)
- Job order lists (urgent positions, specific roles, etc.)

Return as JSON array.{excluded_names_text}"""

    return prompt


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
async def generate_lists_batch(used_names: set, data_counts: dict[str, int], batch_size: int) -> list[dict[str, Any]]:
    """Generate a batch of lists using AI."""
    prompt = create_lists_prompt(used_names, data_counts, batch_size)

    response = await make_anthropic_request(
        prompt=prompt,
        api_key=settings.ANTHROPIC_API_KEY,
        model=settings.DEFAULT_MODEL,
        max_tokens=4000,
        temperature=0.8,
    )

    if not response:
        logger.error("Failed to get response from Anthropic API")
        return []

    lists_data = parse_anthropic_response(response)
    if not lists_data:
        logger.error("Failed to parse lists data from API response")
        return []

    # Validate and clean the data
    validated_lists = []
    for list_item in lists_data:
        if validate_list_data(list_item, data_counts):
            # Clean and format the data
            cleaned_list = clean_list_data(list_item)
            validated_lists.append(cleaned_list)
        else:
            logger.warning(f"Invalid list data: {list_item}")

    return validated_lists


def validate_list_data(list_item: dict[str, Any], data_counts: dict[str, int]) -> bool:
    """Validate list data structure."""
    required_fields = ["description", "dataItemType"]

    for field in required_fields:
        if not list_item.get(field):
            return False

    # Validate data item type
    valid_types = [dt.value for dt in OpenCATSDataItemType]
    try:
        data_item_type = int(list_item.get("dataItemType", 0))
        if data_item_type not in valid_types:
            return False
    except (ValueError, TypeError):
        return False

    # Validate item IDs if provided
    item_ids = list_item.get("itemIds", [])
    if item_ids:
        # Get the corresponding data type name
        type_mapping = {100: "candidates", 200: "companies", 300: "contacts", 400: "joborders"}
        data_type_name = type_mapping.get(data_item_type)
        if data_type_name:
            max_id = data_counts.get(data_type_name, 0)
            for item_id in item_ids:
                try:
                    id_int = int(item_id)
                    if id_int < 1 or id_int > max_id:
                        logger.warning(f"Item ID {id_int} out of range for {data_type_name} (max: {max_id})")
                        return False
                except (ValueError, TypeError):
                    return False

    return True


def clean_list_data(list_item: dict[str, Any]) -> dict[str, Any]:
    """Clean and format list data."""
    # Ensure all required fields exist with defaults
    cleaned = {
        "description": list_item.get("description", "").strip(),
        "dataItemType": int(list_item.get("dataItemType", 100)),
        "itemIds": list_item.get("itemIds", []),
    }

    # Ensure itemIds is a list of integers
    if cleaned["itemIds"]:
        try:
            cleaned["itemIds"] = [int(item_id) for item_id in cleaned["itemIds"]]
        except (ValueError, TypeError):
            cleaned["itemIds"] = []

    return cleaned


async def lists(n_lists: int | None = None) -> dict[str, Any]:
    """Generate lists data."""
    target_count = n_lists or DEFAULT_LISTS_COUNT
    logger.info(f"📋 Starting list generation - Target: {target_count}")

    # Ensure data directory exists
    settings.DATA_PATH.mkdir(parents=True, exist_ok=True)

    # Validate API configuration
    validate_anthropic_config(settings.ANTHROPIC_API_KEY)

    # Load existing data
    existing = load_existing_lists()
    used_names = existing["used_names"]
    generated_lists = existing["generated_lists"]

    # Load data for list items
    all_data = load_data_for_lists()
    data_counts = {
        "candidates": len(all_data["candidates"]),
        "companies": len(all_data["companies"]),
        "contacts": len(all_data["contacts"]),
        "joborders": len(all_data["joborders"]),
    }

    # Check if we have any data to create lists with
    total_items = sum(data_counts.values())
    if total_items == 0:
        logger.warning("⚠️ No data available for creating lists. Generate other data types first.")
        return {"lists": generated_lists}

    current_count = len(generated_lists)
    remaining_count = max(0, target_count - current_count)

    if remaining_count == 0:
        logger.info(f"✅ Already have {current_count} lists, no generation needed")
        return {"lists": generated_lists}

    logger.info(f"📊 Current: {current_count}, Target: {target_count}, Generating: {remaining_count}")
    logger.info(f"📊 Available data: {data_counts}")

    # Generate lists in batches
    new_lists = []
    batches = (remaining_count + LISTS_BATCH_SIZE - 1) // LISTS_BATCH_SIZE

    for batch_num in range(batches):
        batch_size = min(LISTS_BATCH_SIZE, remaining_count - len(new_lists))
        logger.info(f"🔄 Generating batch {batch_num + 1}/{batches} ({batch_size} lists)")

        try:
            batch_lists = await generate_lists_batch(used_names, data_counts, batch_size)

            if batch_lists:
                # Update used names to avoid duplicates
                for list_item in batch_lists:
                    if list_item.get("description"):
                        used_names.add(list_item["description"].lower())

                new_lists.extend(batch_lists)
                logger.info(f"✅ Generated {len(batch_lists)} lists in batch {batch_num + 1}")
            else:
                logger.warning(f"⚠️ No lists generated in batch {batch_num + 1}")

        except Exception as e:
            logger.error(f"❌ Error in batch {batch_num + 1}: {e!s}")
            continue

        # Small delay between batches
        if batch_num < batches - 1:
            await asyncio.sleep(1)

    # Combine with existing data
    all_lists = generated_lists + new_lists

    # Save to file
    if save_to_json(all_lists, LISTS_FILEPATH):
        logger.succeed(f"✅ List generation completed! Generated {len(new_lists)} new lists, total: {len(all_lists)}")
    else:
        logger.error("❌ Failed to save lists data")

    return {"lists": all_lists}
