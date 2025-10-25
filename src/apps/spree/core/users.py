import json
import secrets
from datetime import datetime
from pathlib import Path

from faker import Faker
from pydantic import BaseModel

from apps.spree.config.settings import settings
from apps.spree.utils.constants import ROLES, US_COUNTRY_ID
from common.logger import Logger


logger = Logger()
fake = Faker()

USERS_FILE = settings.DATA_PATH / "generated" / "users.json"
ADDRESSES_FILE = settings.DATA_PATH / "generated" / "addresses.json"
STATES_FILE = settings.DATA_PATH / "states.json"


class User(BaseModel):
    """Individual user model."""

    id: int  # noqa: A003, RUF100
    email: str
    encrypted_password: str
    password_salt: str
    first_name: str
    last_name: str
    login: str
    authentication_token: str
    spree_api_key: str
    sign_in_count: int
    failed_attempts: int
    last_request_at: str | None
    current_sign_in_at: str | None
    last_sign_in_at: str | None
    current_sign_in_ip: str | None
    last_sign_in_ip: str | None
    selected_locale: str
    remember_created_at: str | None
    roles: list[str]  # List of role names
    is_customer: bool


class Address(BaseModel):
    """Individual address model."""

    id: int  # noqa: A003, RUF100
    firstname: str
    lastname: str
    address1: str
    address2: str | None
    city: str
    zipcode: str
    phone: str
    state_name: str
    alternative_phone: str | None
    company: str | None
    state_id: int
    country_id: int  # Always US_COUNTRY_ID for US
    user_id: int  # To link to user
    user_email: str  # For reference
    label: str


def generate_api_key() -> str:
    """Generate a 48-character API key."""
    return secrets.token_urlsafe(36)[:48]


def generate_auth_token() -> str:
    """Generate an authentication token."""
    return secrets.token_urlsafe(32)


def parse_datetime(iso_string: str | None) -> datetime | None:
    """Convert ISO string to datetime object, or return None if string is None."""
    if iso_string is None:
        return None
    try:
        return datetime.fromisoformat(iso_string.replace("T", " "))
    except (ValueError, AttributeError):
        return None


