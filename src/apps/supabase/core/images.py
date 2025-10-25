import json
import uuid
from datetime import datetime, timedelta
from pathlib import Path

from pydantic import BaseModel, Field

from apps.supabase.config.settings import settings
from apps.supabase.core.enums import (
    AIProcessingStatusType,
    ImageType,
    MimeType,
    ModerationStatusType,
)
from apps.supabase.utils.faker import faker
from apps.supabase.utils.supabase import get_supabase_client
from common.logger import logger


images_file = settings.DATA_PATH.joinpath("generated", "images.json")
meals_file = settings.DATA_PATH.joinpath("generated", "meals.json")
users_file = settings.DATA_PATH.joinpath("generated", "users.json")


class ImageData(BaseModel):
    id: str = Field(description="Image UUID")  # noqa: A003, RUF100
    created_at: str = Field(description="Creation timestamp")
    updated_at: str = Field(description="Last update timestamp")

    # Image storage information
    url: str = Field(description="Image URL")
    filename: str = Field(description="Original filename")
    file_size_bytes: int = Field(description="File size in bytes", gt=0)
    mime_type: MimeType = Field(description="MIME type of the image")

    # Image dimensions
    width: int = Field(description="Image width in pixels", gt=0)
    height: int = Field(description="Image height in pixels", gt=0)

    # Relationships
    meal_id: str | None = Field(default=None, description="Associated meal UUID")
    uploaded_by: str | None = Field(default=None, description="User UUID who uploaded the image")
    uploaded_by_user: str = Field(description="Username of the user who uploaded the image")

    # AI Analysis results
    ai_detected_foods: list[str] | None = Field(default=None, description="Array of detected food items")
    ai_confidence_score: float | None = Field(default=None, description="AI confidence score (0-1)", ge=0, le=1)
    ai_estimated_calories: float | None = Field(default=None, description="AI estimated calories", ge=0)
    ai_processing_status: AIProcessingStatusType = Field(default=AIProcessingStatusType.PENDING, description="AI processing status")
    ai_processed_at: str | None = Field(default=None, description="AI processing completion timestamp")

    # Image categorization
    image_type: ImageType = Field(default=ImageType.MEAL_PHOTO, description="Type of image")
    tags: list[str] | None = Field(default=None, description="User or AI generated tags")

    # Quality and metadata
    is_public: bool = Field(default=False, description="Whether image is publicly visible")
    is_verified: bool = Field(default=False, description="Whether image is verified")
    blur_hash: str | None = Field(default=None, description="BlurHash for progressive loading")
    exif_data: dict | None = Field(default=None, description="Camera/device metadata")

    # Moderation
    is_flagged: bool = Field(default=False, description="Whether image is flagged for review")
    moderation_status: ModerationStatusType = Field(default=ModerationStatusType.APPROVED, description="Moderation status")

    # Storage metadata
    storage_bucket: str = Field(default="meal-images", description="Storage bucket name")
    storage_path: str | None = Field(default=None, description="Storage path within bucket")
    cdn_url: str | None = Field(default=None, description="CDN URL for the image")


