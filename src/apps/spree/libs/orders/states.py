"""Order and shipment state change tracking."""

import json
import random
from datetime import datetime, timedelta

from faker import Faker
from pydantic import BaseModel

from apps.spree.config.settings import settings
from apps.spree.utils.constants import ORDERS_FILE, SHIPMENTS_FILE, STATE_CHANGES_FILE
from apps.spree.utils.database import db_client
from common.logger import Logger


logger = Logger()
fake = Faker()


class StateChange(BaseModel):
    """State change model for tracking state transitions."""

    id: int  # noqa: A003, RUF100
    name: str
    previous_state: str
    stateful_id: int
    user_id: int | None
    stateful_type: str
    next_state: str
    created_at: str
    updated_at: str


async def generate_state_changes(orders_list=None):
    """Generate state changes for orders and shipments."""
    logger.info("Generating state changes...")

    try:
        # If orders_list is not provided, load from file
        if not orders_list:
            if not ORDERS_FILE.exists():
                logger.error(f"Orders file not found at {ORDERS_FILE}. Run generate orders command first.")
                return None

            with ORDERS_FILE.open(encoding="utf-8") as f:
                orders_data = json.load(f)
                orders_list = orders_data.get("orders", [])

        # Load shipments if available
        shipments_list = []
        if SHIPMENTS_FILE.exists():
            with SHIPMENTS_FILE.open(encoding="utf-8") as f:
                shipments_data = json.load(f)
                shipments_list = shipments_data.get("shipments", [])

        # Create list for all state changes
        state_changes_list = []
        state_change_id = 1

        # For each order, create state transition history
        for order in orders_list:
            order_id = order["id"]
            user_id = order["user_id"]
            final_state = order["state"]
            final_payment_state = order["payment_state"]

            # Get timestamps for sequencing the state changes
            created_at_str = order["created_at"]
            created_at = datetime.fromisoformat(created_at_str.replace(" ", "T")) if isinstance(created_at_str, str) else created_at_str

            # Use updated_at as a reference for completed orders
            updated_at_str = order["updated_at"]
            updated_at = datetime.fromisoformat(updated_at_str.replace(" ", "T")) if isinstance(updated_at_str, str) else updated_at_str

            # Define possible state sequences based on the final state
            state_sequence = []

            # Standard Spree checkout flow states are cart -> address -> delivery -> payment -> confirm -> complete

            if final_state == "complete":
                # Complete orders go through the full workflow
                state_sequence = [("cart", "address"), ("address", "delivery"), ("delivery", "payment"), ("payment", "confirm"), ("confirm", "complete")]

                # Some complete orders might have skipped confirm based on Spree's logic
                if random.random() < 0.3:  # 30% chance to skip confirm
                    state_sequence = [("cart", "address"), ("address", "delivery"), ("delivery", "payment"), ("payment", "complete")]
            elif final_state == "canceled":
                # Canceled orders can be canceled at different stages
                cancel_stage = random.choice(["cart", "address", "delivery", "payment", "confirm"])

                if cancel_stage == "cart":
                    state_sequence = [("cart", "canceled")]
                elif cancel_stage == "address":
                    state_sequence = [("cart", "address"), ("address", "canceled")]
                elif cancel_stage == "delivery":
                    state_sequence = [("cart", "address"), ("address", "delivery"), ("delivery", "canceled")]
                elif cancel_stage == "payment":
                    state_sequence = [("cart", "address"), ("address", "delivery"), ("delivery", "payment"), ("payment", "canceled")]
                elif cancel_stage == "confirm":
                    state_sequence = [("cart", "address"), ("address", "delivery"), ("delivery", "payment"), ("payment", "confirm"), ("confirm", "canceled")]
            elif final_state == "awaiting_return":
                # Orders awaiting return must have been completed first
                state_sequence = [("cart", "address"), ("address", "delivery"), ("delivery", "payment"), ("payment", "confirm"), ("confirm", "complete"), ("complete", "awaiting_return")]
            elif final_state == "returned":
                # Orders that are returned must have gone through awaiting_return
                state_sequence = [
                    ("cart", "address"),
                    ("address", "delivery"),
                    ("delivery", "payment"),
                    ("payment", "confirm"),
                    ("confirm", "complete"),
                    ("complete", "awaiting_return"),
                    ("awaiting_return", "returned"),
                ]
            else:
                # For orders still in progress, add transitions up to the current state
                in_progress_states = ["cart", "address", "delivery", "payment", "confirm"]
                if final_state in in_progress_states:
                    current_state_index = in_progress_states.index(final_state)
                    for i in range(current_state_index):
                        state_sequence.append((in_progress_states[i], in_progress_states[i + 1]))

            # Generate timestamps for each state change
            # Start with creation time and spread changes over a realistic timeframe
            transition_timestamps = []

            # For completed/canceled orders, distribute state changes between created_at and updated_at
            if final_state in ["complete", "canceled"]:
                total_time_delta = (updated_at - created_at) if isinstance(created_at, datetime) and isinstance(updated_at, datetime) else timedelta(hours=1)
                avg_step = total_time_delta / (len(state_sequence) + 1)

                current_time = created_at if isinstance(created_at, datetime) else datetime.now()
                for _ in state_sequence:
                    # Add some randomness to the time between state changes
                    step_variance = random.uniform(0.5, 1.5)  # 50% variance
                    next_time = current_time + (avg_step * step_variance)
                    transition_timestamps.append(next_time)
                    current_time = next_time
            else:
                # For in-progress orders, distribute state changes closer to creation time
                current_time = created_at if isinstance(created_at, datetime) else datetime.now()
                for _ in state_sequence:
                    next_time = current_time + timedelta(minutes=random.randint(2, 15))
                    transition_timestamps.append(next_time)
                    current_time = next_time

            # Create state changes for the order
            for i, (from_state, to_state) in enumerate(state_sequence):
                timestamp = transition_timestamps[i]

                # Determine if state change was done by user or system
                # System usually handles cart → address and confirm → complete
                # User is involved in other transitions
                change_user_id = None
                if to_state not in ["address", "complete"] and user_id and random.random() < 0.8:
                    change_user_id = user_id

                state_change = StateChange(
                    id=state_change_id,
                    name="order",
                    previous_state=from_state,
                    stateful_id=order_id,
                    user_id=change_user_id,
                    stateful_type="Spree::Order",
                    next_state=to_state,
                    created_at=timestamp.isoformat(),
                    updated_at=timestamp.isoformat(),
                )

                state_changes_list.append(state_change.model_dump())
                state_change_id += 1

            # Add payment state changes for completed orders
            if final_state == "complete" and final_payment_state:
                # Define payment state transitions based on Spree's payment state machine
                payment_state_sequence = []

                if final_payment_state == "paid":
                    # Most common path: balance_due -> paid
                    payment_state_sequence = [("balance_due", "paid")]
                elif final_payment_state == "credit_owed":
                    # For credit_owed, usually goes through paid first (e.g., refund after payment)
                    payment_state_sequence = [("balance_due", "paid"), ("paid", "credit_owed")]
                elif final_payment_state == "void":
                    # For void, could be from balance_due or paid (70% from balance_due, 30% from paid)
                    payment_state_sequence = [("balance_due", "void")] if random.random() < 0.7 else [("balance_due", "paid"), ("paid", "void")]
                elif final_payment_state == "failed":
                    # Failed payment typically starts from balance_due
                    payment_state_sequence = [("balance_due", "failed")]

                # Generate timestamps for payment state changes (after order completion)
                payment_timestamps = []
                last_order_timestamp = transition_timestamps[-1] if transition_timestamps else updated_at

                current_time = last_order_timestamp + timedelta(minutes=random.randint(1, 10))
                for _ in payment_state_sequence:
                    next_time = current_time + timedelta(minutes=random.randint(5, 30))
                    payment_timestamps.append(next_time)
                    current_time = next_time

                # Create payment state changes
                for i, (from_state, to_state) in enumerate(payment_state_sequence):
                    timestamp = payment_timestamps[i]

                    # Usually system or admin handles payment state changes
                    change_user_id = random.randint(1, 5) if random.random() < 0.6 else None

                    state_change = StateChange(
                        id=state_change_id,
                        name="payment",
                        previous_state=from_state,
                        stateful_id=order_id,
                        user_id=change_user_id,
                        stateful_type="Spree::Order",
                        next_state=to_state,
                        created_at=timestamp.isoformat(),
                        updated_at=timestamp.isoformat(),
                    )

                    state_changes_list.append(state_change.model_dump())
                    state_change_id += 1

        # Create state changes for shipments
        for shipment in shipments_list:
            shipment_id = shipment["id"]
            order_id = shipment["order_id"]
            final_state = shipment["state"]

            # Get corresponding order to align timestamps
            corresponding_order = next((o for o in orders_list if o["id"] == order_id), None)
            if not corresponding_order:
                continue

            # Use order timestamps as reference
            order_created_at_str = corresponding_order["created_at"]
            order_created_at = datetime.fromisoformat(order_created_at_str.replace(" ", "T")) if isinstance(order_created_at_str, str) else order_created_at_str

            # Try to find the shipment created_at time
            shipment_created_at_str = shipment["created_at"]
            shipment_created_at = datetime.fromisoformat(shipment_created_at_str.replace(" ", "T")) if isinstance(shipment_created_at_str, str) else shipment_created_at_str

            # Start time for shipment state changes should be after order creation
            start_time = shipment_created_at if isinstance(shipment_created_at, datetime) else (order_created_at + timedelta(minutes=random.randint(5, 30)))

            # Define shipment state sequences based on final state and payment state
            shipment_state_sequence = []

            # Get the payment state from the corresponding order
            payment_state = corresponding_order.get("payment_state")
            order_state = corresponding_order.get("state")

            # Don't ship products with unpaid payment states (void, balance_due, credit_owed, failed)
            if payment_state in ["void", "balance_due", "credit_owed", "failed"] or order_state in ["canceled", "awaiting_return", "returned"]:
                # For unpaid orders or canceled/returned orders, cancel the shipment
                cancel_from = random.choice(["pending", "ready", "backorder"])
                if cancel_from == "pending":
                    shipment_state_sequence = [("pending", "canceled")]
                elif cancel_from == "backorder":
                    shipment_state_sequence = [("backorder", "canceled")]
                else:  # ready
                    shipment_state_sequence = [("pending", "ready"), ("ready", "canceled")]
            elif final_state == "shipped":
                # Standard shipping flow
                if random.random() < 0.1:  # 10% chance for backorder
                    shipment_state_sequence = [("pending", "backorder"), ("backorder", "ready"), ("ready", "shipped")]
                else:
                    shipment_state_sequence = [("pending", "ready"), ("ready", "shipped")]
            elif final_state == "ready":
                # Ready for shipment (20% chance for backorder, 80% direct to ready)
                shipment_state_sequence = [("pending", "backorder"), ("backorder", "ready")] if random.random() < 0.2 else [("pending", "ready")]
            elif final_state == "partial":
                # Partial shipment (some items shipped, some not)
                shipment_state_sequence = [("pending", "ready"), ("ready", "partial")]
            elif final_state == "backorder":
                # Backordered items
                shipment_state_sequence = [("pending", "backorder")]

            # Generate timestamps for shipment state changes
            current_time = start_time
            for from_state, to_state in shipment_state_sequence:
                # More spacing between shipment state changes
                next_time = current_time + timedelta(minutes=random.randint(10, 120))

                # Determine if state change was done by user or system
                # Usually shipping staff handle these state changes
                change_user_id = random.randint(1, 5) if random.random() < 0.7 else None

                state_change = StateChange(
                    id=state_change_id,
                    name="shipment",
                    previous_state=from_state,
                    stateful_id=shipment_id,
                    user_id=change_user_id,
                    stateful_type="Spree::Shipment",
                    next_state=to_state,
                    created_at=next_time.isoformat(),
                    updated_at=next_time.isoformat(),
                )

                state_changes_list.append(state_change.model_dump())
                state_change_id += 1
                current_time = next_time

        # Save to file
        state_changes_dict = {"state_changes": state_changes_list}

        settings.DATA_PATH.mkdir(parents=True, exist_ok=True)
        STATE_CHANGES_FILE.parent.mkdir(parents=True, exist_ok=True)
        with STATE_CHANGES_FILE.open("w", encoding="utf-8") as f:
            json.dump(state_changes_dict, f, indent=2, ensure_ascii=False)

        logger.succeed(f"Successfully generated and saved {len(state_changes_list)} state changes to {STATE_CHANGES_FILE}")
        return state_changes_dict

    except Exception as e:
        logger.error(f"Error generating state changes: {e}")
        raise


