import json
import uuid
from pathlib import Path

from pydantic import BaseModel, Field

from apps.supabase.config.settings import settings
from apps.supabase.core.enums import (
    CuisineType,
    DietaryTag,
    FoodCategoryType,
    MealType,
)
from apps.supabase.utils.faker import faker
from apps.supabase.utils.supabase import get_supabase_client
from common.logger import logger


# Global variable to store email to id mapping
_email_to_id_mapping = {}

# Define file paths
MEALS_DATA_FILE = settings.DATA_PATH / "generated" / "meals.json"
USERS_DATA_FILE = settings.DATA_PATH / "generated" / "users.json"
brands_file = settings.DATA_PATH.joinpath("generated", "brands.json")


# Remove the old enum classes since they're now imported from enums module


class MealData(BaseModel):
    id: str = Field(description="Meal UUID")  # noqa: A003, RUF100
    name: str = Field(description="Meal name")
    meal_type: MealType = Field(description="Type of meal")
    calories_per_serving: int = Field(description="Calories per serving")
    serving_size: float = Field(description="Serving size amount")
    serving_unit: str = Field(description="Serving size unit")

    # Add nutrition fields
    protein_g: float = Field(default=0, description="Protein per serving in grams", ge=0)
    carbs_g: float = Field(default=0, description="Carbs per serving in grams", ge=0)
    fat_g: float = Field(default=0, description="Fat per serving in grams", ge=0)

    brand_name: str | None = Field(default=None, description="Associated brand name")
    brand_id: str | None = Field(default=None, description="Associated brand ID")
    food_category: FoodCategoryType | None = Field(default=None, description="Food category")
    cuisine_type: CuisineType | None = Field(default=None, description="Cuisine type")
    dietary_tags: list[DietaryTag] | None = Field(default=None, description="Dietary tags")
    description: str | None = Field(default=None, description="Meal description")
    image_url: str | None = Field(default=None, description="Image URL")
    barcode: str | None = Field(default=None, description="Barcode")
    verified: bool = Field(default=False, description="Whether meal is verified")
    created_by: str | None = Field(default=None, description="Username or UUID of creator")
    created_at: str = Field(description="Creation timestamp")
    is_active: bool = Field(default=True, description="Whether meal is active")


def get_serving_unit_by_category(category: FoodCategoryType) -> str:
    """Get appropriate serving unit based on food category"""
    # All valid units from the database schema
    valid_units = ["g", "ml", "oz", "cup", "piece", "slice", "tbsp", "tsp"]

    category_units = {
        FoodCategoryType.FRUITS: ["piece", "cup", "g"],
        FoodCategoryType.VEGETABLES: ["cup", "g", "oz"],
        FoodCategoryType.GRAINS: ["cup", "g", "oz"],
        FoodCategoryType.PROTEIN: ["oz", "g", "piece"],
        FoodCategoryType.DAIRY: ["cup", "oz", "g"],
        FoodCategoryType.FATS: ["tbsp", "tsp", "g"],
        FoodCategoryType.BEVERAGES: ["ml", "oz", "cup"],
        FoodCategoryType.SWEETS: ["piece", "slice", "g"],
        FoodCategoryType.PROCESSED: ["piece", "g", "oz"],
    }

    # Get units for the category, ensuring they're all valid
    valid_category_units = [unit for unit in category_units.get(category, ["g"]) if unit in valid_units]
    if not valid_category_units:
        return "g"  # Default to grams if no valid units for category

    return faker.random.choice(valid_category_units)


def generate_realistic_calories(category: FoodCategoryType, serving_size: float) -> int:
    """Generate realistic calories based on food category and serving size"""
    # Calories per 100g/100ml baseline
    category_calories = {
        FoodCategoryType.FRUITS: (30, 100),
        FoodCategoryType.VEGETABLES: (20, 80),
        FoodCategoryType.GRAINS: (150, 400),
        FoodCategoryType.PROTEIN: (150, 300),
        FoodCategoryType.DAIRY: (100, 250),
        FoodCategoryType.FATS: (800, 900),  # High calorie density for fats
        FoodCategoryType.BEVERAGES: (30, 150),
        FoodCategoryType.SWEETS: (250, 500),  # High calorie for sweets
        FoodCategoryType.PROCESSED: (200, 450),  # Variable range for processed foods
    }

    base_min, base_max = category_calories.get(category, (100, 300))
    # Adjust calories based on serving size
    calories = faker.random_int(min=base_min, max=base_max)
    # Scale calories based on serving size (assuming baseline is 100g/ml)
    scaled_calories = int(calories * (serving_size / 100))
    return max(1, scaled_calories)  # Ensure at least 1 calorie