async def generate_users(number_of_dashboard_users: int, number_of_customer_users: int) -> dict | None:
    """Generate realistic users using Faker."""

    logger.info("Generating users using Faker...")

    try:
        users_list = []

        # Start user IDs from 2
        user_id = 2

        # Generate dashboard users (staff with store domain emails)
        for _ in range(number_of_dashboard_users):
            # Generate basic user info
            first_name = fake.first_name()
            last_name = fake.last_name()
            # Create store domain email (e.g., john.doe@fuzzloft.com)
            store_domain = settings.SPREE_STORE_NAME.lower()
            email = f"{first_name.lower()}.{last_name.lower()}@{store_domain}.com"

            # Generate secure tokens
            encrypted_password = settings.SPREE_ENCRYPTED_PASSWORD
            password_salt = settings.SPREE_PASSWORD_SALT
            auth_token = generate_auth_token()
            api_key = generate_api_key()

            # Generate sign-in data (some users have never signed in)
            has_signed_in = fake.boolean(chance_of_getting_true=75)
            sign_in_count = fake.random_int(min=0, max=50) if has_signed_in else 0

            # Generate timestamps
            created_at = fake.date_time_between(start_date="-1y", end_date="now")
            last_request_at = None
            current_sign_in_at = None
            last_sign_in_at = None
            remember_created_at = None

            if has_signed_in and sign_in_count > 0:
                last_sign_in_at = fake.date_time_between(start_date=created_at, end_date="now").isoformat()
                if sign_in_count > 1:
                    current_sign_in_at = fake.date_time_between(start_date=datetime.fromisoformat(last_sign_in_at.replace("T", " ")), end_date="now").isoformat()
                    last_request_at = fake.date_time_between(start_date=datetime.fromisoformat(current_sign_in_at.replace("T", " ")), end_date="now").isoformat()

                # Some users chose "remember me"
                if fake.boolean(chance_of_getting_true=30):
                    remember_created_at = fake.date_time_between(start_date=created_at, end_date="now").isoformat()

            # Generate IP addresses
            current_sign_in_ip = fake.ipv4() if has_signed_in else None
            last_sign_in_ip = fake.ipv4() if has_signed_in and sign_in_count > 1 else None

            # Dashboard users always get roles (they are staff)
            num_roles = fake.random_int(min=1, max=len(ROLES))
            roles = list(fake.random_elements(elements=ROLES, length=num_roles, unique=True))

            # Removed metadata generation

            user = User(
                id=user_id,
                email=email,
                encrypted_password=encrypted_password,
                password_salt=password_salt,
                first_name=first_name,
                last_name=last_name,
                login=email,  # Use email as login
                authentication_token=auth_token,
                spree_api_key=api_key,
                sign_in_count=sign_in_count,
                failed_attempts=fake.random_int(min=0, max=3),
                last_request_at=last_request_at,
                current_sign_in_at=current_sign_in_at,
                last_sign_in_at=last_sign_in_at,
                current_sign_in_ip=current_sign_in_ip,
                last_sign_in_ip=last_sign_in_ip,
                selected_locale=fake.random_element(elements=["en", "es", "fr", "de"]),
                remember_created_at=remember_created_at,
                roles=roles,
                is_customer=False,  # Dashboard users are staff, not customers
            )

            users_list.append(user.model_dump())
            user_id += 1

        # Generate customer users (regular customers with free email providers)
        for _ in range(number_of_customer_users):
            # Generate basic user info
            first_name = fake.first_name()
            last_name = fake.last_name()
            # Create email with name for consistency (with random free email provider)
            email_providers = ["gmail.com", "yahoo.com", "hotmail.com", "outlook.com", "icloud.com", "aol.com"]
            provider = fake.random_element(elements=email_providers)
            # Add variations to username part (sometimes with dot, underscore, or numbers)
            email_format = fake.random_element(
                [
                    f"{first_name.lower()}.{last_name.lower()}@{provider}",
                    f"{first_name.lower()}_{last_name.lower()}@{provider}",
                    f"{first_name.lower()}{last_name.lower()}@{provider}",
                    f"{first_name.lower()}{fake.random_int(1, 99)}@{provider}",
                    f"{first_name[0].lower()}{last_name.lower()}@{provider}",
                    f"{last_name.lower()}.{first_name.lower()}@{provider}",
                ]
            )
            email = email_format

            # Generate secure tokens
            encrypted_password = settings.SPREE_ENCRYPTED_PASSWORD
            password_salt = settings.SPREE_PASSWORD_SALT
            auth_token = generate_auth_token()
            api_key = generate_api_key()

            # Generate sign-in data (some customers have never signed in)
            has_signed_in = fake.boolean(chance_of_getting_true=60)  # Lower than staff
            sign_in_count = fake.random_int(min=0, max=25) if has_signed_in else 0

            # Generate timestamps
            created_at = fake.date_time_between(start_date="-1y", end_date="now")
            last_request_at = None
            current_sign_in_at = None
            last_sign_in_at = None
            remember_created_at = None

            if has_signed_in and sign_in_count > 0:
                last_sign_in_at = fake.date_time_between(start_date=created_at, end_date="now").isoformat()
                if sign_in_count > 1:
                    current_sign_in_at = fake.date_time_between(start_date=datetime.fromisoformat(last_sign_in_at.replace("T", " ")), end_date="now").isoformat()
                    last_request_at = fake.date_time_between(start_date=datetime.fromisoformat(current_sign_in_at.replace("T", " ")), end_date="now").isoformat()

                # Some customers chose "remember me"
                if fake.boolean(chance_of_getting_true=40):  # Higher than staff
                    remember_created_at = fake.date_time_between(start_date=created_at, end_date="now").isoformat()

            # Generate IP addresses
            current_sign_in_ip = fake.ipv4() if has_signed_in else None
            last_sign_in_ip = fake.ipv4() if has_signed_in and sign_in_count > 1 else None

            # Customer users get no roles (they are just customers)
            roles = []

            # Removed customer metadata generation

            user = User(
                id=user_id,
                email=email,
                encrypted_password=encrypted_password,
                password_salt=password_salt,
                first_name=first_name,
                last_name=last_name,
                login=email,  # Use email as login
                authentication_token=auth_token,
                spree_api_key=api_key,
                sign_in_count=sign_in_count,
                failed_attempts=fake.random_int(min=0, max=2),  # Customers have fewer failed attempts
                last_request_at=last_request_at,
                current_sign_in_at=current_sign_in_at,
                last_sign_in_at=last_sign_in_at,
                current_sign_in_ip=current_sign_in_ip,
                last_sign_in_ip=last_sign_in_ip,
                selected_locale=fake.random_element(elements=["en", "es", "fr", "de"]),
                remember_created_at=remember_created_at,
                roles=roles,
                is_customer=True,  # These are customer users
            )

            users_list.append(user.model_dump())
            user_id += 1

        users_dict = {"users": users_list}

        # Save to file
        settings.DATA_PATH.mkdir(parents=True, exist_ok=True)
        USERS_FILE.parent.mkdir(parents=True, exist_ok=True)
        with Path.open(USERS_FILE, "w", encoding="utf-8") as f:
            json.dump(users_dict, f, indent=2, ensure_ascii=False)

        total_users = number_of_dashboard_users + number_of_customer_users
        logger.succeed(f"Successfully generated and saved {total_users} users ({number_of_dashboard_users} dashboard, {number_of_customer_users} customer) to {USERS_FILE}")

        customer_users = users_list[number_of_dashboard_users:]

        # Generate addresses for customer users
        if customer_users:
            await generate_addresses_for_customers(customer_users)

        return users_dict

    except Exception as e:
        logger.error(f"Error generating users: {e}")
        raise


