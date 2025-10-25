"""Order model and related functionality."""

import json
import random
import secrets
from datetime import datetime

from faker import Faker
from pydantic import BaseModel

from apps.spree.config.settings import settings
from apps.spree.libs.orders.guests import add_addresses_to_guest_orders
from apps.spree.libs.orders.line_items import LineItem, generate_line_items, seed_line_items
from apps.spree.libs.orders.shipments import Shipment, generate_shipment_number, generate_shipments, seed_shipments
from apps.spree.libs.orders.shipping_rates import seed_shipping_rates
from apps.spree.libs.orders.states import StateChange, generate_state_changes, seed_state_changes
from apps.spree.utils.constants import ADDRESSES_FILE, ORDERS_FILE, PRODUCTS_FILE, USERS_FILE
from apps.spree.utils.database import db_client
from common.logger import Logger


logger = Logger()
fake = Faker()


class Order(BaseModel):
    """Individual order model."""

    id: int  # noqa: A003, RUF100
    number: str
    item_total: float
    total: float
    state: str
    adjustment_total: float
    user_id: int | None
    completed_at: str | None
    bill_address_id: int | None
    ship_address_id: int | None
    payment_total: float
    shipment_state: str | None
    payment_state: str | None
    email: str
    special_instructions: str | None
    created_at: str | None
    updated_at: str | None
    currency: str
    last_ip_address: str | None
    created_by_id: int | None
    shipment_total: float
    additional_tax_total: float
    promo_total: float
    channel: str
    included_tax_total: float
    item_count: int
    approver_id: int | None
    approved_at: str | None
    confirmation_delivered: bool
    considered_risky: bool
    token: str
    canceled_at: str | None
    canceler_id: int | None
    store_id: int
    state_lock_version: int
    taxable_adjustment_total: float
    non_taxable_adjustment_total: float
    store_owner_notification_delivered: bool | None
    public_metadata: dict | None
    private_metadata: dict | None
    internal_note: str | None


def generate_order_number() -> str:
    """Generate a unique order number with 'R' prefix."""
    return f"R{random.randint(100000000, 999999999)}"


def generate_order_token() -> str:
    """Generate an order token."""
    return f"{secrets.token_urlsafe(22)}{int(datetime.now().timestamp())}"


