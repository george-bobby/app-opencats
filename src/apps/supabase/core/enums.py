"""
Database Enums Module

This module defines all the enums used in the database schema to ensure consistency
between Python code and PostgreSQL database enums. These enum values must match
exactly with the database enums defined in 00_enums.sql.
"""

from enum import Enum


# User-related enums
class GenderType(str, Enum):
    """Gender types for user profiles."""

    MALE = "male"
    FEMALE = "female"
    OTHER = "other"


class ActivityLevelType(str, Enum):
    """Activity levels for calorie calculations."""

    SEDENTARY = "sedentary"
    LIGHT = "light"
    MODERATE = "moderate"
    ACTIVE = "active"
    VERY_ACTIVE = "very_active"


class GoalType(str, Enum):
    """Health goals for users."""

    LOSE = "lose"
    MAINTAIN = "maintain"
    GAIN = "gain"


# Brand-related enums
class BrandCategoryType(str, Enum):
    """Categories for food brands."""

    RESTAURANT = "restaurant"
    PACKAGED_FOOD = "packaged_food"
    BEVERAGE = "beverage"
    SUPPLEMENT = "supplement"
    ORGANIC = "organic"
    FAST_FOOD = "fast_food"


# Meal-related enums
class MealType(str, Enum):
    """Types of meals."""

    BREAKFAST = "breakfast"
    LUNCH = "lunch"
    DINNER = "dinner"
    SNACK = "snack"
    DRINK = "drink"
    DESSERT = "dessert"


class ServingUnitType(str, Enum):
    """Units for serving sizes."""

    G = "g"
    ML = "ml"
    OZ = "oz"
    CUP = "cup"
    PIECE = "piece"
    SLICE = "slice"
    TBSP = "tbsp"
    TSP = "tsp"


class FoodCategoryType(str, Enum):
    """Categories for food classification."""

    FRUITS = "fruits"
    VEGETABLES = "vegetables"
    GRAINS = "grains"
    PROTEIN = "protein"
    DAIRY = "dairy"
    FATS = "fats"
    BEVERAGES = "beverages"
    SWEETS = "sweets"
    PROCESSED = "processed"


# Image-related enums
class MimeType(str, Enum):
    """MIME types for images."""

    JPEG = "image/jpeg"
    PNG = "image/png"
    WEBP = "image/webp"
    HEIC = "image/heic"


class AIProcessingStatusType(str, Enum):
    """AI processing status for images."""

    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class ImageType(str, Enum):
    """Types of images."""

    MEAL_PHOTO = "meal_photo"
    INGREDIENT_PHOTO = "ingredient_photo"
    NUTRITION_LABEL = "nutrition_label"
    RECEIPT = "receipt"


class ModerationStatusType(str, Enum):
    """Moderation status for images."""

    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


# Log-related enums
class LoggingMethodType(str, Enum):
    """Methods for logging meals."""

    MANUAL = "manual"
    BARCODE = "barcode"
    PHOTO = "photo"
    VOICE = "voice"


# User preference enums
class UnitsSystemType(str, Enum):
    """Units system preferences."""

    METRIC = "metric"
    IMPERIAL = "imperial"


class DateFormatType(str, Enum):
    """Date format preferences."""

    MM_DD_YYYY = "MM/DD/YYYY"
    DD_MM_YYYY = "DD/MM/YYYY"
    YYYY_MM_DD = "YYYY-MM-DD"


class TimeFormatType(str, Enum):
    """Time format preferences."""

    TWELVE_HOUR = "12h"
    TWENTY_FOUR_HOUR = "24h"


class ThemePreferenceType(str, Enum):
    """Theme preferences."""

    LIGHT = "light"
    DARK = "dark"
    SYSTEM = "system"


# Additional enums for data generation (not in database schema)
class CuisineType(str, Enum):
    """Cuisine types for meal generation."""

    AMERICAN = "american"
    ITALIAN = "italian"
    CHINESE = "chinese"
    JAPANESE = "japanese"
    MEXICAN = "mexican"
    INDIAN = "indian"
    FRENCH = "french"
    THAI = "thai"
    GREEK = "greek"
    MEDITERRANEAN = "mediterranean"


class DietaryTag(str, Enum):
    """Dietary tags for meals."""

    VEGAN = "vegan"
    VEGETARIAN = "vegetarian"
    GLUTEN_FREE = "gluten-free"
    DAIRY_FREE = "dairy-free"
    NUT_FREE = "nut-free"
    KETO = "keto"
    PALEO = "paleo"
    LOW_CARB = "low-carb"
    LOW_FAT = "low-fat"
    HIGH_PROTEIN = "high-protein"
    ORGANIC = "organic"


class Location(str, Enum):
    """Location types for meal logging."""

    HOME = "home"
    RESTAURANT = "restaurant"
    OFFICE = "office"
    SCHOOL = "school"
    CAFE = "cafe"
    OTHER = "other"


# Utility functions to get enum values as lists
def get_enum_values(enum_class: type[Enum]) -> list[str]:
    """Get all enum values as a list of strings."""
    return [item.value for item in enum_class]


def get_random_enum_value(enum_class: type[Enum]) -> str:
    """Get a random enum value."""
    import random

    return random.choice(get_enum_values(enum_class))
