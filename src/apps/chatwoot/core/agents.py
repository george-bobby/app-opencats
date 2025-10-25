import asyncio
import json
from datetime import datetime

from pydantic import BaseModel, Field

from apps.chatwoot.config.settings import settings
from apps.chatwoot.utils.chatwoot import ChatwootClient
from apps.chatwoot.utils.database import AsyncPostgresClient
from apps.chatwoot.utils.faker import faker
from common.logger import logger


AGENTS_FILE_PATH = settings.DATA_PATH / "generated" / "agents.json"
ADMIN_AGENT = {
    "name": "Johny Appleseed",
    "email": settings.CHATWOOT_ADMIN_EMAIL,
    "role": "administrator",
    "created_at": datetime.now(),
    "confirmed_at": datetime.now(),
    "updated_at": datetime.now(),
}


class Agent(BaseModel):
    name: str = Field(description="The full name of the agent")
    email: str = Field(description="The email address of the agent")
    role: str = Field(description="The role of the agent (agent or administrator)")
    availability: int = Field(description="The availability status of the agent (0=online, 1=offline, 2=busy)")
    created_at: datetime = Field(description="When the agent was created")
    confirmed_at: datetime = Field(description="When the agent was confirmed")
    updated_at: datetime = Field(description="When the agent was last updated")


class AgentList(BaseModel):
    agents: list[Agent] = Field(description="A list of agents")


async def generate_agents(number_of_agents: int):
    """Generate specified number of agents and save them to JSON file."""
    # Ensure the generated directory exists
    AGENTS_FILE_PATH.parent.mkdir(parents=True, exist_ok=True)

    logger.info(f"Generating {number_of_agents} agents")
    agents = []

    for _ in range(number_of_agents):
        gender = faker.random_element(elements=("male", "female"))
        first_name = faker.first_name_female() if gender == "female" else faker.first_name_male()
        last_name = faker.last_name()
        email = faker.company_email(first_name, last_name)
        role = faker.random_element(elements=["agent"] * 4 + ["administrator"])
        availability = faker.random_element(elements=[0, 1, 2])  # 0=online, 1=offline, 2=busy

        # Generate faker timestamps
        # created_at should be earliest, then confirmed_at, then updated_at
        created_at = faker.date_time_between(start_date="-2y", end_date="-1m")
        confirmed_at = faker.date_time_between(start_date=created_at, end_date="-1w")
        updated_at = faker.date_time_between(start_date=confirmed_at, end_date="now")

        agents.append(Agent(name=f"{first_name} {last_name}", email=email, role=role, availability=availability, created_at=created_at, confirmed_at=confirmed_at, updated_at=updated_at))

    # Convert Pydantic models to dictionaries before serializing to JSON
    serializable_agents = [agent.model_dump(mode="json") for agent in agents]

    # Store agents in JSON file
    with AGENTS_FILE_PATH.open("w", encoding="utf-8") as f:
        json.dump(serializable_agents, f, indent=2, default=str)
        logger.info(f"Stored {len(agents)} agents in {AGENTS_FILE_PATH}")


async def seed_agents():
    """Seed agents from JSON file into Chatwoot."""
    async with ChatwootClient() as client:
        agents = None
        try:
            with AGENTS_FILE_PATH.open(encoding="utf-8") as f:
                agents = [Agent(**agent) for agent in json.load(f)]
                logger.info(f"Loaded {len(agents)} agents from {AGENTS_FILE_PATH}")
        except FileNotFoundError:
            logger.error(f"Agents file not found: {AGENTS_FILE_PATH}")
            logger.error("Please run generate_agents() first to create the agents file")
            return
        except json.JSONDecodeError:
            logger.error(f"Invalid JSON format in {AGENTS_FILE_PATH}")
            return

        if agents is None:
            logger.error("No agents loaded from file")
            return

        # Create async tasks for adding agents concurrently
        async def add_single_agent(agent: Agent) -> Agent | None:
            """Add a single agent and return the agent if successful, None if failed."""
            try:
                await client.add_agent(agent.name, agent.email, role=agent.role)
                logger.info(f"Added agent {agent.name} with role {agent.role}")
                return agent
            except Exception as e:
                logger.error(f"Error adding agent {agent.name}: {e}")
                return None

        # Run all add_agent calls concurrently
        logger.info(f"Adding {len(agents)} agents concurrently...")
        results = await asyncio.gather(*[add_single_agent(agent) for agent in agents], return_exceptions=True)

        # Filter out None results and exceptions to get successfully added agents
        added_agents = [result for result in results if result is not None and not isinstance(result, Exception)]

        logger.info(f"Successfully added {len(added_agents)} out of {len(agents)} agents")

        # Update users table with timestamps and passwords
        if added_agents:
            await update_users_timestamps(added_agents)