async def generate_orders(number_of_orders: int = 100):
    """Generate realistic orders using Faker."""
    logger.info(f"Generating {number_of_orders} orders...")

    try:
        # Load users data to reference in orders
        if not USERS_FILE.exists():
            logger.error(f"Users file not found at {USERS_FILE}. Run generate users command first.")
            return None

        with USERS_FILE.open(encoding="utf-8") as f:
            users_data = json.load(f)
            all_users = users_data.get("users", [])

            # Filter users to only include those with is_customer=true
            users = [user for user in all_users if user.get("is_customer", False) is True]

            logger.info(f"Filtered {len(users)} customer users from {len(all_users)} total users")

        # Load addresses data to reference in orders
        if not ADDRESSES_FILE.exists():
            logger.error(f"Addresses file not found at {ADDRESSES_FILE}. Run generate users command first.")
            return None

        with ADDRESSES_FILE.open(encoding="utf-8") as f:
            addresses_data = json.load(f)
            addresses = addresses_data.get("addresses", [])

        # Organize addresses by user_id using the fixed IDs
        user_addresses = {}
        for address in addresses:
            user_id = address["user_id"]
            if user_id not in user_addresses:
                user_addresses[user_id] = []
            user_addresses[user_id].append(address)

        # Load products data to create order items
        if not PRODUCTS_FILE.exists():
            logger.error(f"Products file not found at {PRODUCTS_FILE}. Run generate products command first.")
            return None

        with PRODUCTS_FILE.open(encoding="utf-8") as f:
            products_data = json.load(f)
            products = products_data.get("products", [])

        if not products:
            logger.error("No products found in products data.")
            return None

        logger.info(f"Loaded {len(users)} users, {len(addresses)} addresses, {len(products)} products for order generation.")

        # Define possible order states and their probabilities
        order_states = {
            "cart": 5,  # Very few in cart state
            "address": 5,  # Very few in address state
            "delivery": 5,  # Very few in delivery state
            "payment": 5,  # Very few in payment state
            "confirm": 5,  # Very few in confirm state
            "complete": 65,  # Most orders are completed
            "canceled": 5,  # Some orders are canceled
            "awaiting_return": 3,  # Few orders awaiting return
            "returned": 2,  # Few orders returned
        }

        # Define possible shipment states based on Spree's SHIPMENT_STATES
        shipment_states = {
            "pending": 10,  # Not ready for shipment
            "ready": 10,  # Ready for shipment
            "shipped": 60,  # Shipment has been shipped
            "canceled": 10,  # Shipment was canceled
            "partial": 5,  # Partially shipped
            "backorder": 5,  # Some items are backordered
        }

        # Define possible payment states based on Spree's PAYMENT_STATES
        payment_states = {
            "balance_due": 10,  # Order has outstanding balance
            "paid": 80,  # Order is fully paid
            "credit_owed": 5,  # Customer is owed money (e.g., overpaid)
            "void": 3,  # Payment was voided
            "failed": 2,  # Payment failed
        }

        # Generate orders
        orders_list = []
        for i in range(1, number_of_orders + 1):
            # Determine if this is a guest order or user order
            is_guest_order = random.random() < 0.15  # 15% are guest orders

            if is_guest_order:
                # Generate guest details
                user_id = None
                # Use more realistic email domains for guest orders
                email = f"{fake.user_name()}@{random.choice(['gmail.com', 'yahoo.com', 'outlook.com', 'icloud.com', 'hotmail.com'])}"
                created_by_id = None

                # Generate addresses for guest orders too
                # Will need to create these addresses during seeding
                # Use negative IDs to indicate these are guest addresses
                guest_bill_address_id = -i  # Use negative order ID for billing address
                guest_ship_address_id = -i - 1000  # Use negative order ID - 1000 for shipping address

                # Store these IDs - they'll be replaced with real DB IDs during seeding
                bill_address_id = guest_bill_address_id
                ship_address_id = guest_ship_address_id
            else:
                # Select a random user with their fixed ID
                user = random.choice(users)
                user_id = user["id"]  # Use the fixed ID from users.json
                email = user["email"]
                created_by_id = user_id  # Same as user_id

                # Try to get addresses for this user
                user_addr = user_addresses.get(user_id, [])

                if user_addr:
                    # Randomly select addresses or use None
                    has_addresses = random.random() < 0.9  # 90% chance to have addresses

                    if has_addresses and len(user_addr) > 0:
                        # Use fixed address IDs from the addresses.json data
                        address = random.choice(user_addr)
                        bill_address_id = address["id"]  # Use the fixed ID from addresses.json

                        # 70% chance to use the same address for shipping
                        if random.random() < 0.7 or len(user_addr) == 1:
                            ship_address_id = bill_address_id
                        else:
                            # Use a different address for shipping
                            other_addresses = [addr for addr in user_addr if addr["id"] != bill_address_id]
                            if other_addresses:
                                ship_address = random.choice(other_addresses)
                                ship_address_id = ship_address["id"]  # Use the fixed ID from addresses.json
                            else:
                                ship_address_id = bill_address_id
                    else:
                        bill_address_id = None
                        ship_address_id = None
                else:
                    bill_address_id = None
                    ship_address_id = None

            state = random.choices(population=list(order_states.keys()), weights=list(order_states.values()), k=1)[0]

            created_dt = fake.date_time_between(start_date="-1y", end_date="now")
            created_at = created_dt
            updated_dt = fake.date_time_between(start_date=created_dt, end_date="now")
            updated_at = updated_dt

            # Generate order items and calculate totals
            item_count = random.randint(1, 5)  # 1-5 items per order

            # Create a random mix of products (1-5 items per order)
            selected_products = random.sample(products, min(item_count, len(products)))

            # Calculate order totals
            item_total = round(sum(p["master_price"] for p in selected_products), 2)

            # Apply random adjustments
            adjustment_total = 0.0
            shipment_total = 0.0
            additional_tax_total = 0.0
            promo_total = 0.0
            included_tax_total = 0.0

            # For completed orders, add shipping costs and taxes
            if state == "complete":
                shipment_total = round(random.uniform(5.99, 15.99), 2)

                # Sometimes apply tax
                if random.random() < 0.8:  # 80% chance of having tax
                    tax_rate = random.uniform(0.05, 0.1)  # 5-10% tax
                    additional_tax_total = round(item_total * tax_rate, 2)

                # Sometimes apply promo discount
                if random.random() < 0.3:  # 30% chance of having promotion
                    promo_rate = random.uniform(0.05, 0.2)  # 5-20% discount
                    promo_total = round(-item_total * promo_rate, 2)  # Negative value for discount

            # Calculate final total
            total = round(item_total + shipment_total + additional_tax_total + promo_total, 2)

            # Set payment and shipment states based on order state
            payment_state = None
            shipment_state = None
            payment_total = 0.0
            completed_at = None

            if state == "complete":
                completed_at = updated_at  # Already a datetime object
                payment_state = random.choices(population=list(payment_states.keys()), weights=list(payment_states.values()), k=1)[0]

                # Set shipment state based on payment state and order state
                if state == "canceled":
                    shipment_state = "canceled"
                elif state in ["awaiting_return", "returned"]:
                    # For returns, shipment should have been shipped first
                    shipment_state = "shipped"
                elif payment_state in ["balance_due", "void", "failed"]:
                    # Don't ship unpaid orders
                    shipment_options = ["pending", "ready", "canceled", "backorder"]
                    shipment_weights = [40, 30, 20, 10]  # Higher chance of pending/ready for unpaid
                    shipment_state = random.choices(population=shipment_options, weights=shipment_weights, k=1)[0]
                else:
                    # For paid orders, use the standard distribution
                    shipment_state = random.choices(population=list(shipment_states.keys()), weights=list(shipment_states.values()), k=1)[0]

                if payment_state == "paid":
                    payment_total = total
                elif payment_state == "balance_due":
                    payment_total = round(total * random.uniform(0, 0.9), 2)  # Partial payment

            # Generate other fields
            token = generate_order_token()

            # Approval data
            needs_approval = random.random() < 0.05  # 5% orders need approval
            approver_id = None
            approved_at = None

            if needs_approval and state == "complete":
                # Select a random admin user (is_customer = false) as approver
                admin_users = [user for user in all_users if not user.get("is_customer", False)]
                if admin_users:
                    admin_user = random.choice(admin_users)
                    approver_id = admin_user["id"]
                else:
                    # Fallback if no admin users found
                    approver_id = random.randint(1, 10)

                approved_at = fake.date_time_between(start_date=created_dt, end_date=updated_dt)

            # Cancellation data
            is_canceled = random.random() < 0.08  # 8% of orders are canceled
            canceled_at = None
            canceler_id = None

            if is_canceled:
                state = "canceled"
                payment_state = "void"
                shipment_state = "canceled"
                canceled_at = fake.date_time_between(start_date=created_dt, end_date=updated_dt)

                # 70% chance it's canceled by the user, 30% by an admin
                if random.random() < 0.7:
                    canceler_id = user_id  # Canceled by the user who placed the order
                else:
                    # Select a random admin for admin-canceled orders
                    admin_users = [user for user in all_users if not user.get("is_customer", False)]
                    if admin_users:
                        admin_user = random.choice(admin_users)
                        canceler_id = admin_user["id"]
                    else:
                        # Fallback if no admin users found
                        canceler_id = random.randint(1, 10)

            # Generate special instructions (occasionally)
            special_instructions = None
            if random.random() < 0.15:  # 15% chance of special instructions
                instructions = [
                    "Please leave package at the front door.",
                    "Call upon arrival.",
                    "Ring doorbell twice.",
                    "Please gift wrap if possible.",
                    "Fragile items, handle with care.",
                    "No substitutions please.",
                    "Ring doorbell and leave package.",
                    "Deliver to back door.",
                    "Text before delivery.",
                    "Please do not bend package.",
                ]
                special_instructions = random.choice(instructions)

            # Create internal note (rarely)
            internal_note = None
            if random.random() < 0.08:  # 8% chance of internal note
                notes = [
                    "Customer is a VIP.",
                    "Customer complained about previous delivery.",
                    "Priority shipping requested.",
                    "Follow up needed after delivery.",
                    "Customer requested specific delivery date.",
                    "Customer has returned multiple items previously.",
                    "Address was difficult to find last time.",
                    "Customer made special packaging requests.",
                    "Frequent buyer, consider adding loyalty discount.",
                    "Business address, deliver during business hours.",
                ]
                internal_note = random.choice(notes)

            # Create order object with datetime values converted to strings
            # Convert datetime fields to ISO format strings for JSON serialization
            completed_at_str = completed_at.isoformat() if completed_at else None
            created_at_str = created_at.isoformat() if created_at else None
            updated_at_str = updated_at.isoformat() if updated_at else None
            approved_at_str = approved_at.isoformat() if approved_at else None
            canceled_at_str = canceled_at.isoformat() if canceled_at else None

            order = Order(
                id=i,
                number=generate_order_number(),
                item_total=item_total,
                total=total,
                state=state,
                adjustment_total=adjustment_total,
                user_id=user_id,
                completed_at=completed_at_str,
                bill_address_id=bill_address_id,
                ship_address_id=ship_address_id,
                payment_total=payment_total,
                shipment_state=shipment_state,
                payment_state=payment_state,
                email=email,
                special_instructions=special_instructions,
                created_at=created_at_str,
                updated_at=updated_at_str,
                currency="USD",
                last_ip_address=fake.ipv4() if random.random() < 0.8 else None,
                created_by_id=created_by_id,
                shipment_total=shipment_total,
                additional_tax_total=additional_tax_total,
                promo_total=promo_total,
                channel="spree",
                included_tax_total=included_tax_total,
                item_count=item_count,
                approver_id=approver_id,
                approved_at=approved_at_str,
                confirmation_delivered=(state == "complete"),
                considered_risky=random.random() < 0.20,  # 20% are considered risky
                token=token,
                canceled_at=canceled_at_str,
                canceler_id=canceler_id,
                store_id=1,
                state_lock_version=0,
                taxable_adjustment_total=0.0,
                non_taxable_adjustment_total=0.0,
                store_owner_notification_delivered=(state == "complete"),
                public_metadata=None,
                private_metadata=None,
                internal_note=internal_note,
            )

            orders_list.append(order.model_dump())

        # Save to file
        orders_dict = {"orders": orders_list}

        settings.DATA_PATH.mkdir(parents=True, exist_ok=True)
        ORDERS_FILE.parent.mkdir(parents=True, exist_ok=True)
        with ORDERS_FILE.open("w", encoding="utf-8") as f:
            json.dump(orders_dict, f, indent=2, ensure_ascii=False)

        logger.succeed(f"Successfully generated and saved {number_of_orders} orders to {ORDERS_FILE}")

        # Generate line items for the orders
        logger.info("Generating line items for orders...")
        from apps.spree.libs.orders.line_items import generate_line_items

        await generate_line_items(orders_list, products)

        # Generate shipments for the orders
        logger.info("Generating shipments for orders...")
        from apps.spree.libs.orders.shipments import generate_shipments

        await generate_shipments(orders_list)

        # Generate state changes for orders and shipments
        logger.info("Generating state changes...")
        from apps.spree.libs.orders.states import generate_state_changes

        await generate_state_changes(orders_list)

        return orders_dict

    except Exception as e:
        logger.error(f"Error generating orders: {e}")
        raise


