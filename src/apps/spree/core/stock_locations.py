import json
import random
from datetime import datetime
from pathlib import Path

from faker import Faker
from pydantic import BaseModel, Field

from apps.spree.config.settings import settings
from apps.spree.utils.constants import STATES_FILE, STOCK_LOCATIONS_FILE
from apps.spree.utils.database import db_client
from common.logger import Logger


logger = Logger()
fake = Faker("en_US")


class StockLocation(BaseModel):
    """Individual stock location model."""

    id: int = Field(description="Unique identifier for the stock location")  # noqa: A003, RUF100
    name: str = Field(description="Name of the stock location")
    default: bool = Field(description="Whether this is the default stock location", default=False)
    address1: str = Field(description="Primary address line")
    address2: str | None = Field(description="Secondary address line", default=None)
    city: str = Field(description="City name")
    state_id: int = Field(description="State ID from states data")
    state_name: str = Field(description="State name")
    country_id: int = Field(description="Country ID (US = 49)", default=49)
    zipcode: str = Field(description="ZIP code")
    phone: str = Field(description="Phone number")
    active: bool = Field(description="Whether the location is active", default=True)
    backorderable_default: bool = Field(description="Default backorder setting", default=False)
    propagate_all_variants: bool = Field(description="Whether to propagate all variants", default=False)
    admin_name: str = Field(description="Internal identifier for the stock location used by administrators (e.g., main, processing, depot, storage)")


class StockLocationsResponse(BaseModel):
    """Response format for generated stock locations."""

    stock_locations: list[StockLocation]


async def generate_stock_locations(number_of_stock_locations: int) -> dict | None:
    """Generate realistic stock locations for a pet supplies eCommerce store."""

    logger.info("Generating stock locations for pet supplies store...")

    try:
        # Load states data
        if not STATES_FILE.exists():
            logger.error(f"States file not found at {STATES_FILE}")
            raise FileNotFoundError("States file not found")

        with Path.open(STATES_FILE, encoding="utf-8") as f:
            states_data = json.load(f)

        logger.info(f"Loaded {len(states_data)} states from {STATES_FILE}")

        # Filter out armed forces and other non-standard states
        valid_states = {state_id: state_info for state_id, state_info in states_data.items() if state_info["cities"] and not state_info["name"].startswith("Armed Forces")}

        logger.info(f"Using {len(valid_states)} valid states for generation")

        stock_locations = []

        # Generate stock locations with realistic distribution
        location_types = [
            "Main Warehouse",
            "Distribution Center",
            "Regional Hub",
            "Fulfillment Center",
            "Local Depot",
            "Customer Service Center",
            "Processing Facility",
            "Storage Facility",
        ]

        # Start ID counter at 1
        stock_location_id = 1

        for i in range(number_of_stock_locations):
            # Select a random state and city
            state_id = random.choice(list(valid_states.keys()))
            state_info = valid_states[state_id]
            state_name = state_info["name"]
            city = random.choice(state_info["cities"])

            # Generate location name
            if i == 0:
                # First location is always the main warehouse
                location_name = f"{settings.SPREE_STORE_NAME} Main Warehouse"
                is_default = True
                location_type = "Main Warehouse"
            else:
                location_type = random.choice(location_types)
                location_name = f"{settings.SPREE_STORE_NAME} {location_type} - {city}"
                is_default = False

            # Generate realistic address
            street_address = fake.street_address()

            # Some locations have address2 (suite, unit, etc.)
            address2 = None
            if random.random() < 0.3:  # 30% chance of having address2
                address2_types = ["Suite", "Unit", "Building", "Floor"]
                address2 = f"{random.choice(address2_types)} {random.randint(1, 999)}"

            # Generate ZIP code appropriate for the state
            zipcode = fake.zipcode()

            # Generate phone number
            phone = fake.numerify("###-###-####")

            # Generate admin name (internal identifier for administrators)
            if i == 0:
                admin_name = "main"
            else:
                # Create a simple identifier based on location type
                admin_type_map = {
                    "Main Warehouse": "main",
                    "Distribution Center": "distribution",
                    "Regional Hub": "hub",
                    "Fulfillment Center": "fulfillment",
                    "Local Depot": "depot",
                    "Customer Service Center": "service",
                    "Processing Facility": "processing",
                    "Storage Facility": "storage",
                }
                admin_name = admin_type_map.get(location_type, "").lower()

                # Add region identifier if needed to ensure uniqueness
                if i > 1:
                    region_code = city[:3].lower()
                    admin_name = f"{admin_name}_{region_code}"

            # Set operational parameters based on location type
            if location_type in ["Main Warehouse", "Distribution Center"]:
                backorderable_default = True
                propagate_all_variants = True
            elif location_type in ["Fulfillment Center", "Regional Hub"]:
                backorderable_default = True
                propagate_all_variants = False
            else:
                backorderable_default = False
                propagate_all_variants = False

            stock_location = StockLocation(
                id=stock_location_id,
                name=location_name,
                default=is_default,
                address1=street_address,
                address2=address2,
                city=city,
                state_id=int(state_id),
                state_name=state_name,
                country_id=49,  # US
                zipcode=zipcode,
                phone=phone,
                active=True,
                backorderable_default=backorderable_default,
                propagate_all_variants=propagate_all_variants,
                admin_name=admin_name,
            )

            stock_locations.append(stock_location)
            stock_location_id += 1

        # Convert to dict format
        stock_locations_data = {"stock_locations": [sl.model_dump() for sl in stock_locations]}

        # Save to file
        settings.DATA_PATH.mkdir(parents=True, exist_ok=True)
        STOCK_LOCATIONS_FILE.parent.mkdir(parents=True, exist_ok=True)
        with Path.open(STOCK_LOCATIONS_FILE, "w", encoding="utf-8") as f:
            json.dump(stock_locations_data, f, indent=2, ensure_ascii=False)

        logger.succeed(f"Successfully generated and saved {len(stock_locations)} stock locations to {STOCK_LOCATIONS_FILE}")

        # Log details about generated stock locations
        default_location = next((sl for sl in stock_locations if sl.default), None)
        if default_location:
            logger.info(f"Default location: {default_location.name} in {default_location.city}, {default_location.state_name}")

        # Group by state for summary
        states_used = {}
        for sl in stock_locations:
            state = sl.state_name
            states_used[state] = states_used.get(state, 0) + 1

        logger.info(f"Generated locations across {len(states_used)} states:")
        for state, count in sorted(states_used.items()):
            logger.info(f"  {state}: {count} location{'s' if count > 1 else ''}")

        return stock_locations_data

    except Exception as e:
        logger.error(f"Error generating stock locations: {e}")
        raise


