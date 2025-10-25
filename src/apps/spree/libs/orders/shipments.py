"""Shipment model and related functionality."""

import json
import random
from datetime import datetime

from faker import Faker
from pydantic import BaseModel

from apps.spree.config.settings import settings
from apps.spree.utils.constants import ADDRESSES_FILE, ORDERS_FILE, PRODUCTS_FILE, SHIPMENTS_FILE, STOCK_LOCATIONS_FILE
from apps.spree.utils.database import db_client
from common.logger import Logger


logger = Logger()
fake = Faker()


class Shipment(BaseModel):
    """Shipment model for orders."""

    id: int  # noqa: A003, RUF100
    tracking: str | None
    number: str
    cost: float
    shipped_at: str | None
    order_id: int
    address_id: int | None
    state: str
    created_at: str
    updated_at: str
    stock_location_id: int
    adjustment_total: float = 0.0
    additional_tax_total: float = 0.0
    promo_total: float = 0.0
    included_tax_total: float = 0.0
    pre_tax_amount: float = 0.0
    taxable_adjustment_total: float = 0.0
    non_taxable_adjustment_total: float = 0.0
    public_metadata: dict | None = None
    private_metadata: dict | None = None


def generate_shipment_number() -> str:
    """Generate a unique shipment number with 'H' prefix."""
    return f"H{random.randint(10000000000, 99999999999)}"


