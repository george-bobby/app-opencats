import json
import uuid
from datetime import datetime, time, timedelta

from pydantic import BaseModel, Field, field_validator

from apps.supabase.config.settings import settings
from apps.supabase.core.enums import (
    Location,
    LoggingMethodType,
    MealType,
)
from apps.supabase.utils.faker import faker
from apps.supabase.utils.supabase import get_supabase_client
from common.logger import logger


# Define file paths
MEAL_LOGS_FILE = settings.DATA_PATH / "generated" / "meal_logs.json"
MEALS_FILE = settings.DATA_PATH / "generated" / "meals.json"
USERS_FILE = settings.DATA_PATH / "generated" / "users.json"
IMAGES_FILE = settings.DATA_PATH / "generated" / "images.json"


# Remove the old enum classes since they're now imported from enums module


class MealLogData(BaseModel):
    id: str = Field(description="Log UUID")  # noqa: A003, RUF100
    created_at: str = Field(description="Creation timestamp")
    updated_at: str = Field(description="Last update timestamp")

    # Relationships
    user_id: str = Field(description="User UUID")
    meal_id: str = Field(description="Meal UUID")
    image_id: str | None = Field(default=None, description="Optional image UUID")

    # Consumption details
    logged_date: str = Field(description="Date of consumption (YYYY-MM-DD)")
    logged_time: str = Field(description="Time of consumption (HH:MM:SS)")
    portion_consumed: float = Field(description="Portion size consumed", gt=0)

    # Calculated nutrition (based on portion)
    calories_consumed: float = Field(description="Calories consumed", ge=0)
    protein_consumed_g: float = Field(default=0, description="Protein consumed in grams", ge=0)
    carbs_consumed_g: float = Field(default=0, description="Carbs consumed in grams", ge=0)
    fat_consumed_g: float = Field(default=0, description="Fat consumed in grams", ge=0)

    # Meal context
    meal_type: MealType = Field(description="Type of meal")
    notes: str | None = Field(default=None, description="Optional notes about the meal")
    location: str | None = Field(default=None, description="Location where meal was consumed")
    logging_method: LoggingMethodType = Field(default=LoggingMethodType.MANUAL, description="Method used to log the meal")

    # Metadata
    is_favorite: bool = Field(default=False, description="Whether this is a favorite meal log")
    confidence_score: float = Field(default=1.0, description="Confidence score for the log entry", ge=0, le=1.0)

    @field_validator("portion_consumed")
    @classmethod
    def validate_portion(cls, v):
        """Ensure portion is a reasonable value"""
        if v <= 0 or v > 10:  # Assuming no one eats more than 10 portions
            raise ValueError("Portion must be between 0 and 10")
        return round(v, 2)

    @field_validator("calories_consumed", "protein_consumed_g", "carbs_consumed_g", "fat_consumed_g")
    @classmethod
    def round_nutrition(cls, v):
        """Round nutrition values to 2 decimal places"""
        return round(v, 2)


def generate_meal_time(meal_type: MealType) -> time:
    """Generate a realistic time for a given meal type"""

    def random_time(start_hour: int, start_min: int, end_hour: int, end_min: int) -> time:
        """Generate a random time between two times"""
        start_minutes = start_hour * 60 + start_min
        end_minutes = end_hour * 60 + end_min
        random_minutes = faker.random_int(min=start_minutes, max=end_minutes)
        hour = random_minutes // 60
        minute = random_minutes % 60
        return time(hour=hour, minute=minute)

    if meal_type == MealType.BREAKFAST:
        return random_time(6, 0, 10, 0)  # 6:00 - 10:00
    elif meal_type == MealType.LUNCH:
        return random_time(11, 30, 14, 0)  # 11:30 - 14:00
    elif meal_type == MealType.DINNER:
        return random_time(17, 30, 21, 0)  # 17:30 - 21:00
    elif meal_type == MealType.SNACK:
        # Snacks can be mid-morning or mid-afternoon
        if faker.boolean():
            return random_time(10, 0, 11, 30)  # 10:00 - 11:30
        return random_time(14, 0, 17, 30)  # 14:00 - 17:30
    elif meal_type == MealType.DRINK:
        # Drinks can be throughout the day
        return random_time(8, 0, 22, 0)  # 8:00 - 22:00
    else:  # DESSERT
        # Desserts usually after lunch or dinner
        if faker.boolean():
            return random_time(13, 0, 15, 0)  # 13:00 - 15:00
        return random_time(19, 0, 22, 0)  # 19:00 - 22:00