def generate_realistic_nutrition(calories: int, food_category: FoodCategoryType) -> tuple[float, float, float]:
    """Generate realistic macronutrient values based on calories and food category"""
    # Macronutrient ratios (protein/carbs/fat) by food category
    category_ratios = {
        FoodCategoryType.FRUITS: (5, 85, 10),  # Low protein, high carbs, low fat
        FoodCategoryType.VEGETABLES: (15, 75, 10),  # Moderate protein, high carbs, low fat
        FoodCategoryType.GRAINS: (10, 75, 15),  # Moderate protein, high carbs, low fat
        FoodCategoryType.PROTEIN: (60, 10, 30),  # High protein, low carbs, moderate fat
        FoodCategoryType.DAIRY: (30, 30, 40),  # High protein, moderate carbs, high fat
        FoodCategoryType.FATS: (5, 5, 90),  # Low protein, low carbs, very high fat
        FoodCategoryType.BEVERAGES: (10, 85, 5),  # Low protein, high carbs, very low fat
        FoodCategoryType.SWEETS: (5, 80, 15),  # Low protein, very high carbs, low fat
        FoodCategoryType.PROCESSED: (20, 50, 30),  # Moderate protein, high carbs, moderate fat
    }

    # Get ratio for category or use balanced ratio
    protein_ratio, carb_ratio, fat_ratio = category_ratios.get(food_category, (30, 40, 30))

    # Add some randomness to the ratios while maintaining the sum at 100
    variation = 5  # percentage points of variation

    # Add variation but ensure ratios stay positive
    protein_ratio = max(5, protein_ratio + faker.random_int(min=-variation, max=variation))
    carb_ratio = max(5, carb_ratio + faker.random_int(min=-variation, max=variation))

    # Adjust fat ratio to make total 100%, but ensure it's at least 5%
    fat_ratio = 100 - protein_ratio - carb_ratio
    if fat_ratio < 5:
        # If fat ratio would be too low, reduce the larger of protein and carb ratios
        if protein_ratio > carb_ratio:
            protein_ratio -= 5 - fat_ratio
        else:
            carb_ratio -= 5 - fat_ratio
        fat_ratio = 5

    # Normalize ratios to ensure they sum to 100
    total = protein_ratio + carb_ratio + fat_ratio
    protein_ratio = (protein_ratio / total) * 100
    carb_ratio = (carb_ratio / total) * 100
    fat_ratio = (fat_ratio / total) * 100

    # Calculate grams based on calories (4 cal/g for protein and carbs, 9 cal/g for fat)
    protein_g = round((calories * protein_ratio / 100) / 4, 2)
    carbs_g = round((calories * carb_ratio / 100) / 4, 2)
    fat_g = round((calories * fat_ratio / 100) / 9, 2)

    # Ensure all values are non-negative (should never happen with above logic, but just in case)
    protein_g = max(0, protein_g)
    carbs_g = max(0, carbs_g)
    fat_g = max(0, fat_g)

    return protein_g, carbs_g, fat_g


