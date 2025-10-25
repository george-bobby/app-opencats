import datetime
import json
import random
from typing import Any

from faker import Faker

from apps.odoosales.config.constants import (
    CrmModelName,
    MailModelName,
    ProductModelName,
    ResModelName,
    SaleModelName,
)
from apps.odoosales.config.settings import settings
from apps.odoosales.utils.odoo import OdooClient
from common.load_json import load_json
from common.logger import logger


faker = Faker("en_US")


async def _process_quotations(
    quotations: list[dict[str, Any]],
    products_lookup: dict[str, list[dict[str, Any]]],
    customers_lookup: dict[str, dict[str, Any]],
    activity_type_lookup: dict[str, int],
    teams: list[dict[str, Any]],
    members: list[dict[str, Any]],
) -> int:
    """Process a chunk of quotations and return count of created quotations"""

    async with OdooClient() as client:
        sale_order_model = await client.search_read("ir.model", [("model", "=", "sale.order")], ["id"])

        created_count = 0

        for idx, quotation in enumerate(quotations):
            try:
                if quotation["product_name"] not in products_lookup:
                    continue

                if quotation["customer_name"] not in customers_lookup:
                    continue

                team_id = random.choice(teams)["id"]
                products = products_lookup[quotation["product_name"]]
                user_id = random.choice(members)["user_id"][0]
                partner_id = customers_lookup[quotation["customer_name"]]["id"]

                if idx <= len(quotations) // 3:
                    user_id = 2

                quotation_id = await client.create(
                    SaleModelName.SALE_ORDER.value,
                    {
                        "partner_id": partner_id,
                        "user_id": user_id,
                        "state": "draft",
                        "name": faker.numerify(f"QUO/{datetime.date.today().strftime('%Y/%m/%d')}/####"),
                        "team_id": team_id,
                        "pricelist_id": 1,
                    },
                )

                activity_id = await client.create(
                    MailModelName.MAIL_ACTIVITY.value,
                    {
                        "res_id": quotation_id,
                        "activity_type_id": activity_type_lookup.get(random.choice(["Call", "Email", "Meeting", "Exception", "Upload Document"])),
                        "res_model": "sale.order",
                        "res_model_id": sale_order_model[0]["id"],
                        "date_deadline": (datetime.date.today() + datetime.timedelta(days=random.randint(3, 15))).strftime("%Y-%m-%d"),
                    },
                )
                await client.write(
                    SaleModelName.SALE_ORDER.value,
                    quotation_id,
                    {
                        "activity_ids": [(4, activity_id)],
                    },
                )

                # Create order lines for selected products
                selected_products = random.sample(products, random.randint(1, min(3, len(products))))
                order_lines = []

                for product in selected_products:
                    product_id = product["id"]
                    quantity = random.randint(30, 100) if customers_lookup[quotation["customer_name"]]["is_company"] else random.randint(3, 10)
                    order_lines.append(
                        {
                            "order_id": quotation_id,
                            "product_id": product_id,
                            "product_uom_qty": quantity,
                        }
                    )

                # Bulk create order lines
                if order_lines:
                    await client.create(SaleModelName.SALE_ORDER_LINE.value, [order_lines])

                created_count += 1

            except Exception as e:
                logger.error(f"Error creating quotation for '{quotation.get('customer_name', 'Unknown')}': {e}")
                continue

        return created_count


