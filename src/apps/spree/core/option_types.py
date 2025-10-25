import json
from datetime import datetime
from pathlib import Path

from pydantic import BaseModel, Field

from apps.spree.config.settings import settings
from apps.spree.utils.ai import instructor_client
from apps.spree.utils.constants import OPTION_TYPES_FILE
from apps.spree.utils.database import db_client
from common.logger import Logger


logger = Logger()


class OptionValue(BaseModel):
    """Individual option value model."""

    id: int = Field(description="Unique identifier for the option value")  # noqa: A003, RUF100
    name: str = Field(description="Internal name for the option value (lowercase/underscored)")
    presentation: str = Field(description="Customer-facing label for the option value")
    position: int = Field(description="Position/order of this value within the option type")


class OptionType(BaseModel):
    """Individual option type model."""

    id: int = Field(description="Unique identifier for the option type")  # noqa: A003, RUF100
    name: str = Field(description="Internal name for the option type (lowercase/underscored)")
    presentation: str = Field(description="Customer-facing label for the option type")
    position: int = Field(description="Position/order of this option type")
    filterable: bool = Field(description="Whether this option type can be used for filtering", default=True)
    public_metadata: str = Field(description="Public metadata as JSON string", default="{}")
    private_metadata: str = Field(description="Private metadata as JSON string", default="{}")
    option_values: list[OptionValue] = Field(description="List of option values for this type")


class OptionValueForGeneration(BaseModel):
    """Option value model for GPT generation (without ID)."""

    name: str = Field(description="Internal name for the option value (lowercase/underscored)")
    presentation: str = Field(description="Customer-facing label for the option value")
    position: int = Field(description="Position/order of this value within the option type")


class OptionTypeForGeneration(BaseModel):
    """Option type model for GPT generation (without ID)."""

    name: str = Field(description="Internal name for the option type (lowercase/underscored)")
    presentation: str = Field(description="Customer-facing label for the option type")
    position: int = Field(description="Position/order of this option type")
    filterable: bool = Field(description="Whether this option type can be used for filtering", default=True)
    public_metadata: str = Field(description="Public metadata as JSON string", default="{}")
    private_metadata: str = Field(description="Private metadata as JSON string", default="{}")
    option_values: list[OptionValueForGeneration] = Field(description="List of option values for this type")


class OptionTypesResponse(BaseModel):
    """Response format for generated option types."""

    option_types: list[OptionTypeForGeneration]


async def generate_option_types(number_of_option_types: int) -> dict | None:
    """Generate realistic option types for a pet supplies eCommerce store."""

    logger.info("Generating option types for pet supplies store...")

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
                        f"\n\nExisting product categories (taxons) in the store:\n{', '.join(taxon_names)}\n\nCreate option types that would be relevant for products in these categories."
                    )
                    logger.info(f"Loaded {len(taxons)} existing taxons for context")
                else:
                    logger.info("No taxons found in file")
            except Exception as e:
                logger.warning(f"Could not load taxons for context: {e}")
        else:
            logger.info("No taxons file found, generating option types without category context")

        system_prompt = f"""Generate {number_of_option_types} realistic Option Types for {settings.SPREE_STORE_NAME}, a {settings.DATA_THEME_SUBJECT}.

        These Option Types will be used for defining product variants like size, color, flavor, etc.

        For a pet supplies store, create relevant option types such as:
        - size (Small, Medium, Large, X-Large)
        - color (Red, Blue, Green, Black, Brown, Pink, etc.)
        - flavor (Chicken, Beef, Fish, Peanut Butter, Sweet Potato, etc.)
        - weight (8oz, 16oz, 32oz, 5lb, 10lb, etc.)
        - material (Cotton, Nylon, Leather, Rope, Plush, etc.)
        - texture (Soft, Crunchy, Chewy){taxons_context}

        Each Option Type should have:
        - name: Internal name (lowercase, underscored, no spaces)
        - presentation: Customer-facing label (proper case)
        - position: Sequential numbering starting from 1
        - filterable: true (allows customers to filter by this option)
        - public_metadata: JSON string with relevant info
        - private_metadata: JSON string with internal notes
        - option_values: At least 3-6 realistic values for each type

        Make sure the option values are relevant to pet supplies and would realistically be used for product variants."""

        user_prompt = f"""Generate exactly {number_of_option_types} Option Types for {settings.SPREE_STORE_NAME}.

        Each Option Type must include:
        - name: Internal identifier (lowercase_underscored)
        - presentation: Customer-facing label
        - position: Sequential position (1, 2, 3, etc.)
        - filterable: true
        - public_metadata: JSON string with description and category info
        - private_metadata: JSON string with internal usage notes
        - option_values: Array of 5-15 option values, each with:
          - name: Internal name (lowercase_underscored)
          - presentation: Customer display name
          - position: Sequential position within the option type

        Focus on options that would be commonly used for pet product variants."""

        option_types_response = await instructor_client.chat.completions.create(
            model="claude-3-5-haiku-latest",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            response_model=OptionTypesResponse,
            temperature=0.3,
            max_tokens=8192,
        )

        if not option_types_response or not option_types_response.option_types:
            logger.error("Failed to parse option types response from AI")
            return None

        # Add incrementing IDs to option types and option values
        option_types_with_ids = []
        option_type_id = 1
        option_value_id = 1

        for generated_option_type in option_types_response.option_types:
            # Add IDs to option values first
            option_values_with_ids = []
            for generated_option_value in generated_option_type.option_values:
                option_value_with_id = OptionValue(
                    id=option_value_id,
                    name=generated_option_value.name,
                    presentation=generated_option_value.presentation,
                    position=generated_option_value.position,
                )
                option_values_with_ids.append(option_value_with_id)
                option_value_id += 1

            # Add ID to option type
            option_type_with_id = OptionType(
                id=option_type_id,
                name=generated_option_type.name,
                presentation=generated_option_type.presentation,
                position=generated_option_type.position,
                filterable=generated_option_type.filterable,
                public_metadata=generated_option_type.public_metadata,
                private_metadata=generated_option_type.private_metadata,
                option_values=option_values_with_ids,
            )
            option_types_with_ids.append(option_type_with_id)
            option_type_id += 1

        # Convert to dict format
        option_types_data = {"option_types": [ot.model_dump() for ot in option_types_with_ids]}

        # Save to file
        settings.DATA_PATH.mkdir(parents=True, exist_ok=True)
        OPTION_TYPES_FILE.parent.mkdir(parents=True, exist_ok=True)
        with Path.open(OPTION_TYPES_FILE, "w", encoding="utf-8") as f:
            json.dump(option_types_data, f, indent=2, ensure_ascii=False)

        logger.succeed(f"Successfully generated and saved {len(option_types_with_ids)} option types to {OPTION_TYPES_FILE}")

        # Log details about generated option types
        for ot in option_types_with_ids:
            logger.info(f"Generated option type: {ot.presentation} ({ot.name}) [ID: {ot.id}] with {len(ot.option_values)} values")
            for ov in ot.option_values:
                logger.info(f"  - {ov.presentation} ({ov.name}) [ID: {ov.id}]")

        return option_types_data

    except Exception as e:
        logger.error(f"Error generating option types: {e}")
        raise


