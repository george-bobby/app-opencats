import json
from datetime import datetime

from gotrue import AdminUserAttributes
from pydantic import BaseModel, Field

from apps.supabase.config.settings import settings
from apps.supabase.utils.faker import faker
from apps.supabase.utils.postgres import PostgresClient
from apps.supabase.utils.supabase import get_supabase_client
from common.logger import logger


users_file = settings.DATA_PATH.joinpath("generated", "users.json")


class UserData(BaseModel):
    # Authentication fields
    first_name: str = Field(description="The first name of the user")
    last_name: str = Field(description="The last name of the user")
    email: str = Field(description="The email address of the user")
    phone: str | None = Field(description="The phone number of the user", default=None)
    provider: str = Field(description="The authentication provider")
    providers: list[str] = Field(description="List of available providers for the user")
    created_at: str = Field(description="When the user was created")
    last_sign_in_at: str = Field(description="The last sign in datetime of the user")
    phone_confirm: bool = Field(description="Whether phone is confirmed", default=False)
    email_confirm: bool = Field(description="Whether email is confirmed", default=True)

    # Profile fields
    username: str | None = Field(description="The username of the user", default=None)
    website: str | None = Field(description="The user's website", default=None)
    age: int | None = Field(description="The user's age", default=None)
    gender: str | None = Field(description="The user's gender", default=None)
    height_cm: float | None = Field(description="The user's height in centimeters", default=None)
    current_weight_kg: float | None = Field(description="The user's current weight in kilograms", default=None)
    activity_level: str | None = Field(description="The user's activity level", default=None)
    goal_type: str | None = Field(description="The user's weight goal type", default=None)
    target_weight_kg: float | None = Field(description="The user's target weight in kilograms", default=None)
    daily_calorie_goal: int | None = Field(description="The user's daily calorie goal", default=None)
    is_active: bool = Field(description="Whether the user is active", default=True)
    onboarding_completed: bool = Field(description="Whether the user has completed onboarding", default=False)