async def insert_quotations():
    quotations = load_json(settings.DATA_PATH.joinpath("quotations.json"))

    logger.start(f"Inserting {len(quotations)} quotations...")

    # Fetch all required data first (shared across all threads)
    async with OdooClient() as client:
        templates = await client.search_read(
            ProductModelName.PRODUCT_TEMPLATE.value,
            [("sale_ok", "=", True)],
            ["id", "name"],
        )
        products = await client.search_read(
            "product.product",
            [],
            ["id", "product_tmpl_id"],
        )

        # Build products mapping
        products_lookup = {}
        for template in templates:
            for product in products:
                if product["product_tmpl_id"][0] == template["id"]:
                    products_lookup.setdefault(template["name"], []).append(product)

        customers = await client.search_read(
            ResModelName.RES_PARTNER.value,
            [("customer_rank", ">", 0)],
            ["id", "name", "is_company"],
        )
        customers_lookup = {customer["name"]: customer for customer in customers}

        activity_types = await client.search_read(
            MailModelName.MAIL_ACTIVITY_TYPE.value,
            [],
            ["id", "name"],
        )
        activity_type_lookup = {activity_type["name"]: activity_type["id"] for activity_type in activity_types}

        teams = await client.search_read(
            CrmModelName.CRM_TEAM.value,
            [],
            ["id"],
        )

        valid_users = await client.search_read(ResModelName.RES_USERS.value, [("active", "=", True)], ["id"])
        members = await client.search_read(
            CrmModelName.CRM_TEAM_MEMBER.value,
            [("user_id", "in", [user["id"] for user in valid_users])],
            ["id", "user_id", "crm_team_id"],
        )

    # Process quotations in parallel
    total_created = await _process_quotations(
        quotations,
        products_lookup,
        customers_lookup,
        activity_type_lookup,
        teams,
        members,
    )
    logger.succeed(f"Successfully inserted {total_created} quotations.")


async def _send_quotations(quotations: list[dict[str, Any]], partner_lookup: dict[int, int], send_quotation_mail_template_id: int) -> int:
    """Process a chunk of quotations for sending and return count of sent quotations"""

    async with OdooClient() as client:
        sent_count = 0

        for quotation in quotations:
            try:
                await client.execute_kw(
                    SaleModelName.SALE_ORDER.value,
                    "action_quotation_send",
                    [quotation["id"]],
                )

                # Skip if quotation user_id is not found in partner lookup
                if not quotation["user_id"] or quotation["user_id"][0] not in partner_lookup:
                    continue

                partner_id = partner_lookup[quotation["user_id"][0]]

                message_id = await client.create(
                    "mail.compose.message",
                    {
                        "res_ids": json.dumps([quotation["id"]]),
                        "model": "sale.order",
                        "message_type": "comment",
                        "author_id": partner_id,
                        "record_company_id": 1,
                        "record_name": quotation["name"],
                        "template_id": send_quotation_mail_template_id,
                        "email_from": settings.ODOO_USERNAME,
                    },
                )

                await client.execute_kw(
                    "mail.compose.message",
                    "action_send_mail",
                    [message_id],
                )

                sent_count += 1

                await client.write(
                    SaleModelName.SALE_ORDER.value,
                    quotation["id"],
                    {
                        "state": "sent",
                    },
                )

            except Exception as e:
                logger.error(f"Error sending quotation {quotation.get('name', 'Unknown')}: {e}")
                continue

        return sent_count


async def send_quotations():
    logger.start("Sending quotations...")

    # Fetch all required data first (shared across all threads)
    async with OdooClient() as client:
        partners = await client.search_read(ResModelName.RES_PARTNER.value, [], ["id", "user_id"])
        quotations = await client.search_read(
            SaleModelName.SALE_ORDER.value,
            [("state", "=", "draft")],
            ["id", "user_id", "name"],
        )
        send_quotation_mail_template = await client.search_read(
            "mail.template",
            [("model", "=", "sale.order"), ("name", "=", "Sales: Send Quotation")],
            ["id"],
        )
        document_report_layouts = await client.search_read("report.layout", [], ["id"])

        partner_lookup = {partner["user_id"][0]: partner["id"] for partner in partners if partner["user_id"]}
        send_quotation_mail_template_id = send_quotation_mail_template[0]["id"]
        send_count = len(quotations) // 2

        # Create document layout for the first quotation (done once)
        if quotations:
            document_layout_id = await client.create(
                "base.document.layout",
                {
                    "company_id": 1,
                    "report_layout_id": random.choice(document_report_layouts)["id"],
                },
            )
            await client.execute_kw("base.document.layout", "document_layout_save", [document_layout_id])

    # Select quotations to send
    quotations_to_send = quotations[:send_count]

    # Process quotations in parallel
    total_sent = await _send_quotations(quotations_to_send, partner_lookup, send_quotation_mail_template_id)
    logger.succeed(f"Successfully sent {total_sent} quotations.")
