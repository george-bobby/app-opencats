import json
import random
from pathlib import Path

from faker import Faker

from apps.frappecrm.config.settings import settings
from apps.frappecrm.utils import frappe_client
from common.logger import logger


fake = Faker()


async def generate_users(target_count: int = 60):
    """Generate users data and save to JSON file"""
    # Define the path to the JSON file
    json_file_path = Path(__file__).parent.parent.joinpath("data/generated/users.json")

    # Ensure the directory exists
    json_file_path.parent.mkdir(parents=True, exist_ok=True)

    users_data = await generate_users_data(target_count)

    # Save the generated users to the JSON file
    try:
        with json_file_path.open("w", encoding="utf-8") as f:
            json.dump(users_data, f, indent=2, ensure_ascii=False)
        logger.succeed(f"Saved {len(users_data)} users to {json_file_path}")
    except Exception as e:
        logger.error(f"Error saving users to file: {e}")


async def insert_users():
    # Define the path to the JSON file
    json_file_path = Path(__file__).parent.parent.joinpath("data/generated/users.json")

    # Check if the JSON file exists and read from it
    if not json_file_path.exists():
        logger.error(f"Users data file not found at {json_file_path}. Please run generate command first.")
        return

    try:
        with json_file_path.open(encoding="utf-8") as f:
            users_data = json.load(f)
        logger.info(f"Loaded {len(users_data)} users from file")
    except Exception as e:
        logger.error(f"Error reading users from file: {e}")
        return

    # Insert users from the data
    client = frappe_client.create_client()
    existing_users = client.get_list(
        "User",
        fields=["email"],
        filters=[["name", "not in", ["Administrator", "Guest"]]],
        limit_page_length=settings.LIST_LIMIT,
    )
    existing_emails = [user["email"] for user in existing_users]

    users_to_insert = []
    for user_data in users_data:
        # Skip if user already exists
        if user_data["email"] in existing_emails:
            logger.info(f"User '{user_data['email']}' already exists, skipping")
            continue
        users_to_insert.append(user_data)

    if not users_to_insert:
        logger.info("No new users to insert")
        return

    inserted_count = 0
    for user_data in users_to_insert:
        try:
            client.insert(user_data)
            inserted_count += 1
        except Exception as e:
            logger.error(f"Failed to create user {user_data['email']}: {e!s}")

    logger.succeed(f"Successfully inserted {inserted_count} users")


async def generate_users_data(target_count: int):
    """Generate users data and return them as a list of dictionaries"""
    # Generate domain from company name or use a random domain
    domain = settings.COMPANY_NAME.lower()
    domain = "".join(c for c in domain if c.isalnum()) + ".com"

    users = []
    for _ in range(target_count):
        # Generate fake user data
        gender = random.choice(["Male", "Female"])
        first_name = fake.first_name_male() if gender == "Male" else fake.first_name_female()
        last_name = fake.last_name()
        email = f"{first_name.lower()}.{last_name.lower()}@{domain}"

        # Create user document
        user_doc = {
            "doctype": "User",
            "email": email,
            "first_name": first_name,
            "last_name": last_name,
            "send_welcome_email": 0,  # Disable automatic welcome email
            "user_type": "System User",
            "roles": [{"role": "Sales User"}],
            "new_password": settings.USER_PASSWORD,
        }
        users.append(user_doc)

    return users