async def seed_orders():
    """Insert orders into the database."""

    logger.start("Inserting orders into spree_orders table...")

    try:
        # Load orders from JSON file
        if not ORDERS_FILE.exists():
            logger.error(f"Orders file not found at {ORDERS_FILE}. Run generate command first.")
            raise FileNotFoundError("Orders file not found")

        with ORDERS_FILE.open(encoding="utf-8") as f:
            data = json.load(f)

        orders = data.get("orders", [])
        logger.info(f"Loaded {len(orders)} orders from {ORDERS_FILE}")

        # Get user mapping from database to verify against fixed IDs
        user_map = {}
        user_records = await db_client.fetch("SELECT id, email FROM spree_users")
        for user in user_records:
            user_map[user["id"]] = user["email"]

        # Also map by email for lookup
        user_email_map = {}
        for user in user_records:
            user_email_map[user["email"]] = user["id"]

        # Load original users data to check is_customer status
        with USERS_FILE.open(encoding="utf-8") as f:
            users_data = json.load(f)
            all_users = users_data.get("users", [])

        # Create a map of user IDs to is_customer status
        customer_status_map = {user["id"]: user.get("is_customer", False) for user in all_users}

        # Log how many customer users we have
        customer_count = sum(1 for is_customer in customer_status_map.values() if is_customer)
        logger.info(f"Found {customer_count} customer users out of {len(customer_status_map)} total users")

        # Get address mapping from database to verify against fixed IDs
        address_map = {}
        address_records = await db_client.fetch("SELECT id FROM spree_addresses")
        for address in address_records:
            address_map[address["id"]] = True

        # Insert orders
        inserted_count = 0
        for order in orders:
            try:
                # Use the fixed user ID from the order, but verify it exists in the database and is a customer
                if order["user_id"] in user_map and customer_status_map.get(order["user_id"], False):
                    # Keep the user_id as is, using the fixed ID
                    order["created_by_id"] = order["user_id"]
                elif order["email"] in user_email_map:
                    # If email matches but ID doesn't, update the ID and check customer status
                    new_user_id = user_email_map[order["email"]]
                    if customer_status_map.get(new_user_id, False):
                        order["user_id"] = new_user_id
                        order["created_by_id"] = order["user_id"]
                    else:
                        # User exists but is not a customer, make it a guest order
                        logger.warning(f"User ID {new_user_id} is not a customer for order {order['number']}, treating as guest order")
                        order["user_id"] = None
                        order["created_by_id"] = None
                else:
                    # User doesn't exist in DB or is not a customer, make it a guest order
                    # logger.debug(f"User ID not found in database or is not a customer for order {order['number']}, treating as guest order")
                    order["user_id"] = None
                    order["created_by_id"] = None

                # Handle addresses for both regular and guest orders
                # If bill_address_id is negative, it's a guest order address that needs to be created
                if order["bill_address_id"] and order["bill_address_id"] < 0:
                    # Generate a new address for guest order
                    # Make sure created_at and updated_at are datetime objects
                    if isinstance(order["created_at"], str):
                        try:
                            created_time = datetime.fromisoformat(order["created_at"])
                        except ValueError:
                            try:
                                created_time = datetime.strptime(order["created_at"], "%Y-%m-%dT%H:%M:%S.%f")
                            except ValueError:
                                created_time = datetime.now()
                                logger.warning(f"Could not parse created_at date for order {order['number']}, using current time")
                    else:
                        created_time = order["created_at"]

                    if isinstance(order["updated_at"], str):
                        try:
                            updated_time = datetime.fromisoformat(order["updated_at"])
                        except ValueError:
                            try:
                                updated_time = datetime.strptime(order["updated_at"], "%Y-%m-%dT%H:%M:%S.%f")
                            except ValueError:
                                updated_time = datetime.now()
                                logger.warning(f"Could not parse updated_at date for order {order['number']}, using current time")
                    else:
                        updated_time = order["updated_at"]
                    bill_address = {
                        "firstname": fake.first_name(),
                        "lastname": fake.last_name(),
                        "address1": fake.street_address(),
                        "address2": fake.secondary_address() if random.random() < 0.3 else None,
                        "city": fake.city(),
                        "zipcode": fake.zipcode(),
                        "phone": fake.phone_number(),
                        "state_name": fake.state(),
                        "country_id": 232,  # USA
                        "company": fake.company() if random.random() < 0.2 else None,
                        "alternative_phone": fake.phone_number() if random.random() < 0.1 else None,
                        "created_at": created_time,
                        "updated_at": updated_time,
                    }

                    # Insert address and get ID
                    bill_address_result = await db_client.fetchval(
                        """
                        INSERT INTO spree_addresses (
                            firstname, lastname, address1, address2, city, zipcode, phone,
                            state_name, country_id, company, alternative_phone, created_at, updated_at
                        ) VALUES (
                            $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13
                        ) RETURNING id
                        """,
                        bill_address["firstname"],
                        bill_address["lastname"],
                        bill_address["address1"],
                        bill_address["address2"],
                        bill_address["city"],
                        bill_address["zipcode"],
                        bill_address["phone"],
                        bill_address["state_name"],
                        bill_address["country_id"],
                        bill_address["company"],
                        bill_address["alternative_phone"],
                        created_time,
                        updated_time,
                    )

                    # Update order with real address ID
                    order["bill_address_id"] = bill_address_result
                    # logger.info(f"Created guest billing address ID {bill_address_result} for order {order['number']}")

                # For regular users, verify billing address exists
                elif order["bill_address_id"] and order["bill_address_id"] not in address_map:
                    logger.warning(f"Billing address ID {order['bill_address_id']} not found in database for order {order['number']}, setting to NULL")
                    order["bill_address_id"] = None
                elif order["bill_address_id"] and order["bill_address_id"] > 0:
                    pass
                    # logger.debug(f"Using fixed billing address ID {order['bill_address_id']} for order {order['number']}")

                # Handle shipping address for guest orders
                if order["ship_address_id"] and order["ship_address_id"] < 0:
                    # For guest orders: 70% chance to use same address for shipping
                    if random.random() < 0.7 and order["bill_address_id"]:
                        order["ship_address_id"] = order["bill_address_id"]
                    else:
                        # Generate a different shipping address
                        # Make sure created_at and updated_at are datetime objects
                        if isinstance(order["created_at"], str):
                            try:
                                created_time = datetime.fromisoformat(order["created_at"])
                            except ValueError:
                                try:
                                    created_time = datetime.strptime(order["created_at"], "%Y-%m-%dT%H:%M:%S.%f")
                                except ValueError:
                                    created_time = datetime.now()
                                    logger.warning(f"Could not parse created_at date for order {order['number']}, using current time")
                        else:
                            created_time = order["created_at"]

                        if isinstance(order["updated_at"], str):
                            try:
                                updated_time = datetime.fromisoformat(order["updated_at"])
                            except ValueError:
                                try:
                                    updated_time = datetime.strptime(order["updated_at"], "%Y-%m-%dT%H:%M:%S.%f")
                                except ValueError:
                                    updated_time = datetime.now()
                                    logger.warning(f"Could not parse updated_at date for order {order['number']}, using current time")
                        else:
                            updated_time = order["updated_at"]
                        ship_address = {
                            "firstname": fake.first_name(),
                            "lastname": fake.last_name(),
                            "address1": fake.street_address(),
                            "address2": fake.secondary_address() if random.random() < 0.3 else None,
                            "city": fake.city(),
                            "zipcode": fake.zipcode(),
                            "phone": fake.phone_number(),
                            "state_name": fake.state(),
                            "country_id": 232,  # USA
                            "company": fake.company() if random.random() < 0.2 else None,
                            "alternative_phone": fake.phone_number() if random.random() < 0.1 else None,
                            "created_at": created_time,
                            "updated_at": updated_time,
                        }

                        # Insert address and get ID
                        ship_address_result = await db_client.fetchval(
                            """
                            INSERT INTO spree_addresses (
                                firstname, lastname, address1, address2, city, zipcode, phone,
                                state_name, country_id, company, alternative_phone, created_at, updated_at
                            ) VALUES (
                                $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13
                            ) RETURNING id
                            """,
                            ship_address["firstname"],
                            ship_address["lastname"],
                            ship_address["address1"],
                            ship_address["address2"],
                            ship_address["city"],
                            ship_address["zipcode"],
                            ship_address["phone"],
                            ship_address["state_name"],
                            ship_address["country_id"],
                            ship_address["company"],
                            ship_address["alternative_phone"],
                            created_time,
                            updated_time,
                        )

                        # Update order with real address ID
                        order["ship_address_id"] = ship_address_result
                        # logger.info(f"Created guest shipping address ID {ship_address_result} for order {order['number']}")

                # For regular users, verify shipping address exists
                elif order["ship_address_id"] and order["ship_address_id"] not in address_map:
                    logger.warning(f"Shipping address ID {order['ship_address_id']} not found in database for order {order['number']}, setting to NULL")
                    order["ship_address_id"] = None
                elif order["ship_address_id"] and order["ship_address_id"] > 0:
                    pass
                    # logger.debug(f"Using fixed shipping address ID {order['ship_address_id']} for order {order['number']}")

                # Convert string datetime values to datetime objects
                datetime_fields = ["completed_at", "created_at", "updated_at", "approved_at", "canceled_at"]
                for field in datetime_fields:
                    if order[field]:
                        try:
                            if isinstance(order[field], str):
                                # Parse the ISO format string to datetime object
                                order[field] = datetime.fromisoformat(order[field])
                        except (ValueError, TypeError) as e:
                            try:
                                # Try an alternative format if the first attempt fails
                                order[field] = datetime.strptime(order[field], "%Y-%m-%dT%H:%M:%S.%f")
                            except (ValueError, TypeError) as e2:
                                logger.error(f"Failed to convert {field} value '{order[field]}': {e} / {e2}")
                                order[field] = None

                # Insert order with explicit ID
                await db_client.execute(
                    """
                    INSERT INTO spree_orders (
                        id, number, item_total, total, state, adjustment_total, 
                        user_id, completed_at, bill_address_id, ship_address_id, payment_total,
                        shipment_state, payment_state, email, special_instructions, created_at,
                        updated_at, currency, last_ip_address, created_by_id, shipment_total,
                        additional_tax_total, promo_total, channel, included_tax_total, item_count,
                        approver_id, approved_at, confirmation_delivered, considered_risky, token,
                        canceled_at, canceler_id, store_id, state_lock_version, 
                        taxable_adjustment_total, non_taxable_adjustment_total, 
                        store_owner_notification_delivered, public_metadata, private_metadata, internal_note
                    ) VALUES (
                        $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16,
                        $17, $18, $19, $20, $21, $22, $23, $24, $25, $26, $27, $28, $29, $30, $31,
                        $32, $33, $34, $35, $36, $37, $38, $39, $40, $41
                    )
                    """,
                    order["id"],  # Use the exact ID from JSON data
                    order["number"],
                    order["item_total"],
                    order["total"],
                    order["state"],
                    order["adjustment_total"],
                    order["user_id"],
                    order["completed_at"],
                    order["bill_address_id"],
                    order["ship_address_id"],
                    order["payment_total"],
                    order["shipment_state"],
                    order["payment_state"],
                    order["email"],
                    order["special_instructions"],
                    order["created_at"],
                    order["updated_at"],
                    order["currency"],
                    order["last_ip_address"],
                    order["created_by_id"],
                    order["shipment_total"],
                    order["additional_tax_total"],
                    order["promo_total"],
                    order["channel"],
                    order["included_tax_total"],
                    order["item_count"],
                    order["approver_id"],
                    order["approved_at"],
                    order["confirmation_delivered"],
                    order["considered_risky"],
                    order["token"],
                    order["canceled_at"],
                    order["canceler_id"],
                    order["store_id"],
                    order["state_lock_version"],
                    order["taxable_adjustment_total"],
                    order["non_taxable_adjustment_total"],
                    order["store_owner_notification_delivered"],
                    None,  # public_metadata
                    None,  # private_metadata
                    order["internal_note"],
                )

                inserted_count += 1

            except Exception as e:
                logger.error(f"Failed to insert order {order['number']}: {e}")
                continue

        logger.succeed(f"Successfully inserted {inserted_count} orders into the database")

        # Update the sequence to avoid future conflicts with auto-generated IDs
        if inserted_count > 0:
            max_id = max(order["id"] for order in orders)
            await db_client.execute(f"SELECT setval('spree_orders_id_seq', {max_id}, true)")

        # Now seed line items, shipments and state changes
        from apps.spree.libs.orders.line_items import seed_line_items
        from apps.spree.libs.orders.shipments import seed_shipments
        from apps.spree.libs.orders.states import seed_state_changes

        await seed_line_items()
        await seed_shipments()
        await seed_state_changes()

        # Add addresses for any guest orders without addresses
        await add_addresses_to_guest_orders()

    except Exception as e:
        logger.error(f"Error seeding orders in database: {e}")
        raise


__all__ = [
    "LineItem",
    "Order",
    "Shipment",
    "StateChange",
    "add_addresses_to_guest_orders",
    "generate_line_items",
    "generate_order_number",
    "generate_order_token",
    "generate_orders",
    "generate_shipment_number",
    "generate_shipments",
    "generate_state_changes",
    "seed_line_items",
    "seed_orders",
    "seed_shipments",
    "seed_shipping_rates",
    "seed_state_changes",
]