def generate_food_description(name: str, food_category: FoodCategoryType, dietary_tags: list[DietaryTag] | None) -> str:
    """Generate a sensible description for a food item"""

    # Base descriptions by category
    category_descriptions = {
        FoodCategoryType.FRUITS: ["Fresh and naturally sweet", "Ripe and juicy", "Seasonal and refreshing", "Hand-picked and fresh", "Naturally sweet and nutritious"],
        FoodCategoryType.VEGETABLES: ["Fresh and crispy", "Garden-fresh", "Locally sourced", "Crisp and nutritious", "Farm-fresh and organic"],
        FoodCategoryType.GRAINS: ["Whole grain goodness", "Hearty and filling", "Rich in fiber", "Nutritious and satisfying", "Wholesome and natural"],
        FoodCategoryType.PROTEIN: ["Lean and protein-rich", "High-quality protein source", "Premium cut", "Sustainably sourced", "Rich in essential nutrients"],
        FoodCategoryType.DAIRY: ["Creamy and rich", "Fresh and wholesome", "Calcium-rich", "Farm-fresh dairy", "Smooth and creamy"],
        FoodCategoryType.FATS: ["Heart-healthy", "Rich and flavorful", "Premium quality", "Carefully selected", "Pure and natural"],
        FoodCategoryType.BEVERAGES: ["Refreshing and hydrating", "Perfectly balanced", "Thirst-quenching", "Naturally flavored", "Pure and refreshing"],
        FoodCategoryType.SWEETS: ["Delightfully sweet", "Indulgent treat", "Perfect dessert", "Sweet and satisfying", "Decadent delight"],
        FoodCategoryType.PROCESSED: ["Convenient and tasty", "Ready to enjoy", "Carefully prepared", "Quality ingredients", "Perfectly portioned"],
    }

    # Get base description
    base_desc = faker.random.choice(category_descriptions.get(food_category, ["Delicious and satisfying"]))

    # Add preparation method if applicable
    prep_methods = {
        "Grilled": "Grilled to perfection",
        "Roasted": "Slow-roasted for maximum flavor",
        "Baked": "Freshly baked",
        "Fresh": "Market-fresh",
        "Spicy": "With a spicy kick",
        "Sweet": "Perfectly sweetened",
        "Crispy": "Crispy and delicious",
    }

    for method, desc in prep_methods.items():
        if method.lower() in name.lower():
            base_desc = f"{desc}. {base_desc}"
            break

    # Add dietary information if available
    if dietary_tags:
        dietary_info = []
        for tag in dietary_tags:
            if tag == DietaryTag.VEGAN:
                dietary_info.append("100% plant-based")
            elif tag == DietaryTag.VEGETARIAN:
                dietary_info.append("vegetarian-friendly")
            elif tag == DietaryTag.GLUTEN_FREE:
                dietary_info.append("gluten-free")
            elif tag == DietaryTag.DAIRY_FREE:
                dietary_info.append("dairy-free")
            elif tag == DietaryTag.KETO:
                dietary_info.append("keto-friendly")
            elif tag == DietaryTag.PALEO:
                dietary_info.append("paleo-friendly")
            elif tag == DietaryTag.LOW_CARB:
                dietary_info.append("low in carbs")
            elif tag == DietaryTag.LOW_FAT:
                dietary_info.append("low in fat")
            elif tag == DietaryTag.HIGH_PROTEIN:
                dietary_info.append("high in protein")
            elif tag == DietaryTag.ORGANIC:
                dietary_info.append("made with organic ingredients")

        if dietary_info:
            base_desc = f"{base_desc}. {' and '.join(dietary_info[:2]).capitalize()}"

    return base_desc


