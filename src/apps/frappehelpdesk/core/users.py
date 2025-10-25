import json
import random
from pathlib import Path

from faker import Faker

from apps.frappehelpdesk.config.settings import settings
from apps.frappehelpdesk.utils.frappe_client import FrappeClient
from common.logger import logger


fake = Faker()

# Cache file path
USERS_CACHE_FILE = Path(Path(__file__).parent.parent, "data", "generated", "users.json")


async def generate_users(number_of_agents: int, number_of_admins: int):
    """
    Generate users using Faker and save to JSON cache file.
    Always generates fresh data and overwrites existing cache.
    """
    total_users = number_of_agents + number_of_admins
    logger.start(f"Generating {total_users} users ({number_of_agents} agents, {number_of_admins} admins)...")

    # Generate domain from company name
    domain = settings.COMPANY_DOMAIN

    # Always generate fresh users (no cache loading)
    logger.info(f"Generating {total_users} fresh users with Faker")

    users_data = []
    generated_emails = set()  # Track generated emails to avoid duplicates

    attempts = 0
    max_attempts = total_users * 3  # Allow more attempts than needed users

    # Generate agents first
    agents_generated = 0
    while agents_generated < number_of_agents and attempts < max_attempts:
        attempts += 1

        # Generate fake user data
        gender = random.choice(["Male", "Female"])
        first_name = fake.first_name_male() if gender == "Male" else fake.first_name_female()
        last_name = fake.last_name()

        # Create base email
        base_email = f"{first_name.lower()}.{last_name.lower()}@{domain}"
        email = base_email

        # If base email exists, try variations
        if email in generated_emails:
            # Try with middle initial
            middle_initial = fake.random_letter().lower()
            email = f"{first_name.lower()}.{middle_initial}.{last_name.lower()}@{domain}"

            # If still duplicate, try with numbers
            if email in generated_emails:
                for i in range(1, 100):  # Try numbers 1-99
                    email = f"{first_name.lower()}.{last_name.lower()}{i}@{domain}"
                    if email not in generated_emails:
                        break
                else:
                    # If still no unique email found, skip this iteration
                    continue

        # Skip if email still exists (shouldn't happen with above logic)
        if email in generated_emails:
            continue

        # Add to tracking set
        generated_emails.add(email)

        # Store user data
        user_data = {
            "email": email,
            "first_name": first_name,
            "last_name": last_name,
            "gender": gender,
            "role": "Agent",
        }
        users_data.append(user_data)
        agents_generated += 1

    # Generate admins
    admins_generated = 0
    while admins_generated < number_of_admins and attempts < max_attempts:
        attempts += 1

        # Generate fake user data
        gender = random.choice(["Male", "Female"])
        first_name = fake.first_name_male() if gender == "Male" else fake.first_name_female()
        last_name = fake.last_name()

        # Create base email
        base_email = f"{first_name.lower()}.{last_name.lower()}@{domain}"
        email = base_email

        # If base email exists, try variations
        if email in generated_emails:
            # Try with middle initial
            middle_initial = fake.random_letter().lower()
            email = f"{first_name.lower()}.{middle_initial}.{last_name.lower()}@{domain}"

            # If still duplicate, try with numbers
            if email in generated_emails:
                for i in range(1, 100):  # Try numbers 1-99
                    email = f"{first_name.lower()}.{last_name.lower()}{i}@{domain}"
                    if email not in generated_emails:
                        break
                else:
                    # If still no unique email found, skip this iteration
                    continue

        # Skip if email still exists (shouldn't happen with above logic)
        if email in generated_emails:
            continue

        # Add to tracking set
        generated_emails.add(email)

        # Store user data
        user_data = {
            "email": email,
            "first_name": first_name,
            "last_name": last_name,
            "gender": gender,
            "role": "Agent Manager",
        }
        users_data.append(user_data)
        admins_generated += 1

    if len(users_data) < total_users:
        logger.warning(f"Could only generate {len(users_data)} unique users out of {total_users} requested after {attempts} attempts")

    # Always save to cache (overwrite existing)
    try:
        # Ensure the data directory exists
        USERS_CACHE_FILE.parent.mkdir(exist_ok=True)

        cache_data = {"users": users_data, "domain": domain, "agents": number_of_agents, "admins": number_of_admins}

        with USERS_CACHE_FILE.open("w") as f:
            json.dump(cache_data, f, indent=2)
        logger.info(f"Saved {len(users_data)} fresh users to {USERS_CACHE_FILE}")
    except Exception as e:
        logger.warning(f"Error saving users cache: {e}")

    logger.succeed(f"Generated {len(users_data)} fresh users ({agents_generated} agents, {admins_generated} admins)")


async def seed_users():
    """
    Read users from cache file and insert them into Frappe helpdesk using the new APIs.
    """
    logger.start("Seeding users...")

    # Load users from cache
    if not USERS_CACHE_FILE.exists():
        logger.fail("Users cache file not found. Please run generate_users first.")
        return

    try:
        with USERS_CACHE_FILE.open() as f:
            cache_data = json.load(f)
            users_data = cache_data.get("users", [])
    except (json.JSONDecodeError, KeyError, Exception) as e:
        logger.fail(f"Error loading users cache: {e}")
        return

    if not users_data:
        logger.fail("No users found in cache file")
        return

    async with FrappeClient(url=settings.API_URL, username=settings.ADMIN_USERNAME, password=settings.ADMIN_PASSWORD) as client:
        # Step 1: Send bulk invites first (if the API works)
        emails = [user["email"] for user in users_data]
        try:
            await client.post_api("helpdesk.api.agent.sent_invites", {"emails": emails})
            logger.info(f"Sent bulk invites to {len(emails)} users")
        except Exception as e:
            logger.info(f"Bulk invite API failed ({e}), will create users individually")

        # Step 2: Create/update users individually
        successful_users = 0

        for user_data in users_data:
            # Fix invalid roles from old cache data
            if user_data.get("role") == "Manager" or user_data.get("role") == "Support Manager":
                user_data["role"] = "Agent Manager"

            try:
                # Build roles list - everyone gets Agent role, plus their specific role if different
                roles = [{"role": "Agent"}]  # Everyone needs Agent role for HD Article/Canned Response creation
                if user_data["role"] != "Agent":  # Add specific role only if it's different from Agent
                    roles.append({"role": user_data["role"]})

                user_doc = {
                    "doctype": "User",
                    "email": user_data["email"],
                    "first_name": user_data["first_name"],
                    "last_name": user_data["last_name"],
                    "full_name": f"{user_data['first_name']} {user_data['last_name']}",
                    "gender": user_data["gender"],
                    "new_password": settings.USER_PASSWORD,
                    "enabled": 1,
                    "user_type": "System User",
                    "roles": roles,
                }

                await client.insert(user_doc)
                successful_users += 1
                role_names = [r["role"] for r in roles]
                logger.info(f"Created user: {user_data['email']} with roles: {', '.join(role_names)}")

            except Exception as e:
                if "DuplicateEntryError" in str(e) or "already exists" in str(e):
                    successful_users += 1  # Count existing users as successful
                    logger.info(f"User {user_data['email']} already exists")
                else:
                    logger.warning(f"Failed to create user {user_data['email']}: {e!s}")

    logger.succeed(f"Seeded {successful_users}/{len(users_data)} users")
