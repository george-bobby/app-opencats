import json
import uuid
from pathlib import Path

from apps.supabase.config.settings import settings
from apps.supabase.core.enums import (
    ActivityLevelType,
    DateFormatType,
    GenderType,
    GoalType,
    ThemePreferenceType,
    TimeFormatType,
    UnitsSystemType,
    get_enum_values,
)
from apps.supabase.utils.faker import faker
from apps.supabase.utils.supabase import get_supabase_client
from common.logger import logger


# Define the path to the generated users data file
USERS_DATA_FILE = settings.DATA_PATH / "generated" / "users.json"


async def generate_users_data():
    """
    Generate fake user data for existing users and save to users.json.
    Reads base user data from users.json and enhances it with additional fields.
    Based on schema from 01_users.sql
    """
    if USERS_DATA_FILE.exists():
        logger.info(f"User data file already exists at {USERS_DATA_FILE}")
        logger.start("Loading existing user data...")
        with Path.open(USERS_DATA_FILE) as f:
            existing_users = json.load(f)
    else:
        logger.error(f"Users data file not found at {USERS_DATA_FILE}")
        return

    if not existing_users:
        logger.info("No users found in users.json")
        return

    num_users = len(existing_users)
    logger.info(f"Found {num_users} users to generate data for")
    logger.start(f"Generating fake data for {num_users} users...")

    # Generate realistic sample data for each existing user
    generated_users = []

    for user in existing_users:
        # Preserve existing authentication fields
        user_data = {
            "email": user["email"],
            "first_name": user["first_name"],
            "last_name": user["last_name"],
            "provider": user["provider"],
            "providers": user["providers"],
            "created_at": user["created_at"],
            "last_sign_in_at": user.get("last_sign_in_at"),  # Preserve last_sign_in_at
            "phone": user.get("phone"),  # Optional field
            "phone_confirm": user.get("phone_confirm", False),
            "email_confirm": user.get("email_confirm", False),
        }

        # Generate username based on existing first and last name
        username_base = (user["first_name"].lower() + user["last_name"].lower()).replace(" ", "")
        user_data["username"] = username_base + str(faker.random_int(min=10, max=999))

        # Physical data for calorie calculations
        user_data["age"] = faker.random_int(min=18, max=70)
        user_data["gender"] = faker.random_element(elements=get_enum_values(GenderType))
        user_data["height_cm"] = faker.random_int(min=140, max=200)  # Realistic height range

        # Weight based on height (BMI between 18-35)
        height_m = user_data["height_cm"] / 100
        bmi = faker.random_int(min=18, max=35)
        user_data["current_weight_kg"] = round(bmi * (height_m**2), 1)

        # Health goals
        user_data["activity_level"] = faker.random_element(elements=get_enum_values(ActivityLevelType))
        user_data["goal_type"] = faker.random_element(elements=get_enum_values(GoalType))

        # Target weight based on goal type
        if user_data["goal_type"] == GoalType.LOSE.value:
            user_data["target_weight_kg"] = round(user_data["current_weight_kg"] - faker.random_int(min=2, max=15), 1)
        elif user_data["goal_type"] == GoalType.GAIN.value:
            user_data["target_weight_kg"] = round(user_data["current_weight_kg"] + faker.random_int(min=2, max=10), 1)
        else:  # maintain
            user_data["target_weight_kg"] = user_data["current_weight_kg"]

        # Calculate daily calorie goal (simplified BMR calculation)
        if user_data["gender"] == GenderType.MALE.value:
            bmr = 88.362 + (13.397 * user_data["current_weight_kg"]) + (4.799 * user_data["height_cm"]) - (5.677 * user_data["age"])
        else:
            bmr = 447.593 + (9.247 * user_data["current_weight_kg"]) + (3.098 * user_data["height_cm"]) - (4.330 * user_data["age"])

        # Activity multipliers
        activity_multipliers = {
            ActivityLevelType.SEDENTARY.value: 1.2,
            ActivityLevelType.LIGHT.value: 1.375,
            ActivityLevelType.MODERATE.value: 1.55,
            ActivityLevelType.ACTIVE.value: 1.725,
            ActivityLevelType.VERY_ACTIVE.value: 1.9,
        }

        # Round to nearest 10 for user-friendly calorie goals (e.g., 1480 instead of 1473)
        daily_calorie_goal = round((bmr * activity_multipliers[user_data["activity_level"]]) / 10) * 10

        # Adjust calories based on goal
        if user_data["goal_type"] == GoalType.LOSE.value:
            daily_calorie_goal -= faker.random_int(min=200, max=500)
        elif user_data["goal_type"] == GoalType.GAIN.value:
            daily_calorie_goal += faker.random_int(min=200, max=500)

        user_data["daily_calorie_goal"] = daily_calorie_goal

        # Account status and website
        user_data["is_active"] = faker.random_element(elements=(True, True, True, False))  # 75% active
        user_data["onboarding_completed"] = faker.random_element(elements=(True, True, False))  # 66% completed

        # Generate social media profile URL (30% chance)
        if faker.boolean(chance_of_getting_true=30):
            platform = faker.random.choice(["instagram", "tiktok", "facebook", "twitter", "linkedin"])
            username = f"{user_data['first_name'].lower()}{user_data['last_name'].lower()}{faker.random_int(min=1, max=999)}"

            if platform == "instagram":
                user_data["website"] = f"https://instagram.com/{username}"
            elif platform == "tiktok":
                user_data["website"] = f"https://tiktok.com/@{username}"
            elif platform == "facebook":
                user_data["website"] = f"https://facebook.com/{username}"
            elif platform == "twitter":
                user_data["website"] = f"https://twitter.com/{username}"
            else:  # linkedin
                user_data["website"] = f"https://linkedin.com/in/{username}"
        else:
            user_data["website"] = None

        generated_users.append(user_data)

    logger.succeed(f"Generated fake data for {len(generated_users)} user records")

    # Save generated data to JSON file
    with Path.open(USERS_DATA_FILE, "w") as f:
        json.dump(generated_users, f, indent=2)

    logger.succeed(f"Saved generated user data to {USERS_DATA_FILE}")
    return generated_users