async def update_agent_statues():
    """Update agent statuses by setting auto_offline to false and using availability from generated agents data.

    Availability values:
    - 0 = online
    - 1 = offline
    - 2 = busy
    """
    try:
        # Load agents from JSON file to get their availability data
        agents = None
        try:
            with AGENTS_FILE_PATH.open(encoding="utf-8") as f:
                agents = [Agent(**agent) for agent in json.load(f)]
                logger.info(f"Loaded {len(agents)} agents from {AGENTS_FILE_PATH}")
        except FileNotFoundError:
            logger.error(f"Agents file not found: {AGENTS_FILE_PATH}")
            logger.error("Please run generate_agents() first to create the agents file")
            return
        except json.JSONDecodeError:
            logger.error(f"Invalid JSON format in {AGENTS_FILE_PATH}")
            return

        if not agents:
            logger.error("No agents loaded from file")
            return

        # Create email to availability mapping
        agent_availability_map = {agent.email: agent.availability for agent in agents}

        # Get all account_users records with their associated user emails
        account_users_query = """
            SELECT au.id, u.email 
            FROM account_users au
            JOIN users u ON au.user_id = u.id
        """
        account_users = await AsyncPostgresClient.fetch(account_users_query)

        if not account_users:
            logger.info("No account_users found to update")
            return

        logger.info(f"Updating statuses for {len(account_users)} account_users records")

        # Update each record with auto_offline = false and availability from agents data
        for user in account_users:
            user_id = user["id"]
            user_email = user["email"]

            # Use availability from agents data if available, otherwise use random
            if user_email in agent_availability_map:
                availability = agent_availability_map[user_email]
            else:
                availability = faker.random_element(elements=[0, 1, 2])  # 0=online, 1=offline, 2=busy
                logger.debug(f"Using random availability {availability} for non-agent user {user_email}")

            update_query = """
                UPDATE account_users 
                SET auto_offline = $1, 
                    availability = $2,
                    active_at = $3,
                    updated_at = $4
                WHERE id = $5
            """

            await AsyncPostgresClient.execute(
                update_query,
                False,  # auto_offline = false
                availability,
                datetime.now(),  # active_at
                datetime.now(),  # updated_at
                user_id,
            )

        logger.info(f"Successfully updated auto_offline to false and set availability for {len(account_users)} account_users")

    except Exception as e:
        logger.error(f"Error updating agent statuses: {e}")
        raise


async def update_user_activity_data():
    """Update users table with realistic activity data like sign-in counts, last sign-in times, etc."""
    try:
        # Get all users
        users = await AsyncPostgresClient.fetch("SELECT id, email, created_at FROM users")

        if not users:
            logger.info("No users found to update")
            return

        logger.info(f"Updating activity data for {len(users)} users")

        for user in users:
            user_id = user["id"]
            user_email = user["email"]
            created_at = user["created_at"]

            # Generate realistic activity data
            sign_in_count = faker.random_int(min=1, max=150)

            # Generate sign-in timestamps between user creation and now
            last_sign_in_at = faker.date_time_between(start_date=created_at, end_date="now")
            current_sign_in_at = faker.date_time_between(start_date=last_sign_in_at, end_date="now")

            # Generate IP addresses
            last_sign_in_ip = faker.ipv4()
            current_sign_in_ip = faker.ipv4()

            # Generate display name (optional field)
            display_name = faker.first_name() if faker.boolean(chance_of_getting_true=30) else None

            update_query = """
                UPDATE users 
                SET sign_in_count = $1,
                    current_sign_in_at = $2,
                    last_sign_in_at = $3,
                    current_sign_in_ip = $4,
                    last_sign_in_ip = $5,
                    display_name = $6,
                    updated_at = $7
                WHERE id = $8
            """

            await AsyncPostgresClient.execute(
                update_query,
                sign_in_count,
                current_sign_in_at,
                last_sign_in_at,
                current_sign_in_ip,
                last_sign_in_ip,
                display_name,
                datetime.now(),
                user_id,
            )

            logger.debug(f"Updated activity data for user {user_email}: {sign_in_count} sign-ins")

        logger.info(f"Successfully updated activity data for {len(users)} users")

    except Exception as e:
        logger.error(f"Error updating user activity data: {e}")
        raise