async def generate_addresses_for_customers(customer_users: list[dict]) -> dict | None:
    """Generate realistic US addresses for customer users."""

    logger.info("Generating addresses for customer users...")

    try:
        # Load US states data
        if not STATES_FILE.exists():
            logger.error(f"States file not found at {STATES_FILE}")
            raise FileNotFoundError("States file not found")

        with Path.open(STATES_FILE, encoding="utf-8") as f:
            states_data = json.load(f)

        # Filter states that have cities
        valid_states = {state_id: state_info for state_id, state_info in states_data.items() if state_info.get("cities") and len(state_info["cities"]) > 0}

        if not valid_states:
            logger.error("No states with cities found in states.json")
            raise ValueError("No valid states found")

        logger.debug(f"Found {len(valid_states)} states with cities for address generation")

        addresses_list = []
        address_id = 1  # Start ID counter for addresses

        for user in customer_users:
            # Generate 1-3 addresses per customer (some have multiple addresses)
            num_addresses = fake.random_int(min=1, max=3)

            for i in range(num_addresses):
                # Pick a random state that has cities
                state_id = fake.random_element(elements=list(valid_states.keys()))
                state_info = valid_states[state_id]
                state_name = state_info["name"]
                city = fake.random_element(elements=state_info["cities"])

                # Generate address components
                address1 = fake.street_address()
                address2 = fake.secondary_address() if fake.boolean(chance_of_getting_true=30) else None
                zipcode = fake.zipcode()

                # Use user's name or generate slight variations
                if i == 0:  # First address uses exact user name
                    firstname = user["first_name"]
                    lastname = user["last_name"]
                else:  # Additional addresses might be for family members
                    firstname = fake.first_name() if fake.boolean(chance_of_getting_true=40) else user["first_name"]
                    lastname = user["last_name"]  # Keep same last name for family

                # Generate phone numbers
                phone = fake.numerify("+1-###-###-####")
                alternative_phone = fake.numerify("+1-###-###-####") if fake.boolean(chance_of_getting_true=20) else None

                # Sometimes add company for business addresses
                company = fake.company() if fake.boolean(chance_of_getting_true=15) else None

                # Generate address labels
                if i == 0:
                    label = "Home"
                elif i == 1:
                    label = fake.random_element(elements=["Work", "Office", "Secondary", "Shipping"])
                else:
                    label = fake.random_element(elements=["Billing", "Gift", "Parents", "Vacation Home"])

                # Removed address metadata generation

                address = Address(
                    id=address_id,
                    firstname=firstname,
                    lastname=lastname,
                    address1=address1,
                    address2=address2,
                    city=city,
                    zipcode=zipcode,
                    phone=phone,
                    state_name=state_name,
                    alternative_phone=alternative_phone,
                    company=company,
                    state_id=int(state_id),
                    country_id=US_COUNTRY_ID,  # US country ID
                    user_id=user["id"],
                    user_email=user["email"],
                    label=label,
                )

                # Increment address ID for next address
                address_id += 1

                addresses_list.append(address.model_dump())

        addresses_dict = {"addresses": addresses_list}

        # Save to file
        settings.DATA_PATH.mkdir(parents=True, exist_ok=True)
        ADDRESSES_FILE.parent.mkdir(parents=True, exist_ok=True)
        with Path.open(ADDRESSES_FILE, "w", encoding="utf-8") as f:
            json.dump(addresses_dict, f, indent=2, ensure_ascii=False)

        return addresses_dict

    except Exception as e:
        logger.error(f"Error generating addresses: {e}")
        raise