async def generate_meals_data(number_of_meals: int = 500):
    """Generate meal data and save to JSON file"""

    logger.info(f"Generating {number_of_meals} meals data")

    # Load brands data for linking
    try:
        with brands_file.open(encoding="utf-8") as f:
            brands_data = json.load(f)
            brand_names = [brand["name"] for brand in brands_data]
    except (FileNotFoundError, json.JSONDecodeError):
        brand_names = []
        logger.warning("No brands data found, meals will not be linked to brands")

    # Get usernames from users.json
    usernames = []
    try:
        with Path.open(USERS_DATA_FILE) as f:
            users_data = json.load(f)
            usernames = [f"{user['first_name'].lower()}.{user['last_name'].lower()}" for user in users_data]
            logger.info(f"Found {len(usernames)} users in users.json")
        if not usernames:
            logger.warning("No users found in users.json, meals will not be linked to users")
    except (FileNotFoundError, json.JSONDecodeError) as e:
        logger.warning(f"Failed to load users from {USERS_DATA_FILE}: {e}, meals will not be linked to users")

    meals_data = []
    for _ in range(number_of_meals):
        # Generate core meal data
        food_category = faker.random.choice(list(FoodCategoryType))
        serving_size = round(faker.random_int(min=50, max=500) / 100, 1)  # 0.5 to 5.0
        serving_unit = get_serving_unit_by_category(food_category)
        calories = generate_realistic_calories(food_category, serving_size)

        # Generate nutrition data
        protein_g, carbs_g, fat_g = generate_realistic_nutrition(calories, food_category)

        # Randomly assign brand and creator
        brand_name = faker.random.choice(brand_names) if brand_names and faker.pybool(30) else None

        # Generate dietary tags (0 to 3 tags)
        num_tags = faker.random_int(min=0, max=3)
        dietary_tags = faker.random.sample(list(DietaryTag), num_tags) if num_tags > 0 else None

        # Assign a random creator from our existing users
        created_by = None
        if usernames and faker.pybool(80):  # 80% chance to have a creator
            created_by = faker.random.choice(usernames)

        # Generate meal name first
        dish_types = ["Bowl", "Salad", "Sandwich", "Soup", "Stir-Fry", "Pasta", "Risotto", "Curry", "Stew"]
        proteins = ["Chicken", "Beef", "Tofu", "Shrimp", "Salmon", "Vegetables", "Mushrooms"]

        asian_styles = ["Spicy", "Sweet", "Crispy"]
        asian_dishes = ["Pad Thai", "Ramen", "Udon", "Pho", "Bibimbap", "Sushi Roll", "Fried Rice", "Dumplings"]

        med_styles = ["Greek", "Italian", "Lebanese"]
        med_dishes = ["Mezze Platter", "Hummus", "Falafel Wrap", "Shawarma", "Kebab", "Pita"]

        healthy_bases = ["Quinoa", "Kale", "Acai", "Buddha", "Protein"]
        healthy_types = ["Bowl", "Smoothie", "Salad"]
        healthy_toppings = ["Avocado", "Chickpeas", "Sweet Potato", "Grilled Chicken", "Tofu"]

        comfort_styles = ["Classic", "Gourmet", "Homestyle"]
        comfort_foods = ["Mac & Cheese", "Pizza", "Burger", "Tacos", "Nachos", "Grilled Cheese"]

        breakfast_items = ["French Toast", "Pancakes", "Waffles", "Omelette", "Breakfast Burrito"]
        breakfast_toppings = ["Berries", "Bacon", "Maple Syrup", "Eggs", "Spinach"]

        veg_styles = ["Roasted", "Grilled", "Fresh"]
        veg_bases = ["Cauliflower", "Eggplant", "Portobello", "Zucchini"]
        veg_types = ["Steak", "Bowl", "Tacos", "Curry"]

        seafood_styles = ["Grilled", "Pan-Seared", "Baked"]
        seafood_types = ["Salmon", "Tuna", "Shrimp", "Fish"]
        seafood_sauces = ["Lemon Butter", "Garlic Sauce", "Teriyaki Glaze"]

        fusion_styles = ["Korean", "Mexican", "Thai", "Indian"]
        fusion_types = ["Tacos", "Bowl", "Wrap", "Burger"]

        dessert_flavors = ["Chocolate", "Vanilla", "Strawberry", "Caramel"]
        dessert_types = ["Cake", "Ice Cream", "Pudding", "Cookies", "Brownies"]

        name = faker.random.choice(
            [
                # Basic dishes
                f"{faker.random.choice(dish_types)} with {faker.random.choice(proteins)}",
                # Asian-inspired
                f"{faker.random.choice(asian_styles)} {faker.random.choice(asian_dishes)}",
                # Mediterranean
                f"{faker.random.choice(med_styles)} {faker.random.choice(med_dishes)}",
                # Healthy options
                f"{faker.random.choice(healthy_bases)} {faker.random.choice(healthy_types)} with {faker.random.choice(healthy_toppings)}",
                # Comfort food
                f"{faker.random.choice(comfort_styles)} {faker.random.choice(comfort_foods)}",
                # Breakfast items
                f"{faker.random.choice(breakfast_items)} with {faker.random.choice(breakfast_toppings)}",
                # Vegetarian/Vegan
                f"{faker.random.choice(veg_styles)} {faker.random.choice(veg_bases)} {faker.random.choice(veg_types)}",
                # Seafood
                f"{faker.random.choice(seafood_styles)} {faker.random.choice(seafood_types)} with {faker.random.choice(seafood_sauces)}",
                # Global fusion
                f"{faker.random.choice(fusion_styles)} Fusion {faker.random.choice(fusion_types)}",
                # Desserts
                f"{faker.random.choice(dessert_flavors)} {faker.random.choice(dessert_types)}",
            ]
        )

        meal = MealData(
            id=str(uuid.uuid4()),
            name=name,
            meal_type=faker.random.choice(list(MealType)),
            calories_per_serving=calories,
            serving_size=serving_size,
            serving_unit=serving_unit,
            protein_g=protein_g,
            carbs_g=carbs_g,
            fat_g=fat_g,
            brand_name=brand_name,
            brand_id=None,
            food_category=food_category,
            cuisine_type=faker.random.choice(list(CuisineType)) if faker.pybool(60) else None,
            dietary_tags=dietary_tags,
            description=generate_food_description(name, food_category, dietary_tags) if faker.pybool(70) else None,
            image_url=faker.image_url(width=300, height=300) if faker.pybool(60) else None,
            barcode=faker.ean13() if faker.pybool(40) else None,
            verified=faker.pybool(20),  # 20% chance of being verified
            created_by=created_by,
            created_at=faker.date_time_between(start_date="-1y", end_date="now").isoformat(),
            is_active=faker.pybool(90),  # 90% chance of being active
        )
        meals_data.append(meal)

    # Save to JSON file
    serializable_meals = [meal.model_dump() for meal in meals_data]
    with MEALS_DATA_FILE.open("w", encoding="utf-8") as f:
        json.dump(serializable_meals, f, indent=2)
        logger.info(f"Stored {len(meals_data)} meals in {MEALS_DATA_FILE}")

    logger.succeed(f"Generated {number_of_meals} meals data")


