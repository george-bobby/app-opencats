import asyncio
import json
from datetime import datetime
from pathlib import Path

from openai import AsyncOpenAI
from pydantic import BaseModel, Field

from apps.chatwoot.config.settings import settings
from apps.chatwoot.core.agents import AGENTS_FILE_PATH
from apps.chatwoot.utils.chatwoot import ChatwootClient
from apps.chatwoot.utils.faker import faker
from common.logger import logger


teams_file = settings.DATA_PATH / "generated" / "teams.json"
openai_client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)


class Team(BaseModel):
    name: str = Field(description="The name of the team")
    description: str = Field(description="The description of what the team does")
    created_at: datetime = Field(description="When the team was created")
    updated_at: datetime = Field(description="When the team was last updated")
    member_emails: list[str] = Field(description="List of email addresses of team members")


class TeamList(BaseModel):
    teams: list[Team] = Field(description="A list of teams")


async def generate_teams(number_of_teams: int):
    """Generate specified number of teams using OpenAI and save them to JSON file."""
    teams_file.parent.mkdir(parents=True, exist_ok=True)

    reference_teams_file = Path(__file__).parent.parent.joinpath("data", "teams.json")
    reference_teams = []
    try:
        with reference_teams_file.open(encoding="utf-8") as f:
            reference_teams = json.load(f)
    except FileNotFoundError:
        logger.warning(f"Reference teams file not found: {reference_teams_file}")

    agents_file_path = AGENTS_FILE_PATH
    agents_data = []
    try:
        with agents_file_path.open(encoding="utf-8") as f:
            agents_data = json.load(f)
        logger.info(f"Loaded {len(agents_data)} agents for team assignment")
    except FileNotFoundError:
        logger.warning(f"Generated agents file not found: {agents_file_path}")
        logger.warning("Teams will be generated without predefined member assignments")

    logger.info(f"Generating {number_of_teams} teams")

    # Generate teams using OpenAI with retry logic to ensure we get the requested amount
    max_retries = 3
    for attempt in range(max_retries):
        try:
            teams_response = await openai_client.beta.chat.completions.parse(
                model="gpt-4.1",
                messages=[
                    {
                        "role": "system",
                        "content": "You are a helpful assistant that generates realistic team data for Chatwoot. Always generate the EXACT number of teams requested.",
                    },
                    {
                        "role": "user",
                        "content": f"""Generate EXACTLY {number_of_teams} teams for a Chatwoot customer support system of a {settings.DATA_THEME_SUBJECT}.

                        IMPORTANT: You must generate exactly {number_of_teams} teams, no more, no less.
                        
                        Learn from these example teams to understand the structure and naming patterns:
                        ```json
                        {json.dumps(reference_teams, indent=2)}
                        ```
                        
                        Create teams that would be realistic for customer support operations. Each team should have:
                        - A meaningful name that reflects their role
                        - A clear description of their responsibilities
                        - Mix of specialized and general support teams
                        
                        **Common Team Types:**
                        - General Support: First-line customer service, basic inquiries
                        - Technical Support: Bug reports, integrations, technical troubleshooting
                        - Sales Support: Pre-sales questions, demos, pricing inquiries
                        - Billing Support: Payment issues, subscription management, invoicing
                        - Product Support: Feature requests, product feedback, onboarding
                        - Escalation Team: Complex issues, management escalations
                        
                        Make team names and descriptions specific to {settings.DATA_THEME_SUBJECT} context when relevant.
                        Each team should have allow_auto_assign set to true or false based on their role.""",
                    },
                ],
                response_format=TeamList,
            )

            teams_data = teams_response.choices[0].message.parsed.teams

            # Validate we got the correct number
            if len(teams_data) >= number_of_teams:
                # Trim to exact number if we got more
                teams_data = teams_data[:number_of_teams]
                break
            else:
                logger.warning(f"Attempt {attempt + 1}: Generated {len(teams_data)} teams, need {number_of_teams}")
                if attempt == max_retries - 1:
                    logger.error(f"Failed to generate {number_of_teams} teams after {max_retries} attempts")
                    return

        except Exception as e:
            logger.error(f"Attempt {attempt + 1} failed: {e}")
            if attempt == max_retries - 1:
                logger.error(f"Failed to generate teams after {max_retries} attempts")
                return

    agents = [agent for agent in agents_data if agent.get("role") == "agent"]
    admins = [agent for agent in agents_data if agent.get("role") == "administrator"]

    for team in teams_data:
        created_at = faker.date_time_between(start_date="-1y", end_date="-1m")
        updated_at = faker.date_time_between(start_date=created_at, end_date="now")
        team.created_at = created_at
        team.updated_at = updated_at

        team_member_emails = []

        if agents_data:
            num_admins = faker.random_int(min=1, max=min(3, len(admins)))
            if num_admins > 0:
                selected_admins = faker.random_elements(elements=admins, length=num_admins, unique=True)
                team_member_emails.extend([admin["email"] for admin in selected_admins])

            if agents:
                percentage = faker.random_int(min=30, max=90) / 100
                num_agents = max(1, int(len(agents) * percentage))
                selected_agents = faker.random_elements(elements=agents, length=num_agents, unique=True)
                team_member_emails.extend([agent["email"] for agent in selected_agents])

        team_member_emails.append(settings.CHATWOOT_ADMIN_EMAIL)  # Ensure admin is always included
        team.member_emails = team_member_emails
        logger.debug(f"Assigned {len(team_member_emails)} members to team {team.name}")

    serializable_teams = [team.model_dump(mode="json") for team in teams_data]

    with teams_file.open("w", encoding="utf-8") as f:
        json.dump(serializable_teams, f, indent=2, default=str)
        logger.info(f"Stored {len(teams_data)} teams with member assignments in {teams_file}")


