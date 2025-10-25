"""Line item model and related functionality."""

import json
import random
from datetime import datetime

from faker import Faker
from pydantic import BaseModel

from apps.spree.config.settings import settings
from apps.spree.utils.constants import LINE_ITEMS_FILE, ORDERS_FILE, PRODUCTS_FILE
from apps.spree.utils.database import db_client
from common.logger import Logger


logger = Logger()
fake = Faker()


class LineItem(BaseModel):
    """Individual line item model for orders."""

    id: int  # noqa: A003, RUF100
    variant_id: int
    order_id: int
    quantity: int
    price: float
    created_at: str
    updated_at: str
    currency: str
    cost_price: float | None
    tax_category_id: int | None
    adjustment_total: float = 0.0
    additional_tax_total: float = 0.0
    promo_total: float = 0.0
    included_tax_total: float = 0.0
    pre_tax_amount: float = 0.0
    taxable_adjustment_total: float = 0.0
    non_taxable_adjustment_total: float = 0.0
    public_metadata: dict | None = None
    private_metadata: dict | None = None


async def generate_line_items(orders_list=None, products_list=None):
    """Generate line items for existing orders."""
    logger.info("Generating line items...")

    try:
        # If orders_list is not provided, load from file
        if not orders_list:
            if not ORDERS_FILE.exists():
                logger.error(f"Orders file not found at {ORDERS_FILE}. Run generate orders command first.")
                return None

            with ORDERS_FILE.open(encoding="utf-8") as f:
                orders_data = json.load(f)
                orders_list = orders_data.get("orders", [])

        # If products_list is not provided, load from file
        if not products_list:
            if not PRODUCTS_FILE.exists():
                logger.error(f"Products file not found at {PRODUCTS_FILE}. Run generate products command first.")
                return None

            with PRODUCTS_FILE.open(encoding="utf-8") as f:
                products_data = json.load(f)
                products_list = products_data.get("products", [])

        if not products_list:
            logger.error("No products found in products data.")
            return None

        if not orders_list:
            logger.error("No orders found in orders data.")
            return None

        logger.info(f"Loaded {len(orders_list)} orders and {len(products_list)} products for line item generation.")

        # Create list for all line items
        line_items_list = []
        line_item_id = 1

        for order in orders_list:
            # Get the number of items for this order
            item_count = order.get("item_count", random.randint(1, 5))

            # Randomly select products for this order
            selected_products = random.sample(products_list, min(item_count, len(products_list)))

            # We'll calculate the actual totals from the line items rather than using the order total
            line_items_total = 0.0

            for product in selected_products:
                # Get variant ID from product (assuming master variant ID)
                variant_id = product.get("master_id", product.get("id"))

                # Determine quantity (1-3 items per line item)
                quantity = random.randint(1, 3)

                # Calculate price based on product master price
                unit_price = product.get("master_price", random.uniform(10.0, 100.0))

                # Calculate the item price total based on unit price and quantity
                item_price_total = round(unit_price * quantity, 2)
                line_items_total += item_price_total

                # Calculate tax and promo adjustments
                additional_tax_total = 0.0
                promo_total = 0.0

                if order.get("state") == "complete":
                    # Sometimes apply tax to line item
                    if random.random() < 0.8:  # 80% chance
                        tax_rate = random.uniform(0.05, 0.1)  # 5-10% tax
                        additional_tax_total = round(item_price_total * tax_rate, 2)

                    # Sometimes apply promo to line item
                    if random.random() < 0.3:  # 30% chance
                        promo_rate = random.uniform(0.05, 0.2)  # 5-20% discount
                        promo_total = round(-item_price_total * promo_rate, 2)  # Negative value

                # Create timestamps (use same timestamps as order)
                created_at = order["created_at"]
                updated_at = order["updated_at"]

                # Create line item
                line_item = LineItem(
                    id=line_item_id,
                    variant_id=variant_id,
                    order_id=order["id"],
                    quantity=quantity,
                    price=unit_price,
                    created_at=created_at,
                    updated_at=updated_at,
                    currency=order.get("currency", "USD"),
                    cost_price=round(unit_price * 0.6, 2),  # 60% of price as cost
                    tax_category_id=random.randint(1, 3) if random.random() < 0.8 else None,
                    adjustment_total=round(additional_tax_total + promo_total, 2),
                    additional_tax_total=additional_tax_total,
                    promo_total=promo_total,
                    included_tax_total=0.0,
                    pre_tax_amount=round(item_price_total, 4),
                    taxable_adjustment_total=0.0,
                    non_taxable_adjustment_total=0.0,
                )

                line_items_list.append(line_item.model_dump())
                line_item_id += 1

            # Update the order's item_total and total with the actual sum from line items
            order["item_total"] = line_items_total

            # Recalculate the total based on item_total and other adjustments
            shipment_total = order.get("shipment_total", 0.0)
            additional_tax_total = order.get("additional_tax_total", 0.0)
            promo_total = order.get("promo_total", 0.0)
            order["total"] = round(line_items_total + shipment_total + additional_tax_total + promo_total, 2)

        # Save line items to file
        line_items_dict = {"line_items": line_items_list}

        settings.DATA_PATH.mkdir(parents=True, exist_ok=True)
        LINE_ITEMS_FILE.parent.mkdir(parents=True, exist_ok=True)
        with LINE_ITEMS_FILE.open("w", encoding="utf-8") as f:
            json.dump(line_items_dict, f, indent=2, ensure_ascii=False)

        # Update orders file with corrected totals
        orders_dict = {"orders": orders_list}
        with ORDERS_FILE.open("w", encoding="utf-8") as f:
            json.dump(orders_dict, f, indent=2, ensure_ascii=False)

        logger.succeed(f"Successfully generated and saved {len(line_items_list)} line items to {LINE_ITEMS_FILE}")
        return line_items_dict

    except Exception as e:
        logger.error(f"Error generating line items: {e}")
        raise


