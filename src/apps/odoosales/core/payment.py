from apps.odoosales.utils.odoo import OdooClient
from common.logger import logger


async def insert_payment_methods():
    """
    Create payment methods for cash, card, and gift card and link them to appropriate accounting journals.
    """
    payment_methods_data = [
        {
            "name": "Credit Card",
            "journal_name": "Bank (POS)",
            "journal_type": "credit",  # Assuming 'credit' for bank journal
        },
        {
            "name": "Gift Card",
            "journal_name": "Miscellaneous",
            "journal_type": "general",  # Assuming 'general' for miscellaneous journal
        },
    ]

    logger.start("Creating/updating payment methods and journals...")
    try:
        async with OdooClient() as client:
            for method in payment_methods_data:
                # First, ensure the journal exists or create it
                journal_id = await client.create(
                    "account.journal",
                    {
                        "name": method["journal_name"],
                        "type": method["journal_type"],
                        "code": method["journal_name"][:5].upper(),  # Simple code generation
                    },
                )

                # Then, create or update the payment method and link it to the journal
                await client.create(
                    "pos.payment.method",
                    {
                        "name": method["name"],
                        "journal_id": journal_id,
                        "config_ids": [1],
                    },
                )
            logger.succeed("Payment methods and linked journals created/updated successfully.")
    except Exception as e:
        logger.fail(f"Failed to create/update payment methods and journals: {e}")


async def create_pos_order_payments(orders: list):
    """
    Create payment entries for all POS orders.
    """
    async with OdooClient() as client:
        try:
            for order in orders:
                # Get payment method id
                payment_method_id = await client.search_read("pos.payment.method", [("name", "=", order["payment"])], ["id"])

                if not payment_method_id:
                    logger.warning(f"Payment method {order['payment']} not found for order {order['order_number']}. Skipping payment creation.")
                    continue

                payment_method_id = payment_method_id[0]["id"]

                payment_data = {
                    "pos_order_id": order["order_id"],
                    "payment_method_id": payment_method_id,
                    "amount": order["amount"],
                    "payment_date": order["date"],  # Ensure date is in 'YYYY-MM-DD HH:MM:SS' format
                }
                await client.create("pos.payment", payment_data)
        except Exception as e:
            logger.warning(f"Failed to create POS order payments: {e}")
