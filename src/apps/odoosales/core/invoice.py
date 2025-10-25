import datetime

from faker import Faker

from apps.odoosales.config.constants import SaleModelName
from apps.odoosales.utils.odoo import OdooClient
from common.logger import logger


faker = Faker("en_US")


async def insert_invoices():
    logger.start("Inserting invoices...")

    async with OdooClient() as client:
        orders_to_invoice = await client.search_read(
            SaleModelName.SALE_ORDER.value,
            [("state", "=", "sale"), ("invoice_status", "=", "to invoice")],
            ["id", "name"],
        )

        orders_to_invoice = orders_to_invoice[: int(len(orders_to_invoice) * 0.5)]

        for order in orders_to_invoice:
            try:
                invoice_id = await client.create(
                    "sale.advance.payment.inv",
                    {
                        "advance_payment_method": "delivered",
                        "sale_order_ids": [order["id"]],
                    },
                )
                await client.execute_kw("sale.advance.payment.inv", "create_invoices", [invoice_id])
            except Exception as e:
                logger.warning(f"Failed to create invoice for order {order['name']}: {e}")
                continue

        existing_invoices = await client.search_read(
            "account.move",
            [],
            fields=["id", "name"],
        )

        # Updates invoices for each sale order
        for invoice in existing_invoices:
            try:
                await client.write(
                    "account.move",
                    invoice["id"],
                    {
                        "name": faker.numerify(f"INV/{datetime.date.today().strftime('%Y')}/######"),
                        "invoice_date": faker.date_between(start_date="-1y", end_date="today").strftime("%Y-%m-%d"),
                        "invoice_date_due": faker.date_between(start_date="today", end_date="+30d").strftime("%Y-%m-%d"),
                    },
                )
                await client.execute_kw("account.move", "action_post", [invoice["id"]])

            except Exception as e:
                raise ValueError(f"Skip creating invoice for order {invoice['name']}: {e}")

    logger.succeed(f"Inserted {len(existing_invoices)} invoices")


async def pay_invoices():
    logger.start("Paying invoices...")

    async with OdooClient() as client:
        not_paid_invoices = await client.search_read(
            "account.move",
            [("state", "=", "posted"), ("payment_state", "=", "not_paid")],
            fields=["id", "name"],
        )

        # journal = await client.search_read(
        #     "account.journal",
        #     [("name", "=", "Bank")],
        #     fields=["id"],
        # )

        not_paid_invoices = not_paid_invoices[: int(len(not_paid_invoices) * 0.5)]

        for invoice in not_paid_invoices:
            try:
                # lines = await client.search_read(
                #     "account.move.line",
                #     [("move_id", "=", invoice["id"])],
                #     fields=["id"],
                # )
                # await client.execute_kw("account.move", "action_register_payment", [invoice["id"]])
                # register_id = await client.create(
                #     "account.payment.register",
                #     {
                #         "journal_id": journal[0]["id"],
                #         "payment_date": datetime.date.today().strftime("%Y-%m-%d"),
                #         "line_ids": [
                #             [6, 0, [line["id"] for line in lines]],
                #         ],
                #         "can_edit_wizard": True,
                #     },
                # )
                # await client.execute_kw("account.payment.register", "action_create_payments", [register_id])
                await client.write(
                    "account.move",
                    invoice["id"],
                    {"payment_state": "paid"},
                )
            except Exception as e:
                logger.warning(f"Failed to pay invoice {invoice['name']}: {e}")
                continue

    logger.succeed("Finished paying invoices.")