async def seed_stock_locations():
    """Insert stock locations into the database."""

    logger.start("Inserting stock locations into spree_stock_locations table...")

    try:
        # Load stock locations from JSON file
        if not STOCK_LOCATIONS_FILE.exists():
            logger.error(f"Stock locations file not found at {STOCK_LOCATIONS_FILE}. Run generate command first.")
            raise FileNotFoundError("Stock locations file not found")

        with Path.open(STOCK_LOCATIONS_FILE, encoding="utf-8") as f:
            data = json.load(f)

        stock_locations = data.get("stock_locations", [])
        logger.info(f"Loaded {len(stock_locations)} stock locations from {STOCK_LOCATIONS_FILE}")

        current_time = datetime.now()

        # Check if there's an existing default location (the shop location)
        existing_default = await db_client.fetchrow('SELECT id, name FROM spree_stock_locations WHERE "default" = true')

        # Process each stock location
        inserted_count = 0
        existing_count = 0
        updated_count = 0

        # Create a mapping from location ID to database ID
        stock_location_id_map = {}  # stock_location_id -> database_id

        for i, location_data in enumerate(stock_locations):
            try:
                # If this is the first location (our main warehouse) and there's an existing default, update it
                if i == 0 and existing_default and location_data.get("default", False):
                    # Update the existing default location instead of creating a new one
                    await db_client.execute(
                        """
                        UPDATE spree_stock_locations SET 
                            name = $1, address1 = $2, address2 = $3, city = $4, state_id = $5, 
                            state_name = $6, country_id = $7, zipcode = $8, phone = $9, 
                            active = $10, backorderable_default = $11, propagate_all_variants = $12, 
                            admin_name = $13, updated_at = $14
                        WHERE "default" = true
                        """,
                        location_data["name"],
                        location_data["address1"],
                        location_data.get("address2"),
                        location_data["city"],
                        location_data["state_id"],
                        location_data["state_name"],
                        location_data.get("country_id", 49),
                        location_data["zipcode"],
                        location_data["phone"],
                        location_data.get("active", True),
                        location_data.get("backorderable_default", False),
                        location_data.get("propagate_all_variants", False),
                        location_data["admin_name"],
                        current_time,
                    )
                    updated_count += 1
                    # Update the ID mapping
                    stock_location_id_map[location_data.get("id", i + 1)] = existing_default["id"]
                    logger.info(f"Updated existing default location: {existing_default['name']} -> {location_data['name']} (DB ID: {existing_default['id']})")
                    continue

                # Check if stock location already exists by name
                existing_location = await db_client.fetchrow("SELECT id FROM spree_stock_locations WHERE name = $1", location_data["name"])

                if existing_location:
                    existing_count += 1
                    # Update the ID mapping
                    stock_location_id_map[location_data.get("id", i + 1)] = existing_location["id"]
                    logger.info(f"Found existing stock location: {location_data['name']} (DB ID: {existing_location['id']})")
                    continue

                # Insert new stock location
                db_id = await db_client.fetchval(
                    """
                    INSERT INTO spree_stock_locations (
                        name, "default", address1, address2, city, state_id, state_name, 
                        country_id, zipcode, phone, active, backorderable_default, 
                        propagate_all_variants, admin_name, created_at, updated_at
                    )
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16)
                    RETURNING id
                    """,
                    location_data["name"],
                    location_data.get("default", False),
                    location_data["address1"],
                    location_data.get("address2"),
                    location_data["city"],
                    location_data["state_id"],
                    location_data["state_name"],
                    location_data.get("country_id", 49),
                    location_data["zipcode"],
                    location_data["phone"],
                    location_data.get("active", True),
                    location_data.get("backorderable_default", False),
                    location_data.get("propagate_all_variants", False),
                    location_data["admin_name"],
                    current_time,
                    current_time,
                )

                # Update the ID mapping
                stock_location_id_map[location_data.get("id", i + 1)] = db_id

                inserted_count += 1

            except Exception as e:
                logger.error(f"Failed to process stock location {location_data['name']}: {e}")
                continue

        logger.succeed("Successfully processed stock locations")

        state_distribution = await db_client.fetch("SELECT state_name, COUNT(*) as count FROM spree_stock_locations GROUP BY state_name ORDER BY count DESC")

        if state_distribution:
            logger.info("Stock locations by state:")
            for row in state_distribution:
                logger.info(f"  {row['state_name']}: {row['count']} location{'s' if row['count'] > 1 else ''}")

    except Exception as e:
        logger.error(f"Error seeding stock locations in database: {e}")
        raise
