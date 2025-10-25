"""Guest order management functions."""

import json
import random
from datetime import datetime

from faker import Faker

from apps.spree.utils.constants import ORDERS_FILE
from apps.spree.utils.database import db_client
from common.logger import Logger


logger = Logger()
fake = Faker()


async def add_addresses_to_guest_orders():
    """Find guest orders without addresses and add them."""
    logger.info("Checking for guest orders that need addresses...")

    try:
        # Find guest orders without addresses
        guest_orders = await db_client.fetch(
            """
            SELECT id, number, email, created_at, updated_at 
            FROM spree_orders 
            WHERE user_id IS NULL 
            AND (bill_address_id IS NULL OR ship_address_id IS NULL)
        """
        )

        if not guest_orders:
            logger.info("No guest orders without addresses found")
            return

        logger.info(f"Found {len(guest_orders)} guest orders that need addresses")

        for order in guest_orders:
            logger.info(f"Adding addresses for guest order #{order['number']} (ID: {order['id']})")

            # Convert datetime strings to objects if needed
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

            # Generate an address for the guest order
            guest_address = {
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
                "user_id": None,
                "deleted_at": None,
                "label": None,
                "public_metadata": None,
                "private_metadata": None,
            }

            # Insert the address and get its ID
            address_id = await db_client.fetchval(
                """
                INSERT INTO spree_addresses (
                    firstname, lastname, address1, address2, city, zipcode, phone,
                    state_name, alternative_phone, company, country_id,
                    created_at, updated_at, user_id, deleted_at, label, 
                    public_metadata, private_metadata
                ) VALUES (
                    $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11,
                    $12, $13, $14, $15, $16, $17, $18
                ) RETURNING id
                """,
                guest_address["firstname"],
                guest_address["lastname"],
                guest_address["address1"],
                guest_address["address2"],
                guest_address["city"],
                guest_address["zipcode"],
                guest_address["phone"],
                guest_address["state_name"],
                guest_address["alternative_phone"],
                guest_address["company"],
                guest_address["country_id"],
                guest_address["created_at"],
                guest_address["updated_at"],
                guest_address["user_id"],
                guest_address["deleted_at"],
                guest_address["label"],
                guest_address["public_metadata"],
                guest_address["private_metadata"],
            )

            if not address_id:
                logger.error(f"Failed to insert address for guest order #{order['number']}")
                continue

            logger.info(f"Created address with ID: {address_id} for guest order #{order['number']}")

            # Update the order with the new address IDs
            await db_client.execute(
                """
                UPDATE spree_orders 
                SET bill_address_id = $1, ship_address_id = $1
                WHERE id = $2
                """,
                address_id,
                order["id"],
            )

            logger.succeed(f"Successfully updated guest order #{order['number']} with address ID: {address_id}")

            # Also update the JSON file for consistency
            if ORDERS_FILE.exists():
                with ORDERS_FILE.open("r", encoding="utf-8") as f:
                    orders_data = json.load(f)

                for order_data in orders_data.get("orders", []):
                    if order_data.get("email") == order["email"]:
                        order_data["bill_address_id"] = address_id
                        order_data["ship_address_id"] = address_id
                        break

                with ORDERS_FILE.open("w", encoding="utf-8") as f:
                    json.dump(orders_data, f, indent=2, ensure_ascii=False)

    except Exception as e:
        logger.error(f"Error adding addresses for guest orders: {e}")
        # We'll continue with other operations even if this fails
