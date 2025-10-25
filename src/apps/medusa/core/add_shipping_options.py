import asyncio

from apps.medusa.utils.api_utils import MedusaAPIUtils
from common.logger import logger


async def select_shipping_option(order_id: str, shipping_option_id: str | None, api_utils: MedusaAPIUtils) -> str | None:
    """Select shipping option for the order."""
    order_details = await api_utils.fetch_draft_order_by_id(order_id)
    cart_id = order_details.get("cart_id") if order_details else None

    shipping_options = await api_utils.fetch_shipping_options(cart_id)

    if not shipping_options:
        logger.warning(f"No shipping options found for order {order_id}")
        return None

    if shipping_option_id:
        option = next((opt for opt in shipping_options if opt.get("id") == shipping_option_id), None)
        if option:
            return option.get("id")

    standard_option = next((opt for opt in shipping_options if "standard shipping" in opt.get("name", "").lower()), None)
    if standard_option:
        return standard_option.get("id")

    return shipping_options[0].get("id") if shipping_options else None


async def add_shipping_to_order(order_id: str, shipping_option_id: str | None, api_utils: MedusaAPIUtils) -> bool:
    """Add shipping to a draft order through the complete workflow."""
    try:
        selected_shipping_id = await select_shipping_option(order_id, shipping_option_id, api_utils)

        if not selected_shipping_id or not isinstance(selected_shipping_id, str):
            logger.warning(f"Invalid shipping option ID for order {order_id}")
            return False

        workflow_steps = [
            ("edit_draft_order", [order_id]),
            ("add_shipping_method_to_draft", [order_id, selected_shipping_id]),
            ("request_draft_order_confirmation", [order_id]),
            ("confirm_draft_order_changes", [order_id]),
        ]

        for method_name, args in workflow_steps:
            method = getattr(api_utils, method_name)
            if not await method(*args):
                logger.error(f"Failed to {method_name.replace('_', ' ')} for order {order_id}")
                return False

        logger.info(f"Added shipping to order: {order_id}")
        return True

    except Exception as e:
        logger.error(f"Error in shipping workflow for order {order_id}: {e}")
        return False


async def process_all_draft_orders(shipping_option_id: str | None, api_utils: MedusaAPIUtils) -> dict[str, int]:
    """Process all draft orders to add shipping options."""
    draft_orders = await api_utils.fetch_all_draft_orders()

    if not draft_orders:
        logger.warning("No draft orders to process")
        return {"total": 0, "successful": 0, "failed": 0, "skipped": 0}

    logger.info(f"Processing {len(draft_orders)} draft orders...")

    successful = 0
    failed = 0
    skipped = 0

    for idx, draft_order in enumerate(draft_orders, 1):
        order_id = draft_order.get("id")

        if not order_id:
            failed += 1
            continue

        if draft_order.get("shipping_methods"):
            skipped += 1
            continue

        logger.info(f"[{idx}/{len(draft_orders)}] Processing order {order_id}...")
        result = await add_shipping_to_order(order_id, shipping_option_id, api_utils)

        if result:
            successful += 1
            logger.info(f"[{idx}/{len(draft_orders)}] Success - Total: {successful} successful, {failed} failed, {skipped} skipped")
        else:
            failed += 1
            logger.warning(f"[{idx}/{len(draft_orders)}] Failed - Total: {successful} successful, {failed} failed, {skipped} skipped")

    logger.info(f"Draft orders processed: {successful} successful, {failed} failed, {skipped} skipped")

    return {"total": len(draft_orders), "successful": successful, "failed": failed, "skipped": skipped}


async def add_shipping_to_draft_orders(shipping_option_id: str | None = None):
    async with MedusaAPIUtils() as api_utils:
        return await process_all_draft_orders(shipping_option_id, api_utils)


if __name__ == "__main__":
    asyncio.run(add_shipping_to_draft_orders())