async def seed_users():
    """Insert users into the database."""
    from apps.spree.utils.database import db_client

    logger.start("Inserting users into spree_users and spree_role_users tables...")

    try:
        # Load users from JSON file
        if not USERS_FILE.exists():
            logger.error(f"Users file not found at {USERS_FILE}. Run generate command first.")
            raise FileNotFoundError("Users file not found")

        with Path.open(USERS_FILE, encoding="utf-8") as f:
            data = json.load(f)

        users = data.get("users", [])
        logger.info(f"Loaded {len(users)} users from {USERS_FILE}")

        # First, get all existing role IDs
        roles_query = "SELECT id, name FROM spree_roles WHERE name = ANY($1)"
        role_records = await db_client.fetch(roles_query, ROLES)
        role_id_map = {role["name"]: role["id"] for role in role_records}

        logger.info(f"Found {len(role_id_map)} roles in database: {list(role_id_map.keys())}")

        # Insert each user into the database
        inserted_count = 0
        for user in users:
            try:
                # Check if user with this ID already exists
                existing_user = await db_client.fetchrow("SELECT id FROM spree_users WHERE id = $1", user["id"])

                user_id = user["id"]  # Use the pre-generated ID
                if existing_user:
                    # Update existing user
                    await db_client.execute(
                        """
                        UPDATE spree_users
                        SET encrypted_password = $1, password_salt = $2, email = $3, first_name = $4, last_name = $5,
                            login = $6, authentication_token = $7, spree_api_key = $8, sign_in_count = $9,
                            failed_attempts = $10, last_request_at = $11, current_sign_in_at = $12,
                            last_sign_in_at = $13, current_sign_in_ip = $14, last_sign_in_ip = $15,
                            selected_locale = $16, remember_created_at = $17, updated_at = NOW()
                        WHERE id = $18
                        """,
                        user["encrypted_password"],
                        user["password_salt"],
                        user["email"],
                        user["first_name"],
                        user["last_name"],
                        user["login"],
                        user["authentication_token"],
                        user["spree_api_key"],
                        user["sign_in_count"],
                        user["failed_attempts"],
                        parse_datetime(user["last_request_at"]),
                        parse_datetime(user["current_sign_in_at"]),
                        parse_datetime(user["last_sign_in_at"]),
                        user["current_sign_in_ip"],
                        user["last_sign_in_ip"],
                        user["selected_locale"],
                        parse_datetime(user["remember_created_at"]),
                        user_id,
                    )
                    logger.info(f"Updated existing user: {user['email']} (ID: {user_id})")
                else:
                    # Insert new user with specified ID
                    await db_client.execute(
                        """
                        INSERT INTO spree_users (id, encrypted_password, password_salt, email, login,
                                               authentication_token, spree_api_key, sign_in_count, failed_attempts,
                                               last_request_at, current_sign_in_at, last_sign_in_at,
                                               current_sign_in_ip, last_sign_in_ip, first_name, last_name,
                                               selected_locale, remember_created_at, created_at, updated_at)
                        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17, $18, NOW(), NOW())
                        """,
                        user_id,
                        user["encrypted_password"],
                        user["password_salt"],
                        user["email"],
                        user["login"],
                        user["authentication_token"],
                        user["spree_api_key"],
                        user["sign_in_count"],
                        user["failed_attempts"],
                        parse_datetime(user["last_request_at"]),
                        parse_datetime(user["current_sign_in_at"]),
                        parse_datetime(user["last_sign_in_at"]),
                        user["current_sign_in_ip"],
                        user["last_sign_in_ip"],
                        user["first_name"],
                        user["last_name"],
                        user["selected_locale"],
                        parse_datetime(user["remember_created_at"]),
                    )

                # Handle role assignments
                if user["roles"] and user_id:
                    # First, remove existing role assignments for this user
                    await db_client.execute("DELETE FROM spree_role_users WHERE user_id = $1", user_id)

                    # Add new role assignments
                    for role_name in user["roles"]:
                        if role_name in role_id_map:
                            role_id = role_id_map[role_name]
                            await db_client.execute(
                                """
                                INSERT INTO spree_role_users (role_id, user_id, created_at, updated_at)
                                VALUES ($1, $2, NOW(), NOW())
                                """,
                                role_id,
                                user_id,
                            )
                        else:
                            logger.warning(f"Role '{role_name}' not found in database for user {user['email']}")

                inserted_count += 1

            except Exception as e:
                logger.error(f"Failed to insert/update user {user['email']}: {e}")
                continue

        logger.succeed(f"Successfully processed {inserted_count} users in the database")

        # Also seed addresses after users are seeded
        await seed_addresses()

    except Exception as e:
        logger.error(f"Error seeding users in database: {e}")
        raise


