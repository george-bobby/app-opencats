import random

from faker import Faker

from apps.odoosales.config.constants import CrmModelName, HRModelName
from apps.odoosales.utils.odoo import OdooClient
from common.logger import logger


fake = Faker()


async def insert_pos_sessions():
    logger.start("Creating POS session data...")
    async with OdooClient() as client:
        try:
            # Get CRM teams with use_opportunities and use_leads enabled
            sale_teams = await client.search_read(
                CrmModelName.CRM_TEAM.value,
                [
                    ("use_opportunities", "=", True),
                    ("use_leads", "=", True),
                ],
                ["id", "name", "user_id"],
            )
            if not sale_teams:
                logger.fail("No CRM teams with opportunities and leads enabled found. Aborting.")
                return

            cashiers = await client.search_read(HRModelName.HR_EMPLOYEE.value, [], ["id", "name", "user_id"])

            team_members = await client.search_read(
                CrmModelName.CRM_TEAM_MEMBER.value,
                [("crm_team_id", "in", [team["id"] for team in sale_teams])],
                ["id", "name", "crm_team_id", "user_id"],
            )
            sale_teams_lookup = {}

            for team in sale_teams:
                sale_teams_lookup[team["id"]] = {
                    "name": team["name"],
                    "leader_id": team["user_id"][0] if team["user_id"] else None,
                    "members": [
                        {
                            "user_id": member["user_id"][0],
                            "emp_id": next((emp["id"] for emp in cashiers if emp["user_id"] and emp["user_id"][0] == member["user_id"][0]), None),
                        }
                        for member in team_members
                        if member["crm_team_id"][0] == team["id"]
                    ],
                }

            pos_configs = await client.search_read(
                "pos.config",
                [],
                ["id", "name", "journal_id", "company_id", "cash_control"],  # Removed journal_ids
            )
            if not pos_configs:
                logger.fail("No POS Configurations found. Aborting session creation.")
                return

            all_sessions_created = []

            # Create multiple sessions per team and config for better distribution
            for config in pos_configs:
                for team in sale_teams:
                    # Create 3-5 sessions per team per config
                    sessions_per_team = random.randint(3, 5)

                    for session_idx in range(sessions_per_team):
                        open_date_dt = fake.date_time_between(start_date="-1y", end_date="now")
                        close_date_dt = fake.date_time_between(start_date=open_date_dt, end_date="+8h")
                        opening_balance = random.randint(100, 1000)
                        closing_balance_cash = opening_balance + random.randint(100, 1000)

                        # Get team members for this team
                        team_members_list = sale_teams_lookup[team["id"]]["members"]
                        if not team_members_list:
                            continue

                        mem = random.choice(team_members_list)
                        if not mem["emp_id"]:
                            continue

                        session_data = {
                            "name": f"Session {team['name']} - {open_date_dt.strftime('%Y-%m-%d %H:%M')} #{session_idx + 1}",
                            "user_id": mem["user_id"],
                            "crm_team_id": team["id"],
                            "employee_id": mem["emp_id"],
                            "config_id": config["id"],
                            "company_id": 1,
                            "start_at": open_date_dt.strftime("%Y-%m-%d %H:%M:%S"),
                            "stop_at": close_date_dt.strftime("%Y-%m-%d %H:%M:%S"),
                            "state": "opened",
                            "cash_register_balance_start": opening_balance,
                            "cash_register_balance_end_real": closing_balance_cash,
                            "opening_balance": opening_balance,
                            "closing_balance_cash": closing_balance_cash,
                            "is_in_company_currency": True,
                        }

                        try:
                            session_id = await client.create("pos.session", session_data)
                            all_sessions_created.append(session_id)
                        except Exception as e:
                            logger.warning(f"Failed to create session for team {team['name']}: {e}")
                            continue

            logger.succeed(f"Successfully created {len(all_sessions_created)} POS sessions across {len(sale_teams)} teams.")

        except Exception as e:
            logger.fail(f"Failed to create POS sessions: {e}")
            # raise
