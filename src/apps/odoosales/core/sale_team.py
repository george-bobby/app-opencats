import random

from apps.odoosales.config.constants import CrmModelName
from apps.odoosales.core.settings import settings
from apps.odoosales.utils.odoo import OdooClient
from common.load_json import load_json
from common.logger import logger


async def insert_sale_teams():
    """Insert or update sales teams with simple user assignment"""

    sale_teams = load_json(settings.DATA_PATH.joinpath("sale_teams.json"))

    logger.start(f"Inserting {len(sale_teams)} sales teams...")

    async with OdooClient() as client:
        try:
            # Get all active users (excluding portal/public users)
            users = await client.search_read(
                "res.users",
                [("active", "=", True)],
                ["id", "name"],
            )

            if not users:
                logger.warning("No users found. Teams will be created without members.")
                users = []

            users_lookup = {user["name"]: user["id"] for user in users}

            team_records = []

            default_sale_team = await client.search_read(
                CrmModelName.CRM_TEAM.value,
                [
                    ("active", "=", True),
                    ("name", "=", "Sales"),
                    ("use_opportunities", "=", True),
                    ("use_leads", "=", True),
                ],
                ["id"],
            )

            for idx, team_data in enumerate(sale_teams):
                team_name = team_data["name"]

                # Assign team leader (first available user)
                team_leader_id = users_lookup.get(team_data["leader"])

                member_ids = [users_lookup.get(member) for member in team_data["members"]]

                team_payload = {
                    "name": team_name,
                    "user_id": team_leader_id,
                    "member_ids": [(6, 0, member_ids)],
                    "invoiced_target": random.randint(10000, 1000000),
                    "use_opportunities": True,
                    "use_leads": True,
                }

                # Add alias if provided
                if "alias_name" in team_data:
                    team_payload["alias_name"] = team_data["alias_name"]

                if idx == 0:
                    await client.write(CrmModelName.CRM_TEAM.value, default_sale_team[0]["id"], team_payload)
                    continue

                team_records.append(team_payload)

            await client.create(CrmModelName.CRM_TEAM.value, [team_records])
            logger.succeed(f"Inserted {len(team_records)} sales teams successfully.")

        except Exception as e:
            logger.error(f"Error inserting sale teams: {e}")
            raise