async def seed_teams():
    """Seed teams from JSON file into Chatwoot."""
    async with ChatwootClient() as client:
        teams = None
        try:
            with teams_file.open(encoding="utf-8") as f:
                teams = [Team(**team) for team in json.load(f)]
                logger.info(f"Loaded {len(teams)} teams from {teams_file}")
        except FileNotFoundError:
            logger.error(f"Teams file not found: {teams_file}")
            logger.error("Please run generate_teams() first to create the teams file")
            return
        except json.JSONDecodeError:
            logger.error(f"Invalid JSON format in {teams_file}")
            return

        if teams is None:
            logger.error("No teams loaded from file")
            return

        api_users = await client.list_agents()
        email_to_user = {user["email"]: user for user in api_users}

        logger.info(f"Found {len(api_users)} users in Chatwoot for team assignment")

        async def add_single_team(team: Team) -> dict | None:
            """Add a single team and assign members to it."""
            try:
                team_data = await client.add_team(team.name, team.description)
                if not team_data:
                    logger.error(f"Failed to create team {team.name}")
                    return None

                logger.info(f"Added team {team.name}")

                team_member_ids = []
                missing_members = []

                for member_email in team.member_emails:
                    if member_email in email_to_user:
                        user = email_to_user[member_email]
                        team_member_ids.append(user["id"])
                    else:
                        missing_members.append(member_email)

                if missing_members:
                    logger.warning(f"Team {team.name}: Could not find users for emails: {missing_members}")

                if team_member_ids:
                    await client.add_team_members(team_data["id"], team_member_ids)
                    logger.info(f"Added {len(team_member_ids)} predefined members to team {team.name}")
                else:
                    logger.warning(f"No valid members found for team {team.name}")

                return team_data
            except Exception as e:
                logger.error(f"Error adding team {team.name}: {e}")
                return None

        logger.info(f"Adding {len(teams)} teams concurrently...")
        results = await asyncio.gather(*[add_single_team(team) for team in teams], return_exceptions=True)

        added_teams = [result for result in results if result is not None and not isinstance(result, Exception)]

        logger.info(f"Successfully added {len(added_teams)} out of {len(teams)} teams with predefined assignments")


async def insert_teams():
    """Legacy function - generates teams and seeds them into Chatwoot."""
    reference_teams_file = Path(__file__).parent.parent.joinpath("data", "teams.json")
    try:
        with reference_teams_file.open(encoding="utf-8") as f:
            reference_teams = json.load(f)
        await generate_teams(len(reference_teams))
    except FileNotFoundError:
        logger.warning("Reference teams.json not found, generating 6 teams")
        await generate_teams(6)

    await seed_teams()


async def delete_teams():
    async with ChatwootClient() as client:
        teams = await client.list_teams()
        for team in teams:
            await client.delete_team(team["id"])
            logger.info(f"Deleted team {team['name']}")