async def seed_users_data():
    """
    Seed the database with user data from the generated JSON file.
    Updates existing users in the database with their generated data.
    """
    if not USERS_DATA_FILE.exists():
        logger.error(f"Users data file not found at {USERS_DATA_FILE}")
        return

    logger.start("Loading generated user data...")
    with Path.open(USERS_DATA_FILE) as f:
        users_data = json.load(f)

    if not users_data:
        logger.info("No user data found in JSON file")
        return

    logger.succeed(f"Found {len(users_data)} users to seed")
    logger.start("Updating existing users in database...")

    supabase = await get_supabase_client()
    successful_updates = 0

    # Get all users from auth.users to get their IDs
    try:
        response = await supabase.auth.admin.list_users(per_page=1000000)
        auth_users = {user.email: user.id for user in response}
    except Exception as e:
        logger.error(f"Failed to fetch user IDs: {e}")
        return

    logger.start(f"Updating {len(users_data)} users in database...")
    for user in users_data:
        try:
            email = user.get("email")
            if not email:
                logger.warning("No email found for user, skipping")
                continue

            # Get the actual UUID from auth.users
            auth_user_id = auth_users.get(email)
            if not auth_user_id:
                logger.warning(f"Could not find UUID for user {email}, skipping")
                continue

            # Prepare update data
            update_data = {
                "first_name": user["first_name"],
                "last_name": user["last_name"],
                "username": user["username"],  # Use the generated username from the JSON file
                "is_active": True,
                "onboarding_completed": True,
            }

            # Update user record using Supabase client
            await supabase.table("users").update(update_data).eq("id", auth_user_id).execute()
            successful_updates += 1

        except Exception as e:
            logger.warning(f"Failed to update user {user.get('email', 'unknown')}: {e!s}")
            continue

    logger.succeed(f"Successfully updated {successful_updates}/{len(users_data)} existing users")


async def clear_users_data():
    """
    Clear personal data from existing users in the public.users table (keeps IDs intact)
    """
    logger.info("Clearing user data (keeping records)...")

    supabase = await get_supabase_client()

    # Get all user IDs first
    response = await supabase.table("users").select("id").execute()

    if response.data:
        # Clear data for all users
        clear_data = {
            "username": None,
            "first_name": None,
            "last_name": None,
            "website": None,
            "age": None,
            "gender": None,
            "height_cm": None,
            "current_weight_kg": None,
            "activity_level": ActivityLevelType.MODERATE.value,
            "goal_type": GoalType.MAINTAIN.value,
            "target_weight_kg": None,
            "daily_calorie_goal": None,
            "is_active": True,
            "onboarding_completed": False,
        }

        # Update all users with cleared data
        for user in response.data:
            await supabase.table("users").update(clear_data).eq("id", user["id"]).execute()

    logger.succeed("User data cleared (records preserved)")