async def generate_authentication_data(number_of_users: int):
    """Generate user data and save to JSON file"""
    if users_file.exists():
        logger.info(f"User data file already exists at {users_file}")
        logger.start("Loading existing user data...")

        try:
            with users_file.open() as f:
                existing_data = json.load(f)

            # Convert existing profile data to include auth fields
            users_data = []
            providers = ["email", "google", "github", "facebook", "apple"]

            for user in existing_data:
                # Extract email from id (which is currently the email)
                email = user["id"]
                first_name = user["first_name"]
                last_name = user["last_name"]

                # Generate auth fields
                provider = faker.random.choice(providers)
                phone = None
                phone_confirm = False
                if faker.pybool(80):
                    phone = faker.numerify("+1##########")
                    phone_confirm = True

                # Always generate new auth timestamps for consistency
                created_at = faker.date_time_between(start_date="-1y", end_date="now")
                last_sign_in_at = faker.date_time_between(start_date=created_at, end_date="now")

                # Create complete user data with both auth and profile fields
                user_data = UserData(
                    # Auth fields
                    first_name=first_name,
                    last_name=last_name,
                    email=email,
                    phone=phone,
                    provider=provider,
                    providers=list({*faker.random_elements(providers), provider}),
                    created_at=created_at.isoformat(),
                    last_sign_in_at=last_sign_in_at.isoformat(),
                    phone_confirm=phone_confirm,
                    email_confirm=faker.pybool(80),
                    # Profile fields (from existing data)
                    username=user["username"],
                    website=user.get("website"),
                    age=user["age"],
                    gender=user["gender"],
                    height_cm=user["height_cm"],
                    current_weight_kg=user["current_weight_kg"],
                    activity_level=user["activity_level"],
                    goal_type=user["goal_type"],
                    target_weight_kg=user["target_weight_kg"],
                    daily_calorie_goal=user["daily_calorie_goal"],
                    is_active=user["is_active"],
                    onboarding_completed=user["onboarding_completed"],
                )
                users_data.append(user_data)

            # Save enhanced data back to JSON file
            serializable_users = [user.model_dump() for user in users_data]
            with users_file.open("w") as f:
                json.dump(serializable_users, f, indent=2)

            logger.succeed(f"Enhanced {len(users_data)} existing users with authentication data")
            return

        except Exception as e:
            logger.error(f"Error processing existing user data: {e}")
            logger.info("Generating new user data...")

    # If we get here, either the file doesn't exist or there was an error
    # Generate completely new data
    logger.info(f"Generating {number_of_users} users data")
    # List of providers to simulate
    providers = ["email", "google", "github", "facebook", "apple"]
    users_data = []
    for _ in range(number_of_users):
        # Generate fake name components
        first_name = faker.first_name()
        last_name = faker.last_name()
        email = f"{first_name.lower()}.{last_name.lower()}{faker.random_number(digits=faker.random_int(min=0, max=4))}"
        email = f"{email}@{faker.free_email_domain()}"
        provider = faker.random.choice(providers)

        phone = None
        phone_confirm = False
        if faker.pybool(80):
            phone = faker.numerify("+1##########")
            phone_confirm = True

        email_confirm = faker.pybool(80)

        # Generate username based on name
        username_base = (first_name.lower() + last_name.lower()).replace(" ", "")
        username = username_base + str(faker.random_int(min=10, max=999))

        # Physical data for calorie calculations
        age = faker.random_int(min=18, max=70)
        gender = faker.random_element(elements=("male", "female", "other"))
        height_cm = faker.random_int(min=140, max=200)  # Realistic height range

        # Weight based on height (BMI between 18-35)
        height_m = height_cm / 100
        bmi = faker.random_int(min=18, max=35)
        current_weight_kg = round(bmi * (height_m**2), 1)

        # Health goals
        activity_level = faker.random_element(elements=("sedentary", "light", "moderate", "active", "very_active"))
        goal_type = faker.random_element(elements=("lose", "maintain", "gain"))

        # Target weight based on goal type
        if goal_type == "lose":
            target_weight_kg = round(current_weight_kg - faker.random_int(min=2, max=15), 1)
        elif goal_type == "gain":
            target_weight_kg = round(current_weight_kg + faker.random_int(min=2, max=10), 1)
        else:  # maintain
            target_weight_kg = current_weight_kg

        # Calculate daily calorie goal (simplified BMR calculation)
        bmr = 88.362 + 13.397 * current_weight_kg + 4.799 * height_cm - 5.677 * age if gender == "male" else 447.593 + 9.247 * current_weight_kg + 3.098 * height_cm - 4.33 * age

        # Activity multipliers
        activity_multipliers = {
            "sedentary": 1.2,
            "light": 1.375,
            "moderate": 1.55,
            "active": 1.725,
            "very_active": 1.9,
        }

        # Round to nearest 10 for user-friendly calorie goals
        daily_calorie_goal = round((bmr * activity_multipliers[activity_level]) / 10) * 10

        # Adjust calories based on goal
        if goal_type == "lose":
            daily_calorie_goal -= faker.random_int(min=200, max=500)
        elif goal_type == "gain":
            daily_calorie_goal += faker.random_int(min=200, max=500)

        created_at = faker.date_time_between(start_date="-1y", end_date="now")
        last_sign_in_at = faker.date_time_between(start_date=created_at, end_date="now")

        user_data = UserData(
            # Auth fields
            first_name=first_name,
            last_name=last_name,
            email=email,
            phone=phone,
            provider=provider,
            providers=list({*faker.random_elements(providers), provider}),
            created_at=created_at.isoformat(),
            last_sign_in_at=last_sign_in_at.isoformat(),
            phone_confirm=phone_confirm,
            email_confirm=email_confirm,
            # Profile fields
            username=username,
            website=faker.url() if faker.boolean(chance_of_getting_true=30) else None,
            age=age,
            gender=gender,
            height_cm=height_cm,
            current_weight_kg=current_weight_kg,
            activity_level=activity_level,
            goal_type=goal_type,
            target_weight_kg=target_weight_kg,
            daily_calorie_goal=daily_calorie_goal,
            is_active=faker.random_element(elements=(True, True, True, False)),  # 75% active
            onboarding_completed=faker.random_element(elements=(True, True, False)),  # 66% completed
        )

        users_data.append(user_data)

    # Save to JSON file
    serializable_users = [user.model_dump() for user in users_data]
    with users_file.open("w", encoding="utf-8") as f:
        json.dump(serializable_users, f, indent=2)
        logger.info(f"Stored {len(users_data)} users in {users_file}")
    logger.succeed(f"Generated {number_of_users} users data")