async def seed_addresses():
    """Insert addresses into the database."""
    from apps.spree.utils.database import db_client

    logger.start("Inserting addresses into spree_addresses table...")

    try:
        # Load addresses from JSON file
        if not ADDRESSES_FILE.exists():
            logger.error(f"Addresses file not found at {ADDRESSES_FILE}. Run generate command first.")
            raise FileNotFoundError("Addresses file not found")

        with Path.open(ADDRESSES_FILE, encoding="utf-8") as f:
            data = json.load(f)

        addresses = data.get("addresses", [])
        logger.info(f"Loaded {len(addresses)} addresses from {ADDRESSES_FILE}")

        # Insert each address into the database
        inserted_count = 0
        for address in addresses:
            try:
                user_id = address["user_id"]

                # Check if similar address already exists for this user
                existing_address = await db_client.fetchrow(
                    "SELECT id FROM spree_addresses WHERE user_id = $1 AND address1 = $2 AND city = $3", user_id, address["address1"], address["city"]
                )

                if existing_address:
                    # Update existing address
                    await db_client.execute(
                        """
                        UPDATE spree_addresses
                        SET firstname = $1, lastname = $2, address2 = $3, zipcode = $4, phone = $5,
                            state_name = $6, alternative_phone = $7, company = $8, state_id = $9,
                            country_id = $10, label = $11, updated_at = NOW()
                        WHERE id = $12
                        """,
                        address["firstname"],
                        address["lastname"],
                        address["address2"],
                        address["zipcode"],
                        address["phone"],
                        address["state_name"],
                        address["alternative_phone"],
                        address["company"],
                        address["state_id"],
                        address["country_id"],
                        address["label"],
                        existing_address["id"],
                    )
                else:
                    # Insert new address with pre-generated ID
                    await db_client.execute(
                        """
                        INSERT INTO spree_addresses (id, firstname, lastname, address1, address2, city, zipcode,
                                                   phone, state_name, alternative_phone, company, state_id,
                                                   country_id, user_id, label, created_at, updated_at, deleted_at)
                        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, NOW(), NOW(), $16)
                        """,
                        address["id"],
                        address["firstname"],
                        address["lastname"],
                        address["address1"],
                        address["address2"],
                        address["city"],
                        address["zipcode"],
                        address["phone"],
                        address["state_name"],
                        address["alternative_phone"],
                        address["company"],
                        address["state_id"],
                        address["country_id"],
                        user_id,
                        address["label"],
                        None,  # deleted_at
                    )

                inserted_count += 1

            except Exception as e:
                logger.error(f"Failed to insert/update address for user ID {address['user_id']}: {e}")
                continue

        logger.succeed(f"Successfully processed {inserted_count} addresses in the database")

        # Update the sequence to avoid future conflicts with auto-generated IDs
        if inserted_count > 0:
            max_id = max(address["id"] for address in addresses)
            await db_client.execute(f"SELECT setval('spree_addresses_id_seq', {max_id}, true)")

        # After inserting all addresses, update user ship_address_id and bill_address_id
        await update_user_address_references()

    except Exception as e:
        logger.error(f"Error seeding addresses in database: {e}")
        raise