async def generate_shipments(orders_list=None):
    """Generate shipments for existing orders."""
    logger.info("Generating shipments...")

    try:
        # If orders_list is not provided, load from file
        if not orders_list:
            if not ORDERS_FILE.exists():
                logger.error(f"Orders file not found at {ORDERS_FILE}. Run generate orders command first.")
                return None

            with ORDERS_FILE.open(encoding="utf-8") as f:
                orders_data = json.load(f)
                orders_list = orders_data.get("orders", [])

        if not orders_list:
            logger.error("No orders found for shipment generation.")
            return None

        # Create list for all shipments
        shipments_list = []
        shipment_id = 1

        # Load addresses data for shipment addresses
        addresses = []
        if ADDRESSES_FILE.exists():
            with ADDRESSES_FILE.open(encoding="utf-8") as f:
                addresses_data = json.load(f)
                addresses = addresses_data.get("addresses", [])

        # Load products data for stock information
        products = []
        if PRODUCTS_FILE.exists():
            with PRODUCTS_FILE.open(encoding="utf-8") as f:
                products_data = json.load(f)
                products = products_data.get("products", [])

        logger.info(f"Loaded {len(addresses)} addresses and {len(products)} products for shipment generation")

        # Define possible shipment states and their probabilities
        shipment_states = {
            "pending": 30,
            "ready": 20,
            "shipped": 40,
            "canceled": 10,
        }

        # Load stock locations from JSON file
        stock_locations = []
        if STOCK_LOCATIONS_FILE.exists():
            with STOCK_LOCATIONS_FILE.open(encoding="utf-8") as f:
                stock_locations_data = json.load(f)
                stock_locations = stock_locations_data.get("stock_locations", [])

        if not stock_locations:
            # Fallback if no stock locations found
            stock_locations = [{"id": 1, "name": "Default"}]

        logger.info(f"Loaded {len(stock_locations)} stock locations for shipment generation")

        for order in orders_list:
            # Skip orders that aren't in a state that would have shipments
            if order["state"] not in ["complete", "canceled"]:
                continue

            # Determine the number of shipments for this order (usually 1, sometimes 2)
            num_shipments = 1 if random.random() < 0.9 else 2  # 90% have 1 shipment, 10% have 2

            # Get order details
            order_id = order["id"]
            created_at = order["created_at"]
            updated_at = order["updated_at"]

            # Use the fixed ship_address_id from the order if available
            address_id = order["ship_address_id"]

            # If the order doesn't have a shipping address but has a user_id (customer order, not guest)
            if not address_id and order["user_id"]:
                user_id = order["user_id"]

                # Find addresses specifically linked to this user's ID
                user_addresses = [addr for addr in addresses if addr.get("user_id") == user_id]

                # If user has addresses, use one of them with its fixed ID
                if user_addresses:
                    chosen_address = random.choice(user_addresses)
                    # Use the fixed ID from addresses.json directly
                    address_id = chosen_address["id"]

                # If still no address_id found but we know this is a customer, use their user_id
                # as a basis for a predictable address ID
                if not address_id and user_id:
                    # Use user_id * 10 + some small offset to create a predictable but unique address ID
                    address_id = user_id * 10 + random.randint(1, 5)

            # Align shipment state with order's shipment_state when possible
            # Never ship a product with payment state of void, balance_due, or credit_owed
            if order["payment_state"] in ["void", "balance_due", "credit_owed"] or order["state"] == "canceled":
                shipment_state = "canceled"
            elif order["shipment_state"] and order["shipment_state"] != "partial":
                shipment_state = order["shipment_state"]
            else:
                # Otherwise, determine based on probability
                shipment_state = random.choices(population=list(shipment_states.keys()), weights=list(shipment_states.values()), k=1)[0]

            # For each shipment in this order
            for _ in range(num_shipments):
                # Create shipment timestamp details
                shipped_at = None
                if shipment_state == "shipped":
                    # If shipped, set a shipped_at date after order creation
                    order_created = datetime.fromisoformat(created_at.replace(" ", "T")) if isinstance(created_at, str) else created_at
                    shipped_at = fake.date_time_between(start_date=order_created, end_date="+30d").isoformat()

                # Set cost (shipping cost)
                cost = round(random.uniform(5.99, 15.99), 2)

                # For completed orders with shipments, ensure the order has this cost in shipment_total
                if order["state"] == "complete" and shipment_state != "canceled":
                    # Already handled in the order generation
                    pass

                # Select a stock location based on shipment state and other factors
                # For shipped items, prefer distribution centers
                # For pending/ready, use main warehouse
                # For canceled, use any location

                if shipment_state == "shipped":
                    # For shipped items, prefer distribution centers or main warehouses (better shipping capacity)
                    preferred_locations = [loc for loc in stock_locations if "Distribution" in loc["name"] or "Main Warehouse" in loc["name"]]
                    if not preferred_locations:
                        preferred_locations = stock_locations

                    stock_location = random.choice(preferred_locations)
                elif shipment_state in ["pending", "ready"]:
                    # For pending/ready, prefer main warehouse (default location) or fulfillment centers
                    preferred_locations = [loc for loc in stock_locations if loc.get("default", False) or "Fulfillment" in loc["name"]]
                    if not preferred_locations:
                        preferred_locations = stock_locations

                    stock_location = random.choice(preferred_locations)
                else:
                    # For canceled or other states, use any location
                    stock_location = random.choice(stock_locations)

                # Generate tracking number for shipped or ready states (sometimes)
                tracking = None
                if shipment_state == "shipped" or (shipment_state == "ready" and random.random() < 0.6):
                    tracking = f"TRACK{random.randint(10000000, 99999999)}"

                # Create the shipment
                shipment = Shipment(
                    id=shipment_id,
                    tracking=tracking,
                    number=generate_shipment_number(),
                    cost=cost,
                    shipped_at=shipped_at,
                    order_id=order_id,
                    address_id=address_id,
                    state=shipment_state,
                    created_at=created_at,
                    updated_at=updated_at,
                    stock_location_id=stock_location["id"],
                    adjustment_total=0.0,
                    additional_tax_total=0.0,
                    promo_total=0.0,
                    included_tax_total=0.0,
                    pre_tax_amount=round(cost, 4),
                    taxable_adjustment_total=0.0,
                    non_taxable_adjustment_total=0.0,
                    public_metadata=None,
                    private_metadata=None,
                )

                shipments_list.append(shipment.model_dump())
                shipment_id += 1

        # Save to file
        shipments_dict = {"shipments": shipments_list}

        settings.DATA_PATH.mkdir(parents=True, exist_ok=True)
        SHIPMENTS_FILE.parent.mkdir(parents=True, exist_ok=True)
        with SHIPMENTS_FILE.open("w", encoding="utf-8") as f:
            json.dump(shipments_dict, f, indent=2, ensure_ascii=False)

        logger.succeed(f"Successfully generated and saved {len(shipments_list)} shipments to {SHIPMENTS_FILE}")
        return shipments_dict

    except Exception as e:
        logger.error(f"Error generating shipments: {e}")
        raise