async def seed_option_types():
    """Insert option types and their values into the database."""

    logger.info("Inserting option types and values into spree_option_types and spree_option_values tables...")

    try:
        # Load option types from JSON file
        if not OPTION_TYPES_FILE.exists():
            logger.error(f"Option types file not found at {OPTION_TYPES_FILE}. Run generate command first.")
            raise FileNotFoundError("Option types file not found")

        with Path.open(OPTION_TYPES_FILE, encoding="utf-8") as f:
            data = json.load(f)

        option_types = data.get("option_types", [])
        logger.info(f"Loaded {len(option_types)} option types from {OPTION_TYPES_FILE}")

        current_time = datetime.now()

        # Process each option type
        for option_type_data in option_types:
            try:
                # Check if option type already exists
                existing_option_type = await db_client.fetchrow("SELECT id FROM spree_option_types WHERE name = $1", option_type_data["name"])

                if existing_option_type:
                    option_type_id = existing_option_type["id"]
                    logger.info(f"Found existing option type: {option_type_data['presentation']}")
                else:
                    # Insert new option type
                    option_type_record = await db_client.fetchrow(
                        """
                        INSERT INTO spree_option_types (name, presentation, position, created_at, updated_at,
                                                      filterable, public_metadata, private_metadata)
                        VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                        RETURNING id
                        """,
                        option_type_data["name"],
                        option_type_data["presentation"],
                        option_type_data["position"],
                        current_time,
                        current_time,
                        option_type_data.get("filterable", True),
                        option_type_data.get("public_metadata", "{}"),
                        option_type_data.get("private_metadata", "{}"),
                    )

                    if not option_type_record:
                        logger.error(f"Failed to insert option type: {option_type_data['name']}")
                        continue

                    option_type_id = option_type_record["id"]

                # Process option values for this option type
                option_values = option_type_data.get("option_values", [])

                for option_value_data in option_values:
                    try:
                        # Check if option value already exists
                        existing_option_value = await db_client.fetchrow(
                            "SELECT id FROM spree_option_values WHERE name = $1 AND option_type_id = $2", option_value_data["name"], option_type_id
                        )

                        if existing_option_value:
                            logger.info(f"  Found existing option value: {option_value_data['presentation']}")
                            continue

                        # Insert new option value
                        await db_client.execute(
                            """
                            INSERT INTO spree_option_values (position, name, presentation, option_type_id,
                                                           created_at, updated_at, public_metadata, private_metadata)
                            VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                            """,
                            option_value_data["position"],
                            option_value_data["name"],
                            option_value_data["presentation"],
                            option_type_id,
                            current_time,
                            current_time,
                            "{}",  # public_metadata
                            "{}",  # private_metadata
                        )

                    except Exception as e:
                        logger.error(f"Failed to insert option value {option_value_data['name']}: {e}")
                        continue

            except Exception as e:
                logger.error(f"Failed to process option type {option_type_data['name']}: {e}")
                continue

        # Log summary
        option_types_count = await db_client.fetchval("SELECT COUNT(*) FROM spree_option_types")
        option_values_count = await db_client.fetchval("SELECT COUNT(*) FROM spree_option_values")

        logger.succeed("Successfully processed option types. Database now contains:")
        logger.succeed(f"  - {option_types_count} option types")
        logger.succeed(f"  - {option_values_count} option values")

    except Exception as e:
        logger.error(f"Error seeding option types in database: {e}")
        raise
