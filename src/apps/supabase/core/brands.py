import json
import uuid

from pydantic import BaseModel, Field

from apps.supabase.config.settings import settings
from apps.supabase.core.enums import BrandCategoryType
from apps.supabase.utils.faker import faker
from apps.supabase.utils.supabase import get_supabase_client
from common.logger import logger


brands_file = settings.DATA_PATH.joinpath("generated", "brands.json")


class BrandData(BaseModel):
    id: str = Field(description="Brand UUID")  # noqa: A003, RUF100
    name: str = Field(description="Unique brand name")
    created_at: str = Field(description="Timestamp of creation")
    updated_at: str = Field(description="Timestamp of last update")

    # Brand information
    logo_url: str | None = Field(default=None, description="Logo URL")
    description: str | None = Field(default=None, description="Brand description")
    website_url: str | None = Field(default=None, description="Brand website URL")

    # Brand metrics
    popularity_rank: int = Field(default=0, description="Popularity ranking")
    verified: bool = Field(default=False, description="Whether brand is verified")
    total_products: int = Field(default=0, description="Total number of products")

    # Brand classification
    category: BrandCategoryType | None = Field(default=None, description="Brand category")
    country_origin: str | None = Field(default=None, description="Country of origin")

    # Metadata
    is_active: bool = Field(default=True, description="Whether brand is active")


def get_sample_brand_names():
    # Mix of real, generic, and test brands
    return [
        "Coca-Cola",
        "Pepsi",
        "Nestle",
        "Kellogg's",
        "Unilever",
        "Procter & Gamble",
        "General Mills",
        "Danone",
        "Heinz",
        "Kraft",
        "Test Brand A",
        "Sample Brand B",
        "Generic Foods",
        "Acme Corp",
        "OpenAI Foods",
        "Healthy Choice",
        "Nature's Best",
        "Urban Eats",
        "QuickBite",
        "FreshStart",
        "FitFuel",
        "SnackSmart",
        "GreenLeaf",
        "Sunrise Foods",
        "BlueSky Brands",
        "RedApple",
        "Golden Harvest",
        "Purely Plant",
        "VitaBoost",
        "SmartCal",
        "CalorieWise",
        "LeanLife",
        "NutriTrack",
        "Test Brand C",
        "Sample Brand D",
        "BrandX",
        "BrandY",
        "BrandZ",
        "Foodie Inc",
        "EatWell",
        "YumYum",
        "TastyBites",
        "FoodLab",
        "MVP Brands",
        "Startup Snacks",
        "Beta Foods",
        "Demo Brand",
        "Mock Foods",
        "Trial Brand",
        "SimuBrand",
        "ProtoFoods",
    ]


def generate_unique_brand_names(target_count: int) -> list[str]:
    base_names = get_sample_brand_names()
    names = set(base_names)
    # Add more fake brands if needed
    while len(names) < target_count:
        company_name = faker.unique.company()
        company_name = company_name.replace("-", " ")
        names.add(company_name)
    return list(names)[:target_count]


async def generate_brand_data(number_of_brands: int = 100):
    """Generate brand data and save to JSON file"""

    logger.info(f"Generating {number_of_brands} brands data")
    brand_names = generate_unique_brand_names(number_of_brands)
    brands_data = []
    for name in brand_names:
        created_time = faker.date_time_between(start_date="-2y", end_date="now")
        brand = BrandData(
            id=str(uuid.uuid4()),
            name=name,
            created_at=created_time.isoformat(),
            updated_at=faker.date_time_between(start_date=created_time, end_date="now").isoformat(),
            logo_url=faker.image_url(width=200, height=200) if faker.pybool(60) else None,
            description=faker.sentence() if faker.pybool(70) else None,
            website_url=faker.url() if faker.pybool(40) else None,
            popularity_rank=faker.random_int(min=0, max=1000),
            verified=faker.pybool(30),  # 30% chance of being verified
            total_products=faker.random_int(min=0, max=500),
            category=faker.random_element(elements=list(BrandCategoryType)) if faker.pybool(80) else None,
            country_origin=faker.country() if faker.pybool(60) else None,
            is_active=faker.pybool(95),  # 95% chance of being active
        )
        brands_data.append(brand)
    # Save to JSON file
    serializable_brands = [brand.model_dump() for brand in brands_data]
    with brands_file.open("w", encoding="utf-8") as f:
        json.dump(serializable_brands, f, indent=2)
        logger.info(f"Stored {len(brands_data)} brands in {brands_file}")
    logger.succeed(f"Generated {number_of_brands} brands data")


async def seed_brands_data():
    """Insert brands into Supabase brands table from generated data"""
    supabase = await get_supabase_client()
    # Try to load from existing JSON file first
    brands_data = None
    try:
        with brands_file.open(encoding="utf-8") as f:
            brands_data = [BrandData(**brand) for brand in json.load(f)]
            logger.info(f"Loaded {len(brands_data)} brands from {brands_file}")
    except FileNotFoundError:
        logger.error(f"Brands file not found: {brands_file}")
        logger.info("Please run generate_brand_data() first to create brand data")
        return
    except json.JSONDecodeError:
        logger.error(f"Invalid JSON format in {brands_file}")
        return
    if brands_data is None:
        logger.error("No brand data available. Please generate brand data first.")
        return
    logger.info(f"Inserting {len(brands_data)} brands into Supabase brands table")
    for brand in brands_data:
        record = {
            "id": brand.id,
            "name": brand.name,
            "created_at": brand.created_at,
            "logo_url": brand.logo_url,
            "description": brand.description,
        }
        try:
            await supabase.table("brands").insert(record).execute()
        except Exception as e:
            if "duplicate key value" in str(e) or "already exists" in str(e):
                pass
            else:
                logger.error(f"Error inserting brand {brand.name}: {e}")
    logger.succeed(f"Inserted {len(brands_data)} brands into brands table")
