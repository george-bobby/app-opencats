import json
from datetime import datetime
from pathlib import Path

from pydantic import BaseModel, Field

from apps.spree.config.settings import settings
from apps.spree.utils.ai import instructor_client
from apps.spree.utils.constants import PROPERTIES_FILE
from apps.spree.utils.database import db_client
from common.logger import Logger


logger = Logger()


class Property(BaseModel):
    """Individual property model."""

    name: str = Field(description="Internal name for the property (lowercase/underscored)")
    presentation: str = Field(description="Customer-facing label for the property")
    filterable: bool = Field(description="Whether this property can be used for filtering", default=False)
    filter_param: str | None = Field(description="URL parameter name for filtering", default=None)
    public_metadata: str = Field(description="Public metadata as JSON string", default="{}")
    private_metadata: str = Field(description="Private metadata as JSON string", default="{}")


class PropertiesResponse(BaseModel):
    """Response format for generated properties."""

    properties: list[Property]


async def generate_properties(number_of_properties: int) -> dict | None:
    """Generate realistic properties for a pet supplies eCommerce store."""

    logger.info("Generating properties for pet supplies store...")

    try:
        # Load existing taxons to understand product categories
        taxons_context = ""
        taxons_file = settings.DATA_PATH / "generated" / "taxons.json"

        if taxons_file.exists():
            try:
                with Path.open(taxons_file, encoding="utf-8") as f:
                    taxons_data = json.load(f)

                taxons = taxons_data.get("taxons", [])
                if taxons:
                    taxon_names = [taxon["name"] for taxon in taxons]
                    taxons_context = (
                        f"\n\nExisting product categories (taxons) in the store:\n{', '.join(taxon_names)}\n\nCreate properties that would be relevant for products in these categories."
                    )
                    logger.info(f"Loaded {len(taxons)} existing taxons for context")
                else:
                    logger.info("No taxons found in file")
            except Exception as e:
                logger.warning(f"Could not load taxons for context: {e}")
        else:
            logger.info("No taxons file found, generating properties without category context")

        system_prompt = f"""Generate {number_of_properties} realistic Properties for {settings.SPREE_STORE_NAME}, a {settings.DATA_THEME_SUBJECT}.

        Properties are used to describe product characteristics and features that don't vary (unlike option types which create variants).

        EXAMPLE PROPERTIES:
        1. material - Material
        2. care_instructions - Care Instructions  
        3. country_of_origin - Country of Origin
        4. expiration_date - Expiration Date
        5. ingredients - Ingredients
        6. dimensions - Dimensions
        7. weight - Weight
        8. warranty - Warranty Information

        If you need more than 10 properties, add relevant ones for a pet supplies store such as:
        - brand (e.g., Purina, Hill's, Blue Buffalo, Kong, Petco)
        - activity_level (e.g., Low, Moderate, High, Very Active)
        - indoor_outdoor (e.g., Indoor Only, Outdoor Only, Both)
        - special_features (e.g., Waterproof, Dishwasher Safe, Non-Slip, Squeaky)
        - nutritional_focus (e.g., High Protein, Grain Free, Limited Ingredient, Weight Management)
        - training_type (e.g., Obedience, Agility, Behavioral, House Training)
        - safety_rating (e.g., Child Safe, Non-Toxic, Choking Hazard Warning)
        - durability_level (e.g., Light Use, Regular Use, Heavy Duty, Indestructible){taxons_context}

        Each Property should have:
        - name: Internal identifier (lowercase_underscored, exactly as specified above)
        - presentation: Customer-facing label (exactly as specified above)
        - filterable: true for properties customers might filter by (material, age_range, breed_size, etc.), false for informational only (care_instructions, warranty, etc.)
        - filter_param: URL-friendly parameter name (same as name if filterable, null if not filterable)
        - public_metadata: JSON string with description and usage info
        - private_metadata: JSON string with internal notes and data source info

        Focus on the required properties first, then add supplementary ones if needed."""

        user_prompt = f"""Generate exactly {number_of_properties} Properties for {settings.SPREE_STORE_NAME}.

        Each Property must include:
        - name: Internal identifier (lowercase_underscored)
        - presentation: Customer-facing label
        - filterable: true if customers should be able to filter by this property
        - filter_param: URL parameter name (same as name if filterable, null if not)
        - public_metadata: JSON string with property description and category info
        - private_metadata: JSON string with internal usage notes

        Make properties that would be useful for describing and filtering pet products."""

        properties_response = await instructor_client.chat.completions.create(
            model="claude-3-5-haiku-latest",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            response_model=PropertiesResponse,
            temperature=0.3,
            max_tokens=8192,
        )

        if not properties_response or not properties_response.properties:
            logger.error("Failed to parse properties response from AI")
            return None

        # Convert to dict format
        properties_data = {"properties": [prop.model_dump() for prop in properties_response.properties]}

        # Save to file
        settings.DATA_PATH.mkdir(parents=True, exist_ok=True)
        PROPERTIES_FILE.parent.mkdir(parents=True, exist_ok=True)
        with Path.open(PROPERTIES_FILE, "w", encoding="utf-8") as f:
            json.dump(properties_data, f, indent=2, ensure_ascii=False)

        logger.succeed(f"Successfully generated and saved {len(properties_response.properties)} properties to {PROPERTIES_FILE}")

        # Log details about generated properties
        filterable_count = sum(1 for prop in properties_response.properties if prop.filterable)
        logger.info(f"Generated {len(properties_response.properties)} properties ({filterable_count} filterable)")

        for prop in properties_response.properties:
            filter_info = " [filterable]" if prop.filterable else ""
            logger.info(f"Generated property: {prop.presentation} ({prop.name}){filter_info}")

        return properties_data

    except Exception as e:
        logger.error(f"Error generating properties: {e}")
        raise