async def seed_meals_data():
    """Insert meals into Supabase meals table from generated data"""
    supabase = await get_supabase_client()

    # Try to load from existing JSON file first
    meals_data = None
    try:
        with MEALS_DATA_FILE.open(encoding="utf-8") as f:
            meals_data = [MealData(**meal) for meal in json.load(f)]
            logger.info(f"Loaded {len(meals_data)} meals from {MEALS_DATA_FILE}")
    except FileNotFoundError:
        logger.error(f"Meals file not found: {MEALS_DATA_FILE}")
        logger.info("Please run generate_meal_data() first to create meal data")
        return
    except json.JSONDecodeError:
        logger.error(f"Invalid JSON format in {MEALS_DATA_FILE}")
        return

    if meals_data is None:
        logger.error("No meal data available. Please generate meal data first.")
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

    # Get brand name to UUID mapping from Supabase
    brand_name_to_uuid = {}
    try:
        response = await supabase.table("brands").select("id,name").execute()
        if response.data:
            brand_name_to_uuid = {brand["name"]: brand["id"] for brand in response.data}
            logger.info(f"Loaded {len(brand_name_to_uuid)} brand name to UUID mappings")
    except Exception as e:
        logger.error(f"Failed to fetch brand mappings: {e}")
        return

    logger.start(f"Inserting {len(meals_data)} meals into Supabase meals table")

    for meal in meals_data:
        # Assign a random user UUID as the creator
        meal.created_by = faker.random.choice(user_uuids)

        # Convert brand name to UUID if present
        if meal.brand_name:
            if meal.brand_name in brand_name_to_uuid:
                meal.brand_id = brand_name_to_uuid[meal.brand_name]
            else:
                logger.warning(f"Brand name {meal.brand_name} not found in database, setting brand_id to null")
                meal.brand_id = None

        record = meal.model_dump()
        # Remove brand_name as it's not in the database schema
        record.pop("brand_name", None)

        try:
            await supabase.table("meals").insert(record).execute()
        except Exception as e:
            if "duplicate key value" in str(e) or "already exists" in str(e):
                pass
            else:
                logger.error(f"Error inserting meal {meal.name}: {e}")

    logger.succeed(f"Inserted {len(meals_data)} meals into meals table")
