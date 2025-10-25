import datetime
import random

from faker import Faker

from apps.odoosales.config.constants import CrmModelName, ProductModelName
from apps.odoosales.core.payment import create_pos_order_payments
from apps.odoosales.utils.odoo import OdooClient
from common.logger import logger


fake = Faker()

POS_CONFIG_ID = 1  # Default POS config ID


async def insert_pos_orders():
    logger.start("Inserting POS orders...")

    async with OdooClient() as client:
        try:
            # 1. Get necessary reference data
            templates = await client.search_read(
                ProductModelName.PRODUCT_TEMPLATE.value,
                [("sale_ok", "=", True)],
                ["id", "name"],
            )
            products = await client.search_read(
                ProductModelName.PRODUCT_PRODUCT.value,
                [("product_tmpl_id", "in", [template["id"] for template in templates])],
            )
            if not products:
                logger.fail("No product variants available for POS. Aborting.")
                return

            crm_teams = await client.search_read(
                CrmModelName.CRM_TEAM.value,
                [("use_opportunities", "=", True), ("use_leads", "=", True)],
                ["id", "name", "user_id"],
            )
            if not crm_teams:
                logger.fail("No CRM teams with opportunities and leads enabled found. Aborting.")
                return

            team_members = await client.search_read(
                "crm.team.member",
                [("crm_team_id", "in", [team["id"] for team in crm_teams])],
                ["id", "user_id", "crm_team_id"],
            )
            if not team_members:
                logger.fail("No team members found for CRM teams. Aborting.")
                return

            emps = await client.search_read("hr.employee", [], ["id", "name", "user_id"])
            if not emps:
                logger.fail("No employee users (cashiers) found. Aborting.")
                return

            # Build team leader lookup
            team_leader_lookup = {team["id"]: team["user_id"][0] for team in crm_teams if team.get("user_id")}
            # Build member-to-employee mapping

            customers = await client.search_read(
                "res.partner",
                [("customer_rank", ">", 0)],
                ["id", "name"],
            )
            if not customers:
                logger.fail("No customers found. Aborting.")
                return

            warehouses = await client.search_read("stock.warehouse", [], ["id", "name"])
            if not warehouses:
                logger.fail("No warehouses (stores) found. Aborting.")
                return

            pos_configs = await client.search_read("pos.config", [], ["id", "name"])
            if not pos_configs:
                logger.fail("No POS Config found. Aborting.")
                return

            pricelist = await client.search_read(
                "product.pricelist",
                [("name", "=", "2025 Standard Retail")],
                ["id"],
            )
            pricelist_id = pricelist[0]["id"] if pricelist else 1

            payment_methods_db = await client.search_read(
                "pos.payment.method",
                [("journal_id", "!=", None)],
                ["id", "name"],
            )
            if not payment_methods_db:
                logger.fail("No POS payment methods found. Aborting.")
                return

            # 2. For each team member, open at least 3 sessions and insert orders
            total_orders = 0
            total_sessions = 0
            orders_per_session = 5  # You can adjust this for more/less orders per session
            for member in team_members:
                member_user_id = member["user_id"][0]
                team_id = member["crm_team_id"][0]
                leader_user_id = team_leader_lookup.get(team_id)
                if not leader_user_id:
                    logger.warning(f"No leader found for team_id {team_id}, skipping session creation for this member.")
                    continue
                for session_num in range(3):
                    # Choose a random employee for employee_id
                    emp = random.choice(emps)
                    # Generate a random start time within the past year
                    start_at_dt = fake.date_time_between(start_date="-1y", end_date="now")
                    # Add at least 4 hours, up to 10 hours, for stop_at
                    stop_at_dt = fake.date_time_between(start_date=start_at_dt, end_date="+8h")
                    # Generate realistic cash register balances
                    opening_balance = round(random.uniform(50.0, 200.0), 2)
                    closing_balance = round(opening_balance + random.uniform(100.0, 1000.0), 2)
                    # Open register (POS session)
                    session_data = {
                        "user_id": leader_user_id,  # Team leader as session user
                        "employee_id": emp["id"],  # Random employee as session employee
                        "config_id": pos_configs[0]["id"],
                        "start_at": start_at_dt.strftime("%Y-%m-%d %H:%M:%S"),
                        "stop_at": stop_at_dt.strftime("%Y-%m-%d %H:%M:%S"),
                        "cash_register_balance_start": opening_balance,
                        "cash_register_balance_end_real": closing_balance,
                    }
                    session_id = await client.create("pos.session", session_data)
                    total_sessions += 1
                    # Insert orders (checkout products)
                    orders = []
                    for i in range(orders_per_session):
                        order_date = fake.date_time_between(start_date="-1y", end_date="now")
                        warehouse = random.choice(warehouses)
                        customer = random.choice(customers)
                        order_number = f"POS{member_user_id}{session_num}{i}{random.randint(1000, 9999)}"
                        order_products = random.sample(products, random.randint(1, min(5, len(products))))
                        payment_method = random.choice(payment_methods_db)["name"]
                        order_lines = []
                        total_amount = 0
                        for product in order_products:
                            qty = random.randint(1, 3)
                            unit_price = product["lst_price"]
                            discount_pct = random.randint(0, 10)
                            subtotal = qty * unit_price * (1 - discount_pct / 100)
                            total_amount += subtotal
                            order_lines.append(
                                {
                                    "product_id": product["id"],
                                    "qty": qty,
                                    "price_unit": unit_price,
                                    "price_subtotal": subtotal,
                                    "price_subtotal_incl": subtotal * 1.0825,
                                    "discount": discount_pct,
                                }
                            )
                        order_data = {
                            "name": order_number,
                            "session_id": session_id,
                            "date_order": order_date.strftime("%Y-%m-%d %H:%M:%S"),
                            "employee_id": emp["id"],
                            "partner_id": customer["id"],
                            "amount_total": total_amount,
                            "amount_tax": total_amount * 0.0825,
                            "amount_paid": total_amount * 1.0825,
                            "amount_return": 0,
                            "lines": [(0, 0, line) for line in order_lines],
                            "state": "paid",
                            "pos_reference": order_number,
                            "pricelist_id": pricelist_id,
                            "crm_team_id": team_id,
                        }
                        try:
                            order_id = await client.create("pos.order", order_data)
                            orders.append(
                                {
                                    "order_id": order_id,
                                    "order_number": order_number,
                                    "date": order_date.strftime("%Y-%m-%d %H:%M:%S"),
                                    "store": warehouse["name"],
                                    "cashier": emp["name"],
                                    "payment": payment_method,
                                    "amount": round(total_amount * 1.0825, 2),
                                    "products": [p["display_name"] for p in order_products],
                                    "team": next(t["name"] for t in crm_teams if t["id"] == team_id),
                                }
                            )
                            total_orders += 1
                        except Exception as e:
                            logger.warning(f"Failed to create order {order_number}: {e}")
                            continue
                    # Create payments for all orders in this session
                    if orders:
                        await create_pos_order_payments(orders)
                    # Close register (POS session)
                    try:
                        await client.write(
                            "pos.session",
                            session_id,
                            {
                                "state": "closed",
                                "stop_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                            },
                        )
                    except Exception as e_close:
                        logger.error(f"Failed to close session ID {session_id}: {e_close}")
            logger.succeed(f"Successfully created {total_orders} POS orders across {total_sessions} sessions for all team members.")
        except Exception as e:
            logger.fail(f"Failed to backfill POS orders: {e}")
