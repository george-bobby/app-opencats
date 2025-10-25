"""Seed saved lists data into OpenCATS."""

import asyncio
from typing import Any

from tenacity import retry, stop_after_attempt, wait_fixed

from apps.opencats.config.constants import LISTS_FILEPATH
from apps.opencats.utils.api_utils import OpenCATSAPIUtils
from apps.opencats.utils.data_utils import load_existing_data
from common.logger import logger


@retry(stop=stop_after_attempt(3), wait=wait_fixed(2))
async def seed_lists() -> dict[str, Any]:
    """Seed saved lists data into OpenCATS."""
    logger.info("📋 Starting list seeding...")

    # Load generated lists data
    lists_data = load_existing_data(LISTS_FILEPATH)

    if not lists_data:
        logger.warning("⚠️ No lists data found. Run generation first.")
        return {"seeded_lists": 0, "errors": 0}

    logger.info(f"📊 Found {len(lists_data)} lists to seed")

    seeded_count = 0
    error_count = 0
    seeded_lists = []

    async with OpenCATSAPIUtils() as api:
        for idx, list_item in enumerate(lists_data):
            list_name = list_item.get("description", "Unknown")
            logger.info(f"🔄 Seeding list {idx + 1}/{len(lists_data)}: {list_name}")

            try:
                # First, create the list using AJAX
                list_data = {
                    "description": list_item.get("description", ""),
                    "dataItemType": str(list_item.get("dataItemType", "")),
                }

                # Submit list creation to OpenCATS via AJAX
                result = await api.ajax_request("lists:newList", list_data)

                if result and result.get("status_code") == 200:
                    # Try to get the list ID from the lists page
                    list_id = await api.get_latest_entity_id("lists", "list")

                    if list_id:
                        logger.info(f"✅ List '{list_name}' created successfully (ID: {list_id})")

                        # Now add items to the list if any
                        item_ids = list_item.get("itemIds", [])
                        if item_ids:
                            items_added = await add_items_to_list(api, list_id, list_item.get("dataItemType"), item_ids)
                            logger.info(f"📝 Added {items_added} items to list '{list_name}'")

                        seeded_lists.append({"original_data": list_item, "opencats_id": list_id, "items_added": len(item_ids) if item_ids else 0, "status": "success"})
                        seeded_count += 1
                    else:
                        logger.warning(f"⚠️ List '{list_name}' may have been created but ID not found")
                        seeded_lists.append({"original_data": list_item, "opencats_id": None, "status": "unknown"})
                        seeded_count += 1
                else:
                    logger.error(f"❌ Failed to seed list '{list_name}': {result}")
                    seeded_lists.append({"original_data": list_item, "opencats_id": None, "status": "failed", "error": str(result)})
                    error_count += 1

            except Exception as e:
                logger.error(f"❌ Error seeding list '{list_name}': {e!s}")
                seeded_lists.append({"original_data": list_item, "opencats_id": None, "status": "error", "error": str(e)})
                error_count += 1

            # Small delay between requests to avoid overwhelming the server
            await asyncio.sleep(0.5)

    logger.succeed(f"✅ List seeding completed! Seeded: {seeded_count}, Errors: {error_count}")

    return {"seeded_lists": seeded_count, "errors": error_count, "details": seeded_lists}


@retry(stop=stop_after_attempt(3), wait=wait_fixed(2))
async def add_items_to_list(api: OpenCATSAPIUtils, list_id: int, data_item_type: int, item_ids: list[int]) -> int:
    """Add items to a saved list using AJAX batch operation."""
    if not item_ids:
        return 0

    try:
        # Prepare data for adding items to list (batch operation)
        # Convert item IDs to comma-separated string
        items_csv = ",".join(str(item_id) for item_id in item_ids)

        add_items_data = {
            "listsToAdd": str(list_id),
            "itemsToAdd": items_csv,
            "dataItemType": str(data_item_type),
        }

        # Submit items addition to OpenCATS via AJAX
        result = await api.ajax_request("lists:addToLists", add_items_data)

        if result and result.get("status_code") == 200:
            return len(item_ids)
        else:
            logger.warning(f"⚠️ Failed to add items to list {list_id}: {result}")
            return 0

    except Exception as e:
        logger.warning(f"⚠️ Error adding items to list {list_id}: {e!s}")
        return 0