async def seed_authentication_users():
    """Add users to Supabase authentication from generated data"""
    supabase = await get_supabase_client()

    # Try to load from existing JSON file first
    users_data = None
    try:
        with users_file.open(encoding="utf-8") as f:
            users_data = [UserData(**user) for user in json.load(f)]
            logger.info(f"Loaded {len(users_data)} users from {users_file}")

    except FileNotFoundError:
        logger.error(f"Users file not found: {users_file}")
        logger.info("Please run generate_user_data() first to create user data")
        return
    except json.JSONDecodeError:
        logger.error(f"Invalid JSON format in {users_file}")
        return

    if users_data is None:
        logger.error("No user data available. Please generate user data first.")
        return

    # Get all existing users to lookup by email
    try:
        existing_users_response = await supabase.auth.admin.list_users(per_page=1000000)
        existing_users_by_email = {user.email: user for user in existing_users_response if user.email}
        logger.info(f"Found {len(existing_users_by_email)} existing users")
    except Exception as e:
        logger.error(f"Failed to fetch existing users: {e}")
        existing_users_by_email = {}

    # Create single PostgreSQL connection for all timestamp updates
    async with PostgresClient() as postgres:
        logger.start(f"Inserting {len(users_data)} users into Supabase authentication")
        for user_data in users_data:
            # Create auth user
            auth_attrs = {
                "email": user_data.email,
                "password": "password",
                "email_confirm": user_data.email_confirm,
                "user_metadata": {
                    "first_name": user_data.first_name,
                    "last_name": user_data.last_name,
                },
                "app_metadata": {
                    "provider": user_data.provider,
                    "providers": user_data.providers,
                },
            }

            if user_data.phone:
                auth_attrs["phone"] = user_data.phone
                auth_attrs["phone_confirm"] = user_data.phone_confirm

            auth_user = AdminUserAttributes(**auth_attrs)

            try:
                # Create auth user
                auth_response = await supabase.auth.admin.create_user(auth_user)

                # Update auth.users table with created_at and last_sign_in_at using reused connection
                try:
                    # Convert ISO strings to datetime objects
                    created_at_dt = datetime.fromisoformat(user_data.created_at.replace("Z", "+00:00"))
                    last_sign_in_at_dt = datetime.fromisoformat(user_data.last_sign_in_at.replace("Z", "+00:00"))

                    await postgres.execute(
                        """
                        UPDATE auth.users 
                        SET created_at = $1, 
                            last_sign_in_at = $2
                        WHERE id = $3
                        """,
                        created_at_dt,
                        last_sign_in_at_dt,
                        auth_response.user.id,
                    )
                except Exception as e:
                    logger.warning(f"Could not update auth timestamps for user {user_data.email}: {e}")

                # Create profile data
                profile_data = {
                    "id": auth_response.user.id,  # Use the actual Supabase user ID
                    "username": user_data.username,
                    "website": user_data.website,
                    "age": user_data.age,
                    "gender": user_data.gender,
                    "height_cm": user_data.height_cm,
                    "current_weight_kg": user_data.current_weight_kg,
                    "activity_level": user_data.activity_level,
                    "goal_type": user_data.goal_type,
                    "target_weight_kg": user_data.target_weight_kg,
                    "daily_calorie_goal": user_data.daily_calorie_goal,
                    "is_active": user_data.is_active,
                    "onboarding_completed": user_data.onboarding_completed,
                }

                # Update the users table with profile data
                await supabase.table("users").update(profile_data).eq("id", auth_response.user.id).execute()

            except Exception as e:
                if "already registered" in str(e):
                    # If user already exists, update their auth timestamps
                    existing_user = existing_users_by_email.get(user_data.email)

                    if existing_user:
                        try:
                            # Update auth.users table with timestamps using reused connection
                            # Convert ISO strings to datetime objects
                            created_at_dt = datetime.fromisoformat(user_data.created_at.replace("Z", "+00:00"))
                            last_sign_in_at_dt = datetime.fromisoformat(user_data.last_sign_in_at.replace("Z", "+00:00"))

                            await postgres.execute(
                                """
                                UPDATE auth.users 
                                SET created_at = $1, 
                                    last_sign_in_at = $2
                                WHERE id = $3
                                """,
                                created_at_dt,
                                last_sign_in_at_dt,
                                existing_user.id,
                            )

                            # Also update profile data
                            profile_data = {
                                "username": user_data.username,
                                "website": user_data.website,
                                "age": user_data.age,
                                "gender": user_data.gender,
                                "height_cm": user_data.height_cm,
                                "current_weight_kg": user_data.current_weight_kg,
                                "activity_level": user_data.activity_level,
                                "goal_type": user_data.goal_type,
                                "target_weight_kg": user_data.target_weight_kg,
                                "daily_calorie_goal": user_data.daily_calorie_goal,
                                "is_active": user_data.is_active,
                                "onboarding_completed": user_data.onboarding_completed,
                            }

                            await supabase.table("users").update(profile_data).eq("id", existing_user.id).execute()

                        except Exception as update_e:
                            logger.error(f"Error updating existing user {user_data.email}: {update_e}")
                    else:
                        logger.warning(f"Could not find existing user {user_data.email} in lookup table")
                else:
                    logger.error(f"Error creating user {user_data.email}: {e}")

    logger.succeed(f"Inserted {len(users_data)} users into authentication")