def generate_realistic_notes(meal_type: MealType, location: str) -> str | None:
    """Generate realistic notes for a meal log"""
    if not faker.boolean(30):  # 30% chance of having notes
        return None

    notes_templates = {
        MealType.BREAKFAST: [
            "Quick breakfast before work",
            "Healthy start to the day",
            "Weekend brunch",
            "Light morning meal",
            "Protein-packed breakfast",
        ],
        MealType.LUNCH: [
            "Business lunch meeting",
            "Quick lunch break",
            "Meal prep lunch",
            "Light lunch today",
            "Working lunch",
        ],
        MealType.DINNER: [
            "Family dinner",
            "Date night",
            "Cooked at home",
            "Trying new recipe",
            "Leftover dinner",
        ],
        MealType.SNACK: [
            "Afternoon energy boost",
            "Pre-workout snack",
            "Post-workout protein",
            "Quick bite",
            "Healthy snack",
        ],
        MealType.DRINK: [
            "Morning coffee",
            "Afternoon tea",
            "Post-workout shake",
            "Staying hydrated",
            "Protein smoothie",
        ],
        MealType.DESSERT: [
            "Special treat",
            "Birthday celebration",
            "Sweet craving",
            "Sharing dessert",
            "Light dessert",
        ],
    }

    # Add location context if not home
    location_context = {
        "restaurant": [
            "Nice atmosphere",
            "Great service",
            "Will come back",
            "First time here",
            "Regular spot",
        ],
        "office": [
            "Quick office lunch",
            "Team lunch",
            "Busy day",
            "Working lunch",
            "Office cafeteria",
        ],
        "cafe": [
            "Cozy cafe",
            "Working remotely",
            "Coffee break",
            "Meeting friend",
            "Regular spot",
        ],
    }

    note = faker.random.choice(notes_templates[meal_type])
    if location.lower() in location_context and faker.boolean():
        note += f". {faker.random.choice(location_context[location.lower()])}"

    return note