async def update_user_address_references():
    """Update user ship_address_id and bill_address_id after addresses are seeded."""
    from apps.spree.utils.database import db_client

    logger.start("Updating user shipping and billing address references...")

    try:
        # Get all users with their addresses
        users_with_addresses = await db_client.fetch(
            """
            SELECT 
                u.id as user_id, 
                u.email, 
                a.id as address_id, 
                a.label
            FROM spree_users u
            JOIN spree_addresses a ON u.id = a.user_id
            ORDER BY u.id, a.label
        """
        )

        # Group addresses by user
        user_addresses = {}
        for record in users_with_addresses:
            if record["user_id"] not in user_addresses:
                user_addresses[record["user_id"]] = {"email": record["email"], "addresses": []}
            user_addresses[record["user_id"]]["addresses"].append({"id": record["address_id"], "label": record["label"]})

        # Update each user's ship_address_id and bill_address_id
        updated_count = 0
        for user_id, user_data in user_addresses.items():
            try:
                addresses = user_data["addresses"]
                if not addresses:
                    continue

                # Find shipping address (prefer "Home" or "Shipping" label)
                ship_address = None
                for addr in addresses:
                    if addr["label"] in ["Home", "Shipping"]:
                        ship_address = addr
                        break
                # If no preferred label found, use the first address
                if not ship_address and addresses:
                    ship_address = addresses[0]

                # Find billing address (prefer "Billing" label, fall back to shipping)
                bill_address = None
                for addr in addresses:
                    if addr["label"] == "Billing":
                        bill_address = addr
                        break
                # If no billing address found, use shipping address
                if not bill_address:
                    bill_address = ship_address

                # Update user with address references
                if ship_address or bill_address:
                    ship_address_id = ship_address["id"] if ship_address else None
                    bill_address_id = bill_address["id"] if bill_address else None

                    await db_client.execute(
                        """
                        UPDATE spree_users
                        SET ship_address_id = $1,
                            bill_address_id = $2,
                            updated_at = NOW()
                        WHERE id = $3
                    """,
                        ship_address_id,
                        bill_address_id,
                        user_id,
                    )

                    updated_count += 1

            except Exception as e:
                logger.error(f"Failed to update address references for user ID {user_id}: {e}")
                continue

        logger.succeed(f"Successfully updated {updated_count} users with shipping and billing address references")

    except Exception as e:
        logger.error(f"Error updating user address references: {e}")
        raise