async def generate_user_preferences_data():
    """Generate user preferences data and save to JSON file"""
    users_file = settings.DATA_PATH.joinpath("generated", "users.json")
    preferences_file = settings.DATA_PATH.joinpath("generated", "user_preferences.json")

    # Load existing users data
    try:
        with users_file.open(encoding="utf-8") as f:
            users_data = json.load(f)
            logger.info(f"Loaded {len(users_data)} users from {users_file}")
    except FileNotFoundError:
        logger.error(f"Users file not found: {users_file}")
        return
    except json.JSONDecodeError:
        logger.error(f"Invalid JSON format in {users_file}")
        return

    preferences_data = []
    dietary_restrictions = ["vegetarian", "vegan", "gluten-free", "dairy-free", "nut-free", "halal", "kosher"]
    cuisines = ["italian", "japanese", "mexican", "indian", "chinese", "thai", "mediterranean", "french", "american"]
    common_foods = ["mushrooms", "olives", "seafood", "spicy_food", "cilantro", "blue_cheese", "raw_onions"]

    for user in users_data:
        # Generate random preferences for each user
        preference = {
            "id": str(uuid.uuid4()),
            "username": user["username"],  # Store username instead of user_id
            "created_at": faker.date_time_between(start_date="-1y", end_date="now").isoformat(),
            "updated_at": faker.date_time_between(start_date="-1m", end_date="now").isoformat(),
            # System & Display Preferences
            "timezone": faker.random.choice(["UTC", "America/New_York", "Europe/London", "Asia/Tokyo", "Australia/Sydney"]),
            "units_system": faker.random.choice(get_enum_values(UnitsSystemType)),
            "preferred_date_format": faker.random.choice(get_enum_values(DateFormatType)),
            "preferred_time_format": faker.random.choice(get_enum_values(TimeFormatType)),
            "theme_preference": faker.random.choice(get_enum_values(ThemePreferenceType)),
            # App Behavior Settings
            "auto_log_favorites": faker.pybool(70),  # 70% true
            "enable_barcode_scanning": faker.pybool(80),
            "enable_photo_analysis": faker.pybool(85),
            "enable_voice_logging": faker.pybool(30),
            # Tracking Preferences
            "track_macros": faker.pybool(75),
            "track_water": faker.pybool(80),
            "track_exercise": faker.pybool(60),
            "daily_water_goal_ml": faker.random_int(min=1500, max=4000, step=100),
            # Dietary Preferences & Restrictions
            "dietary_restrictions": faker.random.sample(dietary_restrictions, k=faker.random_int(min=0, max=2)),
            "allergies": faker.random.sample(common_foods, k=faker.random_int(min=0, max=2)),
            "preferred_cuisines": faker.random.sample(cuisines, k=faker.random_int(min=2, max=5)),
            "disliked_foods": faker.random.sample(common_foods, k=faker.random_int(min=0, max=3)),
            # Notification Settings
            "enable_meal_reminders": faker.pybool(75),
            "enable_water_reminders": faker.pybool(70),
            "enable_goal_notifications": faker.pybool(80),
            "enable_achievement_notifications": faker.pybool(85),
            "breakfast_reminder_time": faker.time_object().strftime("%H:%M:%S") if faker.pybool(80) else None,
            "lunch_reminder_time": faker.time_object().strftime("%H:%M:%S") if faker.pybool(80) else None,
            "dinner_reminder_time": faker.time_object().strftime("%H:%M:%S") if faker.pybool(80) else None,
            "water_reminder_interval_minutes": faker.random_int(min=60, max=240, step=30),
            # Privacy Settings
            "make_profile_public": faker.pybool(40),
            "share_achievements": faker.pybool(70),
            "allow_friend_requests": faker.pybool(75),
            # Data Management
            "auto_backup_enabled": faker.pybool(90),
            "last_backup_date": faker.date_time_between(start_date="-3m", end_date="now").isoformat() if faker.pybool(80) else None,
            "data_retention_days": faker.random_int(min=90, max=730, step=30),
        }
        preferences_data.append(preference)

    # Save to JSON file
    with preferences_file.open("w", encoding="utf-8") as f:
        json.dump(preferences_data, f, indent=2)
        logger.info(f"Stored {len(preferences_data)} user preferences in {preferences_file}")

    logger.succeed(f"Generated {len(preferences_data)} user preferences data")


async def seed_user_preferences_data():
    """Update user preferences in Supabase from generated data"""
    preferences_file = settings.DATA_PATH.joinpath("generated", "user_preferences.json")
    supabase = await get_supabase_client()

    # Try to load from existing JSON file
    try:
        with preferences_file.open(encoding="utf-8") as f:
            preferences_data = json.load(f)
            logger.info(f"Loaded {len(preferences_data)} user preferences from {preferences_file}")
    except FileNotFoundError:
        logger.error(f"User preferences file not found: {preferences_file}")
        logger.info("Please run generate_user_preferences_data() first")
        return
    except json.JSONDecodeError:
        logger.error(f"Invalid JSON format in {preferences_file}")
        return

    # Get all users from public.users table to get username mapping
    try:
        response = await supabase.table("users").select("id, username").execute()
        public_users = response.data
        username_to_id = {user["username"]: user["id"] for user in public_users if user["username"]}
        logger.info(f"Found {len(public_users)} users in public.users")
    except Exception as e:
        logger.error(f"Failed to fetch public users: {e}")
        return

    logger.start(f"Updating {len(preferences_data)} user preferences in Supabase")
    successful_updates = 0

    for preference in preferences_data:
        username = preference.pop("username")  # Remove username from the data
        user_id = username_to_id.get(username)

        if not user_id:
            logger.warning(f"User not found for username: {username}")
            continue

        preference["user_id"] = user_id  # Add the looked-up user_id

        try:
            # Update existing preference for the user
            await supabase.table("user_preferences").update(preference).eq("user_id", user_id).execute()
            successful_updates += 1
        except Exception as e:
            logger.error(f"Error updating preference for user {username}: {e}")

    logger.succeed(f"Successfully updated {successful_updates} user preferences")
