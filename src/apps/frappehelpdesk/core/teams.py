import json
from pathlib import Path

from faker import Faker
from openai import AsyncOpenAI
from pydantic import BaseModel, Field

from apps.frappehelpdesk.config.settings import settings
from apps.frappehelpdesk.core.users import USERS_CACHE_FILE
from apps.frappehelpdesk.utils.frappe_client import FrappeClient
from common.logger import logger


fake = Faker()
openai_client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)

# Cache file paths
TEAMS_CACHE_FILE = Path(Path(__file__).parent.parent, "data", "generated", "teams.json")
TEAM_ASSIGNMENTS_CACHE_FILE = Path(Path(__file__).parent.parent, "data", "generated", "team_assignments.json")


class Team(BaseModel):
    team_name: str = Field(description="The name of the helpdesk team")
    description: str = Field(description="Brief description of the team's role and responsibilities")


class TeamList(BaseModel):
    teams: list[Team] = Field(description="A list of helpdesk teams")


async def generate_teams(number_of_teams: int = 5):
    """
    Generate teams using OpenAI with Pydantic and save to JSON cache file.
    Always generates fresh data and overwrites existing cache.
    """
    logger.start(f"Generating {number_of_teams} teams...")

    # Use OpenAI to generate team data with structured output
    try:
        teams_response = await openai_client.beta.chat.completions.parse(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": "You are a helpful assistant that generates realistic helpdesk team data.",
                },
                {
                    "role": "user",
                    "content": f"""Generate {number_of_teams} professional customer support teams for {settings.COMPANY_NAME}'s helpdesk system. 
                    
                    Company context: {settings.COMPANY_NAME} is {settings.DATA_THEME_SUBJECT}.
                    
                    Create diverse teams that would handle different aspects of customer support:
                    - Technical support teams
                    - Product specialist teams  
                    - Account/billing teams
                    - Escalation teams
                    - Onboarding teams
                    - Sales support teams
                    - Training teams
                    
                    Each team should have:
                    - A professional, clear team name (appropriate for {settings.COMPANY_NAME})
                    - A brief description of their role and responsibilities
                    
                    Make the teams realistic and useful for {settings.COMPANY_NAME}'s customer support organization.""",
                },
            ],
            response_format=TeamList,
        )

        teams = teams_response.choices[0].message.parsed.teams
        logger.info(f"Generated {len(teams)} teams using OpenAI")

    except Exception as e:
        logger.warning(f"Error generating teams with OpenAI: {e}, falling back to default teams")
        # Fallback to default teams with descriptions
        default_teams = [
            {"team_name": "Technical Support", "description": "Handles technical issues and troubleshooting for customers"},
            {"team_name": "Product Experts", "description": "Provides specialized knowledge about product features and usage"},
            {"team_name": "Billing & Accounts", "description": "Manages billing inquiries, account changes, and payment issues"},
            {"team_name": "Escalation Team", "description": "Handles complex cases escalated from other teams"},
            {"team_name": "Customer Onboarding", "description": "Assists new customers with setup and initial configuration"},
        ][:number_of_teams]

        teams = [Team(**team_data) for team_data in default_teams]

    # Create team documents for Frappe
    teams_data = []
    for team in teams:
        team_doc = {"doctype": "HD Team", "team_name": team.team_name, "description": team.description}
        teams_data.append(team_doc)

    # Always save to cache (overwrite existing)
    try:
        TEAMS_CACHE_FILE.parent.mkdir(exist_ok=True)
        # Convert Pydantic models to dictionaries before serializing to JSON
        serializable_teams = [team.model_dump() for team in teams]
        with TEAMS_CACHE_FILE.open("w") as f:
            json.dump(serializable_teams, f, indent=2)
        logger.info(f"Saved {len(teams_data)} teams to {TEAMS_CACHE_FILE}")
    except Exception as e:
        logger.warning(f"Error saving teams cache: {e}")

    logger.succeed(f"Generated {len(teams_data)} teams")


async def seed_teams():
    """
    Read teams from cache file and insert them into Frappe helpdesk.
    """
    logger.start("Seeding teams...")

    # Load teams from cache
    if not TEAMS_CACHE_FILE.exists():
        logger.fail("Teams cache file not found. Please run generate_teams first.")
        return

    try:
        with TEAMS_CACHE_FILE.open() as f:
            teams_data = json.load(f)
            # Convert back to Team objects for validation
            teams = [Team(**team_data) for team_data in teams_data]
    except (json.JSONDecodeError, Exception) as e:
        logger.fail(f"Error loading teams cache: {e}")
        return

    if not teams:
        logger.fail("No teams found in cache file")
        return

    async with FrappeClient() as client:
        successful_teams = 0

        for team in teams:
            try:
                team_doc = {"doctype": "HD Team", "team_name": team.team_name}
                await client.insert(team_doc)
                logger.info(f"Inserted team: {team.team_name}")
                successful_teams += 1
            except Exception as e:
                if "DuplicateEntryError" in str(e):
                    logger.info(f"Team '{team.team_name}' already exists, skipping creation")
                else:
                    logger.warning(f"Error inserting team: {e}")

    logger.succeed(f"Seeded {successful_teams}/{len(teams)} teams")


