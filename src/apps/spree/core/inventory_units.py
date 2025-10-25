import json
import random
from pathlib import Path

from apps.spree.utils.constants import INVENTORY_UNITS_FILE, LINE_ITEMS_FILE, ORDERS_FILE, SHIPMENTS_FILE
from common.logger import Logger


logger = Logger()


async def generate_inventory_units():
    """Generate inventory units for orders based on line items."""
    logger.info("Generating inventory units...")

    try:
        # Load orders, line items, and shipments
        if not ORDERS_FILE.exists() or not LINE_ITEMS_FILE.exists() or not SHIPMENTS_FILE.exists():
            logger.error("Required files (orders, line items, shipments) not found. Run order generation first.")
            raise FileNotFoundError("Required files for inventory unit generation not found")

        with Path.open(ORDERS_FILE, "r", encoding="utf-8") as f:
            orders_data = json.load(f)
            orders = orders_data.get("orders", [])

        with Path.open(LINE_ITEMS_FILE, "r", encoding="utf-8") as f:
            line_items_data = json.load(f)
            line_items = line_items_data.get("line_items", [])

        with Path.open(SHIPMENTS_FILE, "r", encoding="utf-8") as f:
            shipments_data = json.load(f)
            shipments = shipments_data.get("shipments", [])

        logger.info(f"Found {len(orders)} orders, {len(line_items)} line items, and {len(shipments)} shipments")

        # Group line items by order
        line_items_by_order: dict[int, list] = {}
        for item in line_items:
            order_id = item.get("order_id")
            if order_id:
                if order_id not in line_items_by_order:
                    line_items_by_order[order_id] = []
                line_items_by_order[order_id].append(item)

        # Group shipments by order
        shipments_by_order: dict[int, list] = {}
        for shipment in shipments:
            order_id = shipment.get("order_id")
            if order_id:
                if order_id not in shipments_by_order:
                    shipments_by_order[order_id] = []
                shipments_by_order[order_id].append(shipment)

        # Generate inventory units
        inventory_units = []
        unit_id = 1

        for order in orders:
            order_id = order.get("id")
            order_state = order.get("state")

            if not order_id or order_id not in line_items_by_order:
                continue

            items = line_items_by_order[order_id]
            shipments_for_order = shipments_by_order.get(order_id, [])

            # Default state based on order state
            default_state = "on_hand"
            if order_state == "complete":
                default_state = "shipped"
            elif order_state == "canceled":
                default_state = "canceled"

            # Generate inventory units for each line item
            for item in items:
                line_item_id = item.get("id")
                variant_id = item.get("variant_id")
                quantity = item.get("quantity", 1)

                # Create inventory units based on quantity
                for _ in range(quantity):
                    # Assign to a shipment if available
                    shipment_id = None
                    if shipments_for_order:
                        shipment_id = random.choice(shipments_for_order).get("id")

                    # Determine unit state
                    state = default_state
                    if shipment_id and default_state == "shipped":
                        # Some units might be in different states for variety
                        state = random.choices(
                            ["shipped", "on_hand", "backordered"],
                            weights=[0.8, 0.1, 0.1],  # 80% shipped, 10% on_hand, 10% backordered
                            k=1,
                        )[0]

                    # Create inventory unit
                    inventory_unit = {
                        "id": unit_id,
                        "variant_id": variant_id,
                        "order_id": order_id,
                        "shipment_id": shipment_id,
                        "line_item_id": line_item_id,
                        "state": state,
                        "quantity": 1,
                        "pending": state != "shipped",
                        "original_return_item_id": None,
                    }

                    inventory_units.append(inventory_unit)
                    unit_id += 1

        logger.info(f"Generated {len(inventory_units)} inventory units")

        # Save to file
        inventory_units_data = {"inventory_units": inventory_units}
        INVENTORY_UNITS_FILE.parent.mkdir(parents=True, exist_ok=True)

        with Path.open(INVENTORY_UNITS_FILE, "w", encoding="utf-8") as f:
            json.dump(inventory_units_data, f, indent=2)

        logger.succeed(f"Successfully saved inventory units to {INVENTORY_UNITS_FILE}")
        return inventory_units_data

    except Exception as e:
        logger.error(f"Error generating inventory units: {e}")
        raise


async def seed_inventory_units():
    """Seed inventory units into the database."""
    from apps.spree.utils.database import db_client

    logger.start("Inserting inventory units into database...")

    try:
        # Load inventory units from JSON
        if not INVENTORY_UNITS_FILE.exists():
            logger.error(f"Inventory units file not found at {INVENTORY_UNITS_FILE}. Run generate command first.")
            raise FileNotFoundError("Inventory units file not found")

        with Path.open(INVENTORY_UNITS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            inventory_units = data.get("inventory_units", [])

        logger.info(f"Loaded {len(inventory_units)} inventory units from {INVENTORY_UNITS_FILE}")

        # Insert inventory units
        inserted_count = 0
        for unit in inventory_units:
            try:
                unit_id = unit.get("id")

                # Check if unit already exists
                existing_unit = await db_client.fetchrow("SELECT id FROM spree_inventory_units WHERE id = $1", unit_id)

                if existing_unit:
                    # Update existing unit
                    await db_client.execute(
                        """
                        UPDATE spree_inventory_units
                        SET variant_id = $1, order_id = $2, shipment_id = $3, state = $4,
                            line_item_id = $5, quantity = $6, pending = $7, original_return_item_id = $8,
                            updated_at = NOW()
                        WHERE id = $9
                        """,
                        unit.get("variant_id"),
                        unit.get("order_id"),
                        unit.get("shipment_id"),
                        unit.get("state"),
                        unit.get("line_item_id"),
                        unit.get("quantity"),
                        unit.get("pending"),
                        unit.get("original_return_item_id"),
                        unit_id,
                    )
                    logger.info(f"Updated inventory unit ID: {unit_id}")
                else:
                    # Insert new unit
                    await db_client.execute(
                        """
                        INSERT INTO spree_inventory_units
                        (id, variant_id, order_id, shipment_id, state, line_item_id,
                         quantity, pending, original_return_item_id, created_at, updated_at)
                        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, NOW(), NOW())
                        """,
                        unit_id,
                        unit.get("variant_id"),
                        unit.get("order_id"),
                        unit.get("shipment_id"),
                        unit.get("state"),
                        unit.get("line_item_id"),
                        unit.get("quantity"),
                        unit.get("pending"),
                        unit.get("original_return_item_id"),
                    )

                inserted_count += 1

            except Exception as e:
                logger.error(f"Failed to insert/update inventory unit {unit.get('id')}: {e}")
                continue

        logger.succeed(f"Successfully processed {inserted_count} inventory units")
        return True

    except Exception as e:
        logger.error(f"Error seeding inventory units: {e}")
        raise