async def seed_shipments():
    """Insert shipments and their shipping rates into the database."""
    logger.start("Inserting shipments into spree_shipments table and generating shipping rates...")

    try:
        # Load shipments from JSON file
        if not SHIPMENTS_FILE.exists():
            logger.error(f"Shipments file not found at {SHIPMENTS_FILE}. Run generate command first.")
            raise FileNotFoundError("Shipments file not found")

        with SHIPMENTS_FILE.open(encoding="utf-8") as f:
            data = json.load(f)

        shipments = data.get("shipments", [])
        logger.info(f"Loaded {len(shipments)} shipments from {SHIPMENTS_FILE}")

        # Get actual order IDs from database - now they should match our JSON IDs
        order_map = {}
        order_records = await db_client.fetch("SELECT id FROM spree_orders")
        for order in order_records:
            order_map[order["id"]] = order["id"]

        # Get actual address IDs from database
        address_map = {}
        address_records = await db_client.fetch("SELECT id FROM spree_addresses")
        for address in address_records:
            address_map[address["id"]] = address["id"]

        # Get stock location IDs from database
        stock_location_map = {}
        stock_location_records = await db_client.fetch("SELECT id FROM spree_stock_locations")
        for location in stock_location_records:
            stock_location_map[location["id"]] = location["id"]

        # If no stock locations in DB, use default (ID 1)
        if not stock_location_map:
            stock_location_map = {1: 1}
            logger.warning("No stock locations found in database, using default ID 1")

        # Insert shipments
        inserted_count = 0
        for shipment in shipments:
            try:
                # Verify order exists
                if shipment["order_id"] not in order_map:
                    logger.warning(f"Order ID {shipment['order_id']} not found in database, skipping shipment {shipment['number']}")
                    continue

                # Verify stock location exists
                if shipment["stock_location_id"] not in stock_location_map:
                    # Use default stock location (ID 1) if the specified one doesn't exist
                    logger.warning(f"Stock location ID {shipment['stock_location_id']} not found in database for shipment {shipment['number']}, using default")
                    shipment["stock_location_id"] = 1

                # Convert datetime strings to actual datetime objects
                if isinstance(shipment["created_at"], str):
                    shipment["created_at"] = datetime.fromisoformat(shipment["created_at"].replace(" ", "T"))
                if isinstance(shipment["updated_at"], str):
                    shipment["updated_at"] = datetime.fromisoformat(shipment["updated_at"].replace(" ", "T"))
                if shipment["shipped_at"] and isinstance(shipment["shipped_at"], str):
                    shipment["shipped_at"] = datetime.fromisoformat(shipment["shipped_at"])

                # Insert shipment with explicit ID
                await db_client.execute(
                    """
                    INSERT INTO spree_shipments (
                        id, tracking, number, cost, shipped_at, order_id, address_id, state,
                        created_at, updated_at, stock_location_id, adjustment_total,
                        additional_tax_total, promo_total, included_tax_total, pre_tax_amount,
                        taxable_adjustment_total, non_taxable_adjustment_total, 
                        public_metadata, private_metadata
                    ) VALUES (
                        $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, 
                        $13, $14, $15, $16, $17, $18, $19, $20
                    )
                    """,
                    shipment["id"],
                    shipment["tracking"],
                    shipment["number"],
                    shipment["cost"],
                    shipment["shipped_at"],
                    shipment["order_id"],
                    shipment["address_id"],
                    shipment["state"],
                    shipment["created_at"],
                    shipment["updated_at"],
                    shipment["stock_location_id"],
                    shipment["adjustment_total"],
                    shipment["additional_tax_total"],
                    shipment["promo_total"],
                    shipment["included_tax_total"],
                    shipment["pre_tax_amount"],
                    shipment["taxable_adjustment_total"],
                    shipment["non_taxable_adjustment_total"],
                    None,  # public_metadata
                    None,  # private_metadata
                )

                inserted_count += 1

            except Exception as e:
                logger.error(f"Failed to insert shipment {shipment.get('number')}: {e}")
                continue

        logger.succeed(f"Successfully inserted {inserted_count} shipments into the database")

        # Update the sequence to avoid future conflicts with auto-generated IDs
        if inserted_count > 0:
            max_id = max(shipment["id"] for shipment in shipments)
            await db_client.execute(f"SELECT setval('spree_shipments_id_seq', {max_id}, true)")

        # Add shipping rates for the shipments
        from apps.spree.libs.orders.shipping_rates import seed_shipping_rates

        await seed_shipping_rates()

    except Exception as e:
        logger.error(f"Error seeding shipments in database: {e}")
        raise