async def generate_team_assignments():
    """
    Generate team member assignments using Faker and save to JSON cache file.
    Reads from teams.json and users.json cache files.
    """
    logger.start("Generating team member assignments...")

    # Load teams from cache
    if not TEAMS_CACHE_FILE.exists():
        logger.fail("Teams cache file not found. Please run generate_teams first.")
        return

    # Load users from cache
    if not USERS_CACHE_FILE.exists():
        logger.fail("Users cache file not found. Please run generate_users first.")
        return

    try:
        # Load teams
        with TEAMS_CACHE_FILE.open() as f:
            teams_data = json.load(f)

        # Load users (agents only)
        with USERS_CACHE_FILE.open() as f:
            users_cache = json.load(f)
            users_data = users_cache.get("users", [])
            agents_data = [user for user in users_data if user.get("role") == "Agent"]

    except (json.JSONDecodeError, Exception) as e:
        logger.fail(f"Error loading cache files: {e}")
        return

    if not teams_data:
        logger.fail("No teams found in cache file")
        return

    if not agents_data:
        logger.fail("No agents found in users cache file")
        return

    # Generate team assignments
    team_assignments = []

    for team in teams_data:
        # Determine number of members for this team
        base_members = len(agents_data) // len(teams_data)
        variation = fake.random_int(min=-2, max=5)
        number_of_members = max(1, base_members + variation)  # Ensure at least 1 member

        # Randomly select agents for this team
        try:
            selected_agents = fake.random_elements(elements=agents_data, length=min(number_of_members, len(agents_data)), unique=True)
        except ValueError:
            # If we don't have enough unique agents, just use all agents
            selected_agents = agents_data[:number_of_members]

        assignment = {"team_name": team["team_name"], "members": [{"user": agent["email"]} for agent in selected_agents], "member_count": len(selected_agents)}

        team_assignments.append(assignment)

    # Save to cache
    try:
        TEAM_ASSIGNMENTS_CACHE_FILE.parent.mkdir(exist_ok=True)
        with TEAM_ASSIGNMENTS_CACHE_FILE.open("w") as f:
            json.dump(team_assignments, f, indent=2)
        logger.info(f"Saved team assignments to {TEAM_ASSIGNMENTS_CACHE_FILE}")
    except Exception as e:
        logger.warning(f"Error saving team assignments cache: {e}")

    total_assignments = sum(assignment["member_count"] for assignment in team_assignments)
    logger.succeed(f"Generated {len(team_assignments)} team assignments with {total_assignments} total member assignments")


async def seed_team_assignments():
    """
    Read team assignments from cache file and apply them in Frappe helpdesk.
    """
    logger.start("Seeding team member assignments...")

    # Load team assignments from cache
    if not TEAM_ASSIGNMENTS_CACHE_FILE.exists():
        logger.fail("Team assignments cache file not found. Please run generate_team_assignments first.")
        return

    try:
        with TEAM_ASSIGNMENTS_CACHE_FILE.open() as f:
            assignments_data = json.load(f)
    except (json.JSONDecodeError, Exception) as e:
        logger.fail(f"Error loading team assignments cache: {e}")
        return

    if not assignments_data:
        logger.fail("No team assignments found in cache file")
        return

    async with FrappeClient() as client:
        successful_assignments = 0

        for assignment in assignments_data:
            try:
                # First, verify which users actually exist in the system
                existing_members = []
                for member in assignment["members"]:
                    user_email = member["user"]
                    try:
                        # Check if user exists
                        user_doc = await client.get_doc("User", user_email)
                        if user_doc:
                            existing_members.append(member)
                    except Exception:
                        # User doesn't exist, skip this member
                        logger.info(f"Skipping non-existent user {user_email} for team {assignment['team_name']}")
                        continue

                if not existing_members:
                    logger.warning(f"No existing users found for team {assignment['team_name']}, skipping team assignment")
                    continue

                # Use direct document update with only existing users
                update_data = {"doctype": "HD Team", "name": assignment["team_name"], "users": existing_members}
                await client.update(update_data)
                logger.info(f"Assigned {len(existing_members)} existing agents to team: {assignment['team_name']}")
                successful_assignments += 1
            except Exception as e:
                logger.warning(f"Error assigning agents to team {assignment['team_name']}: {e}")

    total_members = sum(assignment["member_count"] for assignment in assignments_data)
    logger.succeed(f"Seeded {successful_assignments}/{len(assignments_data)} team assignments with {total_members} total member assignments")


async def delete_teams():
    """Delete teams"""
    async with FrappeClient() as client:
        teams = await client.get_list("HD Team", fields=["name"], limit_page_length=settings.LIST_LIMIT)
        for team in teams:
            try:
                await client.delete("HD Team", team["name"])
                logger.info(f"Deleted team: {team['name']}")
            except Exception as e:
                logger.warning(f"Error deleting team: {e}")