async def update_users_timestamps(agents: list[Agent]):
    """Update users with timestamps from the agent data, copy password from user ID 1, and reset password tokens."""
    try:
        # First, get the encrypted_password from user ID 1
        admin_user = await AsyncPostgresClient.fetchrow("SELECT encrypted_password FROM users WHERE id = 1")

        if not admin_user:
            logger.error("User with ID 1 not found. Cannot copy encrypted_password.")
            return

        admin_encrypted_password = admin_user["encrypted_password"]
        logger.info("Retrieved encrypted_password from user ID 1")

        # Create a mapping of email to agent data for quick lookup
        agent_email_map = {agent.email: agent for agent in agents}

        # Get all users from the database
        users = await AsyncPostgresClient.fetch("SELECT id, email FROM users")

        if not users:
            logger.info("No users found to update")
            return

        logger.info(f"Updating timestamps, passwords, and tokens for {len(users)} users")

        for user in users:
            user_email = user["email"]
            user_id = user["id"]

            # Check if this user corresponds to one of our agents
            if user_email in agent_email_map:
                agent = agent_email_map[user_email]
                # Use timestamps from the agent data
                created_at = agent.created_at
                confirmed_at = agent.confirmed_at
                updated_at = agent.updated_at

            else:
                # For non-agent users, generate faker timestamps
                created_at = faker.date_time_between(start_date="-2y", end_date="-1m")
                confirmed_at = faker.date_time_between(start_date=created_at, end_date="-1w")
                updated_at = faker.date_time_between(start_date=confirmed_at, end_date="now")

                logger.debug(f"Using generated timestamps for non-agent user {user_email}")

            # Update the user record with timestamps, password, and reset token
            update_query = """
                UPDATE users 
                SET confirmed_at = $1, 
                    created_at = $2, 
                    updated_at = $3,
                    encrypted_password = $4,
                    reset_password_token = NULL,
                    confirmation_token = NULL
                WHERE id = $5
            """

            await AsyncPostgresClient.execute(update_query, confirmed_at, created_at, updated_at, admin_encrypted_password, user_id)

        logger.info(f"Successfully updated timestamps, passwords, and reset tokens for {len(users)} users")

    except Exception as e:
        logger.error(f"Error updating user data: {e}")
        raise


async def insert_agents(number_of_agents: int):
    """Legacy function - generates agents and seeds them into Chatwoot."""
    await generate_agents(number_of_agents)
    await seed_agents()


async def reset_all_agent_passwords():
    """Reset all non-admin user passwords to match the superadmin password"""
    try:
        # First, get the superadmin user's encrypted_password and confirmed_at
        superadmin_query = "SELECT encrypted_password, confirmed_at FROM users WHERE email = $1"
        superadmin = await AsyncPostgresClient.fetchrow(superadmin_query, settings.CHATWOOT_ADMIN_EMAIL)

        if not superadmin:
            logger.error(f"Superadmin user with email {settings.CHATWOOT_ADMIN_EMAIL} not found")
            return

        logger.info("Found superadmin user, using their password and confirmation status")

        # Get all non-admin users
        non_admin_users = await get_non_super_admin_users()
        logger.info(f"Found {len(non_admin_users)} non-admin users to update")

        if not non_admin_users:
            logger.info("No non-admin users found to update")
            return

        # Update all non-admin users with superadmin's encrypted_password and confirmed_at
        update_query = """
            UPDATE users 
            SET encrypted_password = $1, confirmed_at = $2 
            WHERE email != $3
        """

        result = await AsyncPostgresClient.execute(
            update_query,
            superadmin["encrypted_password"],
            superadmin["confirmed_at"],
            settings.CHATWOOT_ADMIN_EMAIL,
        )

        logger.info(f"Password reset completed: {result}")
        logger.info(f"Updated {len(non_admin_users)} users with superadmin password")

    except Exception as e:
        logger.error(f"Error resetting passwords: {e}")
        raise


async def get_non_super_admin_users():
    """Get all users where email is not {settings.CHATWOOT_ADMIN_EMAIL}"""
    try:
        query = "SELECT * FROM users WHERE email != $1"
        users = await AsyncPostgresClient.fetch(query, settings.CHATWOOT_ADMIN_EMAIL)
        logger.info(f"Found {len(users)} non-superadmin users")

        return users

    except Exception as e:
        logger.error(f"Error fetching users: {e}")
        return []