async def generate_meal_logs_data(number_of_logs: int = 750):
    """Generate meal log data and save to JSON file"""

    logger.info(f"Generating {number_of_logs} meal logs data")

    # Load required data
    try:
        # Load meals data
        with MEALS_FILE.open() as f:
            meals_data = json.load(f)
            meal_ids = [meal["id"] for meal in meals_data]
            logger.info(f"Loaded {len(meal_ids)} meals")

        # Load users data
        with USERS_FILE.open() as f:
            users_data = json.load(f)
            logger.info(f"Loaded {len(users_data)} users")

        # Load images data (optional)
        try:
            with IMAGES_FILE.open() as f:
                images_data = json.load(f)
                image_ids = [image["id"] for image in images_data]
                logger.info(f"Loaded {len(image_ids)} images")
        except (FileNotFoundError, json.JSONDecodeError):
            image_ids = []
            logger.warning("No images data found, logs will not be linked to images")

    except FileNotFoundError as e:
        logger.error(f"Required data file not found: {e}")
        return
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON in data file: {e}")
        return

    # Generate logs
    logs_data = []
    end_date = datetime.now()
    start_date = end_date - timedelta(days=90)  # Generate logs for the past 90 days

    for _ in range(number_of_logs):
        # Generate log date and time
        log_date = faker.date_between(start_date=start_date, end_date=end_date)
        meal_type = faker.random.choice(list(MealType))
        log_time = generate_meal_time(meal_type)

        # Generate portion and method
        portion = round(faker.random.uniform(0.5, 2.0), 2)
        logging_method = faker.random.choice(list(LoggingMethodType))

        # Determine if this log should have an image
        has_image = logging_method == LoggingMethodType.PHOTO and image_ids and faker.boolean(70)
        image_id = faker.random.choice(image_ids) if has_image else None

        # Generate location and notes
        location = faker.random.choice(list(Location))
        notes = generate_realistic_notes(meal_type, location)

        # Create log entry
        log = MealLogData(
            id=str(uuid.uuid4()),
            created_at=faker.date_time_between(start_date=log_date, end_date=log_date + timedelta(minutes=30)).isoformat(),
            updated_at=faker.date_time_between(start_date=log_date, end_date=log_date + timedelta(minutes=30)).isoformat(),
            user_id="placeholder",  # Will be replaced during seeding
            meal_id=faker.random.choice(meal_ids),
            image_id=image_id,
            logged_date=log_date.strftime("%Y-%m-%d"),
            logged_time=log_time.strftime("%H:%M:%S"),
            portion_consumed=portion,
            calories_consumed=0,  # Will be calculated by trigger
            protein_consumed_g=0,  # Will be calculated by trigger
            carbs_consumed_g=0,  # Will be calculated by trigger
            fat_consumed_g=0,  # Will be calculated by trigger
            meal_type=meal_type,
            notes=notes,
            location=location,
            logging_method=logging_method,
            is_favorite=faker.boolean(20),  # 20% chance of being favorite
            confidence_score=1.0 if logging_method == LoggingMethodType.MANUAL else round(faker.random.uniform(0.7, 0.98), 2),
        )
        logs_data.append(log)

    # Save to JSON file
    serializable_logs = [log.model_dump() for log in logs_data]
    with MEAL_LOGS_FILE.open("w") as f:
        json.dump(serializable_logs, f, indent=2)
        logger.info(f"Stored {len(logs_data)} meal logs in {MEAL_LOGS_FILE}")

    logger.succeed(f"Generated {number_of_logs} meal logs data")


async def seed_meal_logs_data():
    """Insert meal logs into Supabase logs table from generated data"""
    supabase = await get_supabase_client()

    # Try to load from existing JSON file first
    try:
        with MEAL_LOGS_FILE.open() as f:
            logs_data = [MealLogData(**log) for log in json.load(f)]
            logger.info(f"Loaded {len(logs_data)} meal logs from {MEAL_LOGS_FILE}")
    except FileNotFoundError:
        logger.error(f"Meal logs file not found: {MEAL_LOGS_FILE}")
        logger.info("Please run generate_meal_logs_data() first to create meal logs data")
        return
    except json.JSONDecodeError:
        logger.error(f"Invalid JSON format in {MEAL_LOGS_FILE}")
        return

    # Get all user UUIDs from auth.admin.list_users
    try:
        response = await supabase.auth.admin.list_users(per_page=1000000)
        users_data = response
        user_uuids = [user.id for user in users_data]
        if not user_uuids:
            logger.error("No users found in the database")
            return
        logger.info(f"Found {len(user_uuids)} users in the database")
    except Exception as e:
        logger.error(f"Failed to fetch user UUIDs: {e}")
        return

    logger.start(f"Inserting {len(logs_data)} meal logs into Supabase logs table")

    for log in logs_data:
        # Assign a random user UUID
        log.user_id = faker.random.choice(user_uuids)

        try:
            # Insert log record
            await supabase.table("logs").insert(log.model_dump()).execute()
        except Exception as e:
            if "duplicate key value" in str(e) or "already exists" in str(e):
                pass
            else:
                logger.error(f"Error inserting log {log.id}: {e}")

    logger.succeed(f"Inserted {len(logs_data)} meal logs into logs table")
