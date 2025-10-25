import asyncio  # Added asyncio
import datetime
import random

from faker import Faker

from apps.odoosales.utils.odoo import OdooClient
from common.logger import logger


fake = Faker()


async def insert_pos_refunds():
    logger.start("Inserting POS refunds...")
    async with OdooClient() as client:
        try:
            orders_to_refund_data = await client.search_read(
                "pos.order",
                [("state", "in", ["paid", "done"])],
                [
                    "id",
                    "name",
                    "session_id",
                    "date_order",
                    "lines",
                    "payment_ids",
                    "amount_total",
                    "partner_id",  # Added partner_id,
                    "user_id",  # Added user_id to link to the user who created the order
                    "employee_id",
                ],
            )

            num_refunds = int(len(orders_to_refund_data) * 0.2)  # Refund 10% of orders

            if not orders_to_refund_data:
                logger.fail("No suitable POS orders found to refund.")
                return

            refund_count = 0
            created_refund_details = []

            for order_data in orders_to_refund_data:
                if refund_count >= num_refunds:
                    break

                order_id = order_data["id"]
                order_name = order_data["name"]
                order_lines_ids = order_data.get("lines", [])

                if not order_lines_ids:
                    logger.warning(f"Order {order_name} (ID: {order_id}) has no lines, skipping refund.")
                    continue

                chosen_line_id = random.choice(order_lines_ids)
                # Use search_read with a correct domain for a single ID
                line_details_list = await client.search_read(
                    "pos.order.line",
                    [("id", "=", chosen_line_id)],  # Correct domain
                    [
                        "product_id",
                        "qty",
                        "price_subtotal_incl",
                        "price_unit",
                        "discount",
                    ],  # Added price_unit, discount
                    limit=1,
                )
                if not line_details_list:
                    logger.warning(f"Could not fetch line details for line ID {chosen_line_id}. Skipping.")
                    continue
                line_details = line_details_list[0]  # search_read returns a list

                product_name = line_details["product_id"][1]

                # Ensure qty is treated as int/float before random.randint
                original_qty = float(line_details.get("qty", 0))
                if original_qty < 1:
                    logger.warning(f"Line ID {chosen_line_id} has quantity {original_qty}. Skipping refund for this line.")
                    continue
                qty_to_refund = random.randint(1, int(original_qty))

                # More precise refund amount calculation for the line
                price_unit = float(line_details.get("price_unit", 0))
                discount = float(line_details.get("discount", 0))
                # Assuming price_subtotal_incl was correctly calculated with tax.
                # For simplicity, we'll use price_unit and discount to recalculate line subtotal before tax.
                # This part can be complex depending on how taxes are applied (included/excluded in price_unit).
                # Let's assume price_unit is tax-excluded for this calculation.
                # This is a rough estimate, as tax calculation can be complex.
                # For simplicity, let's assume the proportion of refund amount is similar to qty proportion from price_subtotal_incl
                refund_amount_for_line = (float(line_details["price_subtotal_incl"]) / original_qty) * qty_to_refund
                refund_amount_for_line = round(refund_amount_for_line, 2)

                try:
                    original_session_id = order_data["session_id"][0] if order_data.get("session_id") else None
                    if not original_session_id:
                        logger.warning(f"Order {order_name} has no session_id. Skipping.")
                        continue

                    partner_id_val = order_data.get("partner_id")
                    partner_id_for_refund = partner_id_val[0] if partner_id_val else False

                    refund_order_name = f"R/{order_name}"
                    refund_order_data = {
                        "name": refund_order_name,
                        "pos_reference": refund_order_name,
                        "session_id": original_session_id,
                        "date_order": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        "partner_id": partner_id_for_refund,
                        "user_id": order_data.get("user_id", [False])[0],  # Use user_id from original order
                        "employee_id": order_data.get("employee_id", [False])[0],  # Assuming user_id is the employee
                        "amount_total": -abs(refund_amount_for_line),
                        "amount_paid": 0,
                        "amount_tax": 0,  # Simplified
                        "amount_return": 0,
                        "refunded_order_id": order_id,  # Assuming this field exists to link back to the original order
                        "lines": [
                            (
                                0,
                                0,
                                {
                                    "product_id": line_details["product_id"][0],
                                    "qty": -qty_to_refund,
                                    "price_unit": price_unit,
                                    "discount": discount,
                                    "price_subtotal": round(
                                        -qty_to_refund * price_unit * (1 - (discount / 100)),
                                        2,
                                    ),
                                    "price_subtotal_incl": -refund_amount_for_line,  # Derived from original line's price_subtotal_incl
                                },
                            )
                        ],
                        # "is_refunded": True, # Not a standard field
                    }

                    refund_order_id = await client.create("pos.order", refund_order_data)

                    if order_data.get("payment_ids"):
                        original_payment_id = order_data["payment_ids"][0]
                        payment_detail_list = await client.search_read(
                            "pos.payment",
                            [("id", "=", original_payment_id)],  # Correct domain
                            ["payment_method_id"],
                            limit=1,
                        )
                        if payment_detail_list:
                            payment_detail = payment_detail_list[0]
                            original_payment_method_id = payment_detail["payment_method_id"][0]

                            refund_payment_data = {
                                "pos_order_id": refund_order_id,
                                "payment_method_id": original_payment_method_id,
                                "amount": -abs(refund_amount_for_line),
                                "payment_date": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                            }
                            await client.create("pos.payment", refund_payment_data)

                            await client.write(
                                "pos.order",
                                refund_order_id,
                                {
                                    "state": "paid",
                                    "amount_paid": -abs(refund_amount_for_line),
                                },
                            )
                        else:
                            logger.warning(f"    Could not determine original payment method for order {order_name}. Skipping payment reversal.")
                    else:
                        logger.warning(f"    Order {order_name} has no payment_ids. Skipping payment reversal.")

                    created_refund_details.append(
                        {
                            "refund_order_name": refund_order_name,
                            "original_order_name": order_name,
                            "product": product_name,
                            "quantity": qty_to_refund,
                            "refund_amount": refund_amount_for_line,
                        }
                    )
                    refund_count += 1

                except Exception as e_refund:
                    logger.warning(f"Failed to process refund for order {order_name}: {e_refund}")
                    continue

            if created_refund_details:
                logger.succeed(f"Successfully created {len(created_refund_details)} POS refunds.")

        except Exception as e:
            logger.fail(f"Failed to create POS refunds: {e}")
            # raise


if __name__ == "__main__":
    asyncio.run(insert_pos_refunds(num_refunds=5))