async def seed_properties():
    """Insert properties into the database."""

    logger.start("Inserting properties into spree_properties table...")

    try:
        # Load properties from JSON file
        if not PROPERTIES_FILE.exists():
            logger.error(f"Properties file not found at {PROPERTIES_FILE}. Run generate command first.")
            raise FileNotFoundError("Properties file not found")

        with Path.open(PROPERTIES_FILE, encoding="utf-8") as f:
            data = json.load(f)

        properties = data.get("properties", [])
        logger.info(f"Loaded {len(properties)} properties from {PROPERTIES_FILE}")

        current_time = datetime.now()

        # Process each property
        inserted_count = 0
        existing_count = 0

        for property_data in properties:
            try:
                # Check if property already exists
                existing_property = await db_client.fetchrow("SELECT id FROM spree_properties WHERE name = $1", property_data["name"])

                if existing_property:
                    existing_count += 1
                    logger.info(f"Found existing property: {property_data['presentation']}")
                    continue

                # Insert new property
                await db_client.execute(
                    """
                    INSERT INTO spree_properties (name, presentation, created_at, updated_at,
                                                filterable, filter_param, public_metadata, private_metadata)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                    """,
                    property_data["name"],
                    property_data["presentation"],
                    current_time,
                    current_time,
                    property_data.get("filterable", False),
                    property_data.get("filter_param"),
                    property_data.get("public_metadata", "{}"),
                    property_data.get("private_metadata", "{}"),
                )

                inserted_count += 1

            except Exception as e:
                logger.error(f"Failed to process property {property_data['name']}: {e}")
                continue

        # Log summary
        total_properties = await db_client.fetchval("SELECT COUNT(*) FROM spree_properties")
        filterable_properties = await db_client.fetchval("SELECT COUNT(*) FROM spree_properties WHERE filterable = true")

        logger.succeed("Successfully processed properties:")
        logger.succeed(f"  - {inserted_count} new properties inserted")
        logger.succeed(f"  - {existing_count} existing properties found")
        logger.succeed(f"  - {total_properties} total properties in database")
        logger.succeed(f"  - {filterable_properties} filterable properties available")

    except Exception as e:
        logger.error(f"Error seeding properties in database: {e}")
        raise
