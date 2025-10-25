import random

from apps.odoosales.config.constants import SaleModelName, StockModelName
from apps.odoosales.utils.faker import faker
from apps.odoosales.utils.odoo import OdooClient
from common.logger import logger


async def insert_orders():
    logger.start("Creating sales orders...")
    try:
        async with OdooClient() as client:
            quotations = await client.search_read(
                SaleModelName.SALE_ORDER.value,
                [("state", "=", "draft"), ("invoice_status", "=", "no")],
                ["id"],
            )

            orders_count = len(quotations) // 2
            confirmed_count = 0
            for quotation in quotations[:orders_count]:
                try:
                    await client.execute_kw(
                        SaleModelName.SALE_ORDER.value,
                        "action_confirm",
                        [quotation["id"]],
                    )
                    confirmed_count += 1
                except Exception:
                    continue
            logger.succeed(f"Confirmed {confirmed_count} quotations as sales orders.")

            orders = await client.search_read(
                SaleModelName.SALE_ORDER.value,
                [("state", "=", "sale")],
                ["id", "name"],
            )

            for order in orders:
                await client.write(
                    SaleModelName.SALE_ORDER.value,
                    order["id"],
                    {
                        "date_order": faker.date_between(start_date="-1y", end_date="today").strftime("%Y-%m-%d %H:%M:%S"),
                    },
                )

    except Exception as e:
        raise ValueError(f"Error creating sales orders: {e}")


async def insert_orders_to_upsell():
    logger.start("Creating upsell orders...")
    try:
        async with OdooClient() as client:
            orders = await client.search_read(
                SaleModelName.SALE_ORDER.value,
                [("state", "=", "sale"), ("invoice_status", "=", "to invoice")],
                ["id", "name"],
            )

            upsell_orders_count = len(orders) // 4

            for i, order in enumerate(orders[:upsell_orders_count]):
                picking = await client.search_read(
                    StockModelName.STOCK_PICKING.value,
                    [("sale_id", "=", order["id"])],
                    ["id"],
                )
                moves = await client.search_read(
                    StockModelName.STOCK_MOVE.value,
                    [("picking_id", "=", picking[0]["id"])],
                    ["id", "product_id", "product_qty"],
                )
                random_move = random.choice(moves)

                await client.write(
                    StockModelName.STOCK_MOVE.value,
                    random_move["id"],
                    {
                        "quantity": random_move["product_qty"] + random.randint(1, 5),
                    },
                )

                await client.execute_kw(StockModelName.STOCK_PICKING.value, "button_validate", [picking[0]["id"]])

                if i == 0:
                    confirmed_stock_sms_id = await client.create("confirm.stock.sms", {"pick_ids": [picking[0]["id"]]})

                    await client.execute_kw("confirm.stock.sms", "send_sms", [confirmed_stock_sms_id])

                invoice_id = await client.create(
                    "sale.advance.payment.inv",
                    {
                        "advance_payment_method": "delivered",
                        "sale_order_ids": [order["id"]],
                    },
                )
                await client.execute_kw("sale.advance.payment.inv", "create_invoices", [invoice_id])
        logger.succeed(f"Inserted {upsell_orders_count} upsell orders successfully.")

    except Exception as e:
        raise ValueError(f"Error creating upsell orders: {e}")