async def seed_line_items():
    """Insert line items into the database."""
    logger.start("Inserting line items into spree_line_items table...")

    try:
        # Load line items from JSON file
        if not LINE_ITEMS_FILE.exists():
            logger.error(f"Line items file not found at {LINE_ITEMS_FILE}. Run generate command first.")
            raise FileNotFoundError("Line items file not found")

        with LINE_ITEMS_FILE.open(encoding="utf-8") as f:
            data = json.load(f)

        line_items = data.get("line_items", [])
        logger.info(f"Loaded {len(line_items)} line items from {LINE_ITEMS_FILE}")

        # Get actual order IDs from database
        order_map = {}
        order_records = await db_client.fetch("SELECT id FROM spree_orders")
        for order in order_records:
            order_map[order["id"]] = order["id"]

        # Get actual variant IDs from database
        variant_map = {}
        variant_records = await db_client.fetch("SELECT id FROM spree_variants")
        for i, variant in enumerate(variant_records):
            variant_map[i + 1] = variant["id"]  # Map generated IDs to actual DB IDs

        # Insert line items
        inserted_count = 0
        for line_item in line_items:
            try:
                # Update IDs based on actual database records
                if line_item["order_id"] in order_map:
                    line_item["order_id"] = order_map[line_item["order_id"]]
                else:
                    logger.warning(f"Order ID {line_item['order_id']} not found in database, skipping line item")
                    continue

                # Map variant ID if possible
                if line_item["variant_id"] in variant_map:
                    line_item["variant_id"] = variant_map[line_item["variant_id"]]

                # Convert datetime strings to actual datetime objects
                if isinstance(line_item["created_at"], str):
                    line_item["created_at"] = datetime.fromisoformat(line_item["created_at"])
                if isinstance(line_item["updated_at"], str):
                    line_item["updated_at"] = datetime.fromisoformat(line_item["updated_at"])

                # Insert line item
                await db_client.execute(
                    """
                    INSERT INTO spree_line_items (
                        variant_id, order_id, quantity, price, created_at, updated_at,
                        currency, cost_price, tax_category_id, adjustment_total,
                        additional_tax_total, promo_total, included_tax_total,
                        pre_tax_amount, taxable_adjustment_total, 
                        non_taxable_adjustment_total, public_metadata, private_metadata
                    ) VALUES (
                        $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, 
                        $11, $12, $13, $14, $15, $16, $17, $18
                    )
                    """,
                    line_item["variant_id"],
                    line_item["order_id"],
                    line_item["quantity"],
                    line_item["price"],
                    line_item["created_at"],
                    line_item["updated_at"],
                    line_item["currency"],
                    line_item["cost_price"],
                    line_item["tax_category_id"],
                    line_item["adjustment_total"],
                    line_item["additional_tax_total"],
                    line_item["promo_total"],
                    line_item["included_tax_total"],
                    line_item["pre_tax_amount"],
                    line_item["taxable_adjustment_total"],
                    line_item["non_taxable_adjustment_total"],
                    None,  # public_metadata
                    None,  # private_metadata
                )

                inserted_count += 1

            except Exception as e:
                logger.error(f"Failed to insert line item {line_item.get('id')}: {e}")
                continue

        logger.succeed(f"Successfully inserted {inserted_count} line items into the database")

    except Exception as e:
        logger.error(f"Error seeding line items in database: {e}")
        raise