def generate_realistic_filename(image_type: ImageType) -> str:
    """Generate a realistic filename based on image type"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    device = faker.random.choice(["iPhone", "Pixel", "Galaxy", "Canon", "Nikon"])
    number = faker.random_int(min=1000, max=9999)

    if image_type == ImageType.MEAL_PHOTO:
        prefix = "MEAL"
    elif image_type == ImageType.INGREDIENT_PHOTO:
        prefix = "INGR"
    elif image_type == ImageType.NUTRITION_LABEL:
        prefix = "NUTRI"
    else:
        prefix = "RCPT"

    return f"{prefix}_{timestamp}_{device}_{number}.jpg"


def generate_realistic_exif_data() -> dict:
    """Generate realistic EXIF metadata"""
    devices = [
        {
            "make": "Apple",
            "models": ["iPhone 13 Pro", "iPhone 14 Pro Max", "iPhone 15", "iPhone 15 Pro"],
        },
        {
            "make": "Samsung",
            "models": ["Galaxy S23", "Galaxy S23 Ultra", "Galaxy Z Fold 5", "Galaxy A54"],
        },
        {
            "make": "Google",
            "models": ["Pixel 7", "Pixel 7 Pro", "Pixel 8", "Pixel 8 Pro"],
        },
        {
            "make": "Canon",
            "models": ["EOS R5", "EOS R6", "EOS 90D", "PowerShot G7 X"],
        },
    ]

    device = faker.random.choice(devices)
    make = device["make"]
    model = faker.random.choice(device["models"])

    return {
        "Make": make,
        "Model": model,
        "Software": f"{make} Camera v{faker.random_int(min=1, max=15)}.{faker.random_int(min=0, max=9)}",
        "DateTime": faker.date_time_between(start_date="-1y", end_date="now").strftime("%Y:%m:%d %H:%M:%S"),
        "ExposureTime": f"1/{faker.random_int(min=30, max=2000)}",
        "FNumber": f"f/{faker.random.choice(['1.8', '2.0', '2.4', '2.8', '4.0'])}",
        "ISO": str(faker.random.choice([100, 200, 400, 800, 1600, 3200])),
        "FocalLength": f"{faker.random.choice([24, 28, 35, 50, 85])} mm",
        "Flash": "No Flash",
        "ImageWidth": faker.random_int(min=2000, max=4000),
        "ImageHeight": faker.random_int(min=2000, max=4000),
    }


def generate_realistic_blur_hash() -> str:
    """Generate a realistic BlurHash string"""
    # BlurHash is typically 4-5 characters for X components and 3-4 characters for Y components
    # Followed by actual hash characters
    components = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz#$%*+,-.:;=?@[]^_{|}~"
    length = faker.random_int(min=20, max=30)
    return "".join(faker.random.choices(components, k=length))


def generate_realistic_tags(image_type: str, ai_detected_foods: list | None = None) -> list:
    """Generate realistic tags based on image type and AI detected foods"""
    tags = []

    if image_type == ImageType.MEAL_PHOTO:
        # Add meal-specific tags
        tags.extend(
            faker.random.sample(["breakfast", "lunch", "dinner", "healthy", "delicious", "homemade", "restaurant", "meal_prep", "foodie", "plating"], k=faker.random_int(min=1, max=3))
        )

        # Add detected foods as tags
        if ai_detected_foods:
            tags.extend(ai_detected_foods)

    elif image_type == ImageType.NUTRITION_LABEL:
        tags.extend(faker.random.sample(["nutrition_facts", "ingredients_list", "allergens", "serving_size", "calories", "macros", "product_label"], k=faker.random_int(min=2, max=4)))

    elif image_type == ImageType.INGREDIENT_PHOTO:
        tags.extend(faker.random.sample(["fresh", "organic", "raw", "produce", "ingredients", "cooking", "preparation", "quality"], k=faker.random_int(min=2, max=4)))

    return list(set(tags))  # Remove any duplicates


def generate_realistic_storage_path(image_type: ImageType, user_id: str) -> str:
    """Generate a realistic storage path for the image"""
    year_month = datetime.now().strftime("%Y/%m")
    return f"users/{user_id}/{image_type.value}/{year_month}/{uuid.uuid4()}"


def generate_realistic_url(storage_path: str) -> str:
    """Generate a realistic URL for the image"""
    cdn_domain = "cdn.foodtracker.example.com"
    return f"https://{cdn_domain}/{storage_path}"


async def generate_images_data(number_of_images: int = 1000):
    """Generate image data and save to JSON file"""

    logger.info(f"Generating {number_of_images} images data")

    # Load uploaded images metadata
    uploaded_images_file = settings.DATA_PATH / "uploaded_images.json"
    try:
        with uploaded_images_file.open() as f:
            uploaded_images = json.load(f)
            logger.info(f"Loaded {len(uploaded_images)} uploaded images metadata")
    except (FileNotFoundError, json.JSONDecodeError):
        logger.error("No uploaded images metadata found. Please run upload_sample_images() first")
        return

    # Load meals data for linking
    try:
        with meals_file.open(encoding="utf-8") as f:
            meals_data = json.load(f)
            meal_ids = [meal["id"] for meal in meals_data]
    except (FileNotFoundError, json.JSONDecodeError):
        meal_ids = []
        logger.warning("No meals data found, images will not be linked to meals")

    # Load users data for usernames
    usernames = []
    try:
        with Path.open(users_file) as f:
            users_data = json.load(f)
            usernames = [f"{user['first_name'].lower()}.{user['last_name'].lower()}" for user in users_data]
            logger.info(f"Found {len(usernames)} users in users.json")
        if not usernames:
            logger.warning("No users found in users.json, images will not be linked to users")
    except (FileNotFoundError, json.JSONDecodeError) as e:
        logger.warning(f"Failed to load users from {users_file}: {e}, images will not be linked to users")

    images_data = []
    for _ in range(number_of_images):
        # Select a random uploaded image
        uploaded_image = faker.random.choice(uploaded_images)

        # Generate core image data
        image_type = faker.random.choice(
            [
                ImageType.MEAL_PHOTO,
                ImageType.MEAL_PHOTO,
                ImageType.MEAL_PHOTO,  # 60% chance of meal photo
                ImageType.NUTRITION_LABEL,
                ImageType.INGREDIENT_PHOTO,  # 40% chance of other types
            ]
        )
        uploaded_by_user = faker.random.choice(usernames) if usernames else None

        # Use the actual uploaded image data
        url = uploaded_image["url"]
        storage_path = uploaded_image["storage_path"]
        cdn_url = url.replace("localhost:8000", "cdn.foodtracker.example.com")  # Simulate CDN URL

        # Generate AI analysis data based on image type
        ai_status = (
            AIProcessingStatusType.COMPLETED
            if faker.pybool(70)
            else faker.random.choice([AIProcessingStatusType.PENDING, AIProcessingStatusType.PROCESSING, AIProcessingStatusType.FAILED])
        )

        ai_detected_foods = None
        ai_confidence_score = None
        ai_estimated_calories = None
        ai_processed_at = None

        if ai_status == AIProcessingStatusType.COMPLETED:
            if image_type == ImageType.MEAL_PHOTO:
                # Generate detected foods for meal photos
                ai_detected_foods = faker.random.sample(
                    [
                        "chicken",
                        "rice",
                        "broccoli",
                        "salmon",
                        "pasta",
                        "tomatoes",
                        "lettuce",
                        "beef",
                        "potatoes",
                        "carrots",
                        "eggs",
                        "bread",
                        "cheese",
                        "mushrooms",
                        "onions",
                    ],
                    k=faker.random_int(min=1, max=5),
                )
                ai_confidence_score = round(faker.random.uniform(0.65, 0.98), 2)
                ai_estimated_calories = round(faker.random.uniform(200, 800), 2)
            elif image_type == ImageType.NUTRITION_LABEL:
                # For nutrition labels, we're detecting text and nutritional info
                ai_confidence_score = round(faker.random.uniform(0.85, 0.99), 2)  # Higher confidence for text detection
                ai_estimated_calories = round(faker.random.uniform(0, 1000), 2)  # Calories from the label
            elif image_type == ImageType.INGREDIENT_PHOTO:
                # For ingredient photos, we're detecting single ingredients
                ai_detected_foods = [
                    faker.random.choice(
                        ["tomato", "potato", "carrot", "onion", "garlic", "lettuce", "cucumber", "pepper", "mushroom", "broccoli", "spinach", "apple", "lemon", "orange", "banana"]
                    )
                ]
                ai_confidence_score = round(faker.random.uniform(0.75, 0.99), 2)

            ai_processed_at = (datetime.now() - timedelta(minutes=faker.random_int(min=1, max=60))).isoformat()

        # Link to meal (40% chance)
        meal_id = faker.random.choice(meal_ids) if meal_ids and faker.pybool(40) else None

        # Generate EXIF data (80% chance)
        exif_data = generate_realistic_exif_data() if faker.pybool(80) else None

        # Generate tags based on image type
        tags = generate_realistic_tags(image_type, ai_detected_foods)

        # Create image record
        image = ImageData(
            id=str(uuid.uuid4()),
            created_at=faker.date_time_between(start_date="-1y", end_date="now").isoformat(),
            updated_at=faker.date_time_between(start_date="-1y", end_date="now").isoformat(),
            url=url,
            filename=uploaded_image["filename"],
            file_size_bytes=uploaded_image["file_size_bytes"],
            mime_type=uploaded_image["mime_type"],
            width=3000,  # Assuming standard dimensions for sample images
            height=2000,
            meal_id=meal_id,
            uploaded_by="",  # Will be populated during seeding; set to empty string to satisfy type checker
            uploaded_by_user=uploaded_by_user if uploaded_by_user is not None else "",
            ai_detected_foods=ai_detected_foods,
            ai_confidence_score=ai_confidence_score,
            ai_estimated_calories=ai_estimated_calories,
            ai_processing_status=ai_status,
            ai_processed_at=ai_processed_at,
            image_type=image_type,
            tags=tags,
            is_public=faker.pybool(60),  # 60% chance of being public
            is_verified=faker.pybool(20),  # 20% chance of being verified
            blur_hash=generate_realistic_blur_hash(),
            exif_data=exif_data,
            is_flagged=faker.pybool(5),  # 5% chance of being flagged
            moderation_status=faker.random.choice(
                [ModerationStatusType.APPROVED] * 9 + [ModerationStatusType.PENDING, ModerationStatusType.REJECTED]
            ),  # 90% approved, 5% pending, 5% rejected
            storage_bucket="user-images",
            storage_path=storage_path,
            cdn_url=cdn_url,
        )
        images_data.append(image)

    # Save to JSON file
    serializable_images = [image.model_dump() for image in images_data]
    with images_file.open("w", encoding="utf-8") as f:
        json.dump(serializable_images, f, indent=2)
        logger.info(f"Stored {len(images_data)} images in {images_file}")

    logger.succeed(f"Generated {number_of_images} images data")


async def seed_images_data():
    """Insert images into Supabase images table from generated data"""
    supabase = await get_supabase_client()

    # Try to load from existing JSON file first
    images_data = None
    try:
        with images_file.open(encoding="utf-8") as f:
            images_data = [ImageData(**image) for image in json.load(f)]
            logger.info(f"Loaded {len(images_data)} images from {images_file}")
    except FileNotFoundError:
        logger.error(f"Images file not found: {images_file}")
        logger.info("Please run generate_images_data() first to create image data")
        return
    except json.JSONDecodeError:
        logger.error(f"Invalid JSON format in {images_file}")
        return

    if images_data is None:
        logger.error("No image data available. Please generate image data first.")
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

    logger.start(f"Inserting {len(images_data)} images into Supabase images table")

    for image in images_data:
        # Assign a random user UUID as the uploader
        image.uploaded_by = faker.random.choice(user_uuids)

        # Create a copy of the record without uploaded_by_user
        record = image.model_dump()
        record.pop("uploaded_by_user", None)  # Remove uploaded_by_user from the record

        try:
            await supabase.table("images").insert(record).execute()
        except Exception as e:
            if "duplicate key value" in str(e) or "already exists" in str(e):
                pass
            else:
                logger.error(f"Error inserting image {image.filename}: {e}")

    logger.succeed(f"Inserted {len(images_data)} images into images table")


async def generate_uploaded_images_metadata():
    """Generate metadata for uploaded images without actually uploading them"""
    uploaded_images_file = settings.DATA_PATH / "uploaded_images.json"

    # Sample image metadata
    sample_images = [
        {"prefix": "pe", "start": 1, "end": 1000000, "count": 10},  # Pexels images
        {"prefix": "pi", "start": 1000000, "end": 10000000, "count": 10},  # Pixabay images
        {"prefix": "un", "start": 1, "end": 1000000, "count": 10},  # Unsplash images
    ]

    uploaded_images = []

    for source in sample_images:
        for _ in range(source["count"]):
            image_id = faker.random_int(min=source["start"], max=source["end"])
            filename = f"{source['prefix']}-{image_id}.jpg"
            file_size = faker.random_int(min=20000, max=150000)  # Random file size between 20KB and 150KB

            image_metadata = {
                "filename": filename,
                "url": f"/storage/v1/object/public/user-images/{filename}",
                "storage_path": f"{filename}",
                "file_size_bytes": file_size,
                "mime_type": "image/jpeg",
            }
            uploaded_images.append(image_metadata)

    # Save metadata to JSON file
    with uploaded_images_file.open("w", encoding="utf-8") as f:
        json.dump(uploaded_images, f, indent=2)
        logger.info(f"Generated metadata for {len(uploaded_images)} images in {uploaded_images_file}")