async def seed_state_changes():
    """Insert state changes into the database."""
    logger.start("Inserting state changes into spree_state_changes table...")

    try:
        # Load state changes from JSON file
        if not STATE_CHANGES_FILE.exists():
            logger.error(f"State changes file not found at {STATE_CHANGES_FILE}. Run generate command first.")
            raise FileNotFoundError("State changes file not found")

        with STATE_CHANGES_FILE.open(encoding="utf-8") as f:
            data = json.load(f)

        state_changes = data.get("state_changes", [])
        logger.info(f"Loaded {len(state_changes)} state changes from {STATE_CHANGES_FILE}")

        # Insert state changes
        inserted_count = 0

        # Track the latest state change for each order, payment state, and shipment
        latest_order_states = {}
        latest_payment_states = {}
        latest_shipment_states = {}

        # First pass: Insert all state changes and track the latest ones
        for state_change in state_changes:
            try:
                # Convert datetime strings to actual datetime objects
                if isinstance(state_change["created_at"], str):
                    state_change["created_at"] = datetime.fromisoformat(state_change["created_at"])
                if isinstance(state_change["updated_at"], str):
                    state_change["updated_at"] = datetime.fromisoformat(state_change["updated_at"])

                # Insert state change with explicit ID
                await db_client.execute(
                    """
                    INSERT INTO spree_state_changes (
                        id, name, previous_state, stateful_id, user_id, 
                        stateful_type, next_state, created_at, updated_at
                    ) VALUES (
                        $1, $2, $3, $4, $5, $6, $7, $8, $9
                    )
                    """,
                    state_change["id"],
                    state_change["name"],
                    state_change["previous_state"],
                    state_change["stateful_id"],
                    state_change["user_id"],
                    state_change["stateful_type"],
                    state_change["next_state"],
                    state_change["created_at"],
                    state_change["updated_at"],
                )

                # Track the latest state change for orders and shipments
                if state_change["stateful_type"] == "Spree::Order" and state_change["name"] == "order":
                    order_id = state_change["stateful_id"]
                    if order_id not in latest_order_states or state_change["created_at"] > latest_order_states[order_id]["created_at"]:
                        latest_order_states[order_id] = {"state": state_change["next_state"], "created_at": state_change["created_at"]}
                elif state_change["stateful_type"] == "Spree::Order" and state_change["name"] == "payment":
                    order_id = state_change["stateful_id"]
                    if order_id not in latest_payment_states or state_change["created_at"] > latest_payment_states[order_id]["created_at"]:
                        latest_payment_states[order_id] = {"state": state_change["next_state"], "created_at": state_change["created_at"]}
                elif state_change["stateful_type"] == "Spree::Shipment":
                    shipment_id = state_change["stateful_id"]
                    if shipment_id not in latest_shipment_states or state_change["created_at"] > latest_shipment_states[shipment_id]["created_at"]:
                        latest_shipment_states[shipment_id] = {"state": state_change["next_state"], "created_at": state_change["created_at"], "shipment_id": shipment_id}

                inserted_count += 1

            except Exception as e:
                logger.error(f"Failed to insert state change {state_change.get('id')}: {e}")
                continue

        # Second pass: Update orders with their latest state
        logger.info("Updating orders with their latest state changes...")
        for order_id, state_info in latest_order_states.items():
            try:
                await db_client.execute("UPDATE spree_orders SET state = $1, updated_at = $2 WHERE id = $3", state_info["state"], state_info["created_at"], order_id)
            except Exception as e:
                logger.error(f"Failed to update order {order_id} with latest state: {e}")

        # Update orders with their latest payment state
        logger.info("Updating orders with their latest payment states...")
        for order_id, payment_info in latest_payment_states.items():
            try:
                await db_client.execute("UPDATE spree_orders SET payment_state = $1, updated_at = $2 WHERE id = $3", payment_info["state"], payment_info["created_at"], order_id)
            except Exception as e:
                logger.error(f"Failed to update order {order_id} with latest payment state: {e}")

        # Get shipment to order mapping
        shipment_order_map = {}
        if latest_shipment_states:
            shipment_ids = list(latest_shipment_states.keys())
            shipment_records = await db_client.fetch("SELECT id, order_id FROM spree_shipments WHERE id = ANY($1)", shipment_ids)
            for record in shipment_records:
                shipment_order_map[record["id"]] = record["order_id"]

        # Update orders with their shipment states
        for shipment_id, state_info in latest_shipment_states.items():
            if shipment_id in shipment_order_map:
                order_id = shipment_order_map[shipment_id]
                try:
                    # First check the payment state - don't set shipment to shipped if payment is unpaid
                    payment_state = await db_client.fetchval("SELECT payment_state FROM spree_orders WHERE id = $1", order_id)

                    # If payment is unpaid but shipment is shipped, override to canceled
                    shipment_state = state_info["state"]
                    if payment_state in ["void", "balance_due", "credit_owed"] and shipment_state == "shipped":
                        shipment_state = "canceled"
                        # Also update the shipment record itself
                        await db_client.execute("UPDATE spree_shipments SET state = $1 WHERE id = $2", "canceled", shipment_id)

                    await db_client.execute("UPDATE spree_orders SET shipment_state = $1, updated_at = $2 WHERE id = $3", shipment_state, state_info["created_at"], order_id)
                except Exception as e:
                    logger.error(f"Failed to update order {order_id} with shipment state: {e}")

        logger.succeed(f"Successfully inserted {inserted_count} state changes into the database")
        logger.succeed(f"Updated {len(latest_order_states)} orders with their latest state")
        logger.succeed(f"Updated {len(latest_payment_states)} orders with their latest payment state")
        logger.succeed(f"Updated {len(latest_shipment_states)} orders with their latest shipment state")

        # Update the sequence to avoid future conflicts with auto-generated IDs
        if inserted_count > 0:
            max_id = max(state_change["id"] for state_change in state_changes)
            await db_client.execute(f"SELECT setval('spree_state_changes_id_seq', {max_id}, true)")

    except Exception as e:
        logger.error(f"Error seeding state changes in database: {e}")
        raise
