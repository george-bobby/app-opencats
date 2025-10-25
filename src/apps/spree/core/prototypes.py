import json
from datetime import datetime
from pathlib import Path

from pydantic import BaseModel, Field

from apps.spree.config.settings import settings
from apps.spree.utils.ai import instructor_client
from apps.spree.utils.constants import (
    OPTION_TYPES_FILE,
    PROPERTIES_FILE,
    PROTOTYPES_FILE,
    TAXONS_FILE,
)
from apps.spree.utils.database import db_client
from common.logger import Logger


logger = Logger()


class Prototype(BaseModel):
    """Individual prototype model."""

    id: int = Field(description="Unique identifier for the prototype")  # noqa: A003, RUF100
    name: str = Field(description="Name of the prototype template")
    public_metadata: str = Field(description="Public metadata as JSON string", default="{}")
    private_metadata: str = Field(description="Private metadata as JSON string", default="{}")
    property_names: list[str] = Field(description="List of property names to associate with this prototype")
    option_type_names: list[str] = Field(description="List of option type names to associate with this prototype")
    taxon_names: list[str] = Field(description="List of taxon names to associate with this prototype")


class PrototypeForGeneration(BaseModel):
    """Prototype model for GPT generation (without ID)."""

    name: str = Field(description="Name of the prototype template")
    public_metadata: str = Field(description="Public metadata as JSON string", default="{}")
    private_metadata: str = Field(description="Private metadata as JSON string", default="{}")
    property_names: list[str] = Field(description="List of property names to associate with this prototype")
    option_type_names: list[str] = Field(description="List of option type names to associate with this prototype")
    taxon_names: list[str] = Field(description="List of taxon names to associate with this prototype")


class PrototypesResponse(BaseModel):
    """Response format for generated prototypes."""

    prototypes: list[PrototypeForGeneration]


async def generate_prototypes(number_of_prototypes: int) -> dict | None:
    """Generate realistic prototypes for a pet supplies eCommerce store."""

    logger.info("Generating prototypes for pet supplies store...")

    try:
        # Load existing data for context
        taxons_context = ""
        properties_context = ""
        option_types_context = ""

        # Load taxons
        taxons_file = TAXONS_FILE
        available_taxons = []
        if taxons_file.exists():
            try:
                with Path.open(taxons_file, encoding="utf-8") as f:
                    taxons_data = json.load(f)
                taxons = taxons_data.get("taxons", [])
                if taxons:
                    available_taxons = [taxon["name"] for taxon in taxons]
                    taxons_context = f"Available taxons: {', '.join(available_taxons)}"
                    logger.info(f"Loaded {len(taxons)} taxons for context")
            except Exception as e:
                logger.warning(f"Could not load taxons for context: {e}")

        # Load properties
        properties_file = PROPERTIES_FILE
        available_properties = []
        if properties_file.exists():
            try:
                with Path.open(properties_file, encoding="utf-8") as f:
                    properties_data = json.load(f)
                properties = properties_data.get("properties", [])
                if properties:
                    available_properties = [prop["name"] for prop in properties]
                    properties_context = f"Available properties: {', '.join(available_properties)}"
                    logger.info(f"Loaded {len(properties)} properties for context")
            except Exception as e:
                logger.warning(f"Could not load properties for context: {e}")

        # Load option types
        option_types_file = OPTION_TYPES_FILE
        available_option_types = []
        if option_types_file.exists():
            try:
                with Path.open(option_types_file, encoding="utf-8") as f:
                    option_types_data = json.load(f)
                option_types = option_types_data.get("option_types", [])
                if option_types:
                    available_option_types = [ot["name"] for ot in option_types]
                    option_types_context = f"Available option types: {', '.join(available_option_types)}"
                    logger.info(f"Loaded {len(option_types)} option types for context")
            except Exception as e:
                logger.warning(f"Could not load option types for context: {e}")

        system_prompt = f"""Generate {number_of_prototypes} realistic Prototypes for {settings.SPREE_STORE_NAME}, a {settings.DATA_THEME_SUBJECT}.

        Prototypes act as templates for quickly creating products with prefilled attributes.

        REQUIRED PROTOTYPES (create these specific ones):
        1. Dog Bed - Properties: material, dimensions, warranty - Option Types: size - Taxons: relevant dog/bed categories
        2. Cat Scratcher - Properties: material, dimensions - Option Types: size - Taxons: relevant cat categories  
        3. Travel Carrier - Properties: material, dimensions, weight - Option Types: size, color - Taxons: relevant travel categories
        4. Dog Treats - Properties: ingredients, expiration_date - Option Types: size - Taxons: relevant dog/treat categories
        5. Grooming Brush - Properties: material, care_instructions - Option Types: color - Taxons: relevant grooming categories
        6. Feeding Bowl - Properties: material, dimensions - Option Types: size, color - Taxons: relevant feeding categories
        7. Cat Toy - Properties: material, dimensions - Option Types: size - Taxons: relevant cat/toy categories
        8. Dog Jacket - Properties: material, care_instructions - Option Types: size, color - Taxons: relevant dog/apparel categories
        9. Pet Shampoo - Properties: ingredients, care_instructions - Option Types: size - Taxons: relevant grooming categories
        10. Training Clicker - Properties: material, dimensions - Option Types: color - Taxons: relevant training categories

        {taxons_context}
        {properties_context}
        {option_types_context}

        Each Prototype should have:
        - name: Descriptive name for the prototype template
        - public_metadata: JSON string with description and category info
        - private_metadata: JSON string with internal notes
        - property_names: Array of property names from the available properties list
        - option_type_names: Array of option type names from the available option types list  
        - taxon_names: Array of taxon names from the available taxons list (choose relevant subcategories)

        IMPORTANT: Only use property names, option type names, and taxon names that exist in the provided lists above.
        Choose the most relevant taxons for each prototype (prefer specific subcategories over broad categories)."""

        user_prompt = f"""Generate exactly {number_of_prototypes} Prototypes for {settings.SPREE_STORE_NAME}.

        Each Prototype must include:
        - name: Template name
        - public_metadata: JSON string with prototype description and usage info
        - private_metadata: JSON string with internal notes
        - property_names: Array of relevant property names (use exact names from available properties)
        - option_type_names: Array of relevant option type names (use exact names from available option types)
        - taxon_names: Array of relevant taxon names (use exact names from available taxons, prefer specific subcategories)

        Create prototypes that would be useful templates for common pet product types."""

        prototypes_response = await instructor_client.chat.completions.create(
            model="claude-3-5-haiku-latest",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            response_model=PrototypesResponse,
            temperature=0.3,
            max_tokens=8192,
        )

        if not prototypes_response or not prototypes_response.prototypes:
            logger.error("Failed to parse prototypes response from Anthropic")
            return None

        # Add incrementing IDs to prototypes
        prototypes_with_ids = []
        prototype_id = 1

        for generated_prototype in prototypes_response.prototypes:
            # Add ID to prototype
            prototype_with_id = Prototype(
                id=prototype_id,
                name=generated_prototype.name,
                public_metadata=generated_prototype.public_metadata,
                private_metadata=generated_prototype.private_metadata,
                property_names=generated_prototype.property_names,
                option_type_names=generated_prototype.option_type_names,
                taxon_names=generated_prototype.taxon_names,
            )
            prototypes_with_ids.append(prototype_with_id)
            prototype_id += 1

        # Convert to dict format
        prototypes_data = {
            "prototypes": [proto.model_dump() for proto in prototypes_with_ids],
            "available_taxons": available_taxons,
            "available_properties": available_properties,
            "available_option_types": available_option_types,
        }

        # Save to file
        settings.DATA_PATH.mkdir(parents=True, exist_ok=True)
        PROTOTYPES_FILE.parent.mkdir(parents=True, exist_ok=True)
        with Path.open(PROTOTYPES_FILE, "w", encoding="utf-8") as f:
            json.dump(prototypes_data, f, indent=2, ensure_ascii=False)

        logger.succeed(f"Successfully generated and saved {len(prototypes_with_ids)} prototypes to {PROTOTYPES_FILE}")

        # Log details about generated prototypes
        for proto in prototypes_with_ids:
            logger.info(f"Generated prototype: {proto.name} [ID: {proto.id}]")
            logger.info(f"  Properties: {', '.join(proto.property_names)}")
            logger.info(f"  Option Types: {', '.join(proto.option_type_names)}")
            logger.info(f"  Taxons: {', '.join(proto.taxon_names)}")

        return prototypes_data

    except Exception as e:
        logger.error(f"Error generating prototypes: {e}")
        raise


async def seed_prototypes():
    """Insert prototypes and their relationships into the database."""

    logger.start("Inserting prototypes and relationships into database tables...")

    try:
        # Load prototypes from JSON file
        if not PROTOTYPES_FILE.exists():
            logger.error(f"Prototypes file not found at {PROTOTYPES_FILE}. Run generate command first.")
            raise FileNotFoundError("Prototypes file not found")

        with Path.open(PROTOTYPES_FILE, encoding="utf-8") as f:
            data = json.load(f)

        prototypes = data.get("prototypes", [])
        logger.info(f"Loaded {len(prototypes)} prototypes from {PROTOTYPES_FILE}")

        current_time = datetime.now()

        # Get existing IDs for relationships
        logger.info("Loading existing taxon, property, and option type IDs...")

        # Load taxon IDs
        taxon_records = await db_client.fetch("SELECT id, name FROM spree_taxons")
        taxon_id_map = {record["name"]: record["id"] for record in taxon_records}
        logger.info(f"Found {len(taxon_id_map)} taxons in database")

        # Load property IDs
        property_records = await db_client.fetch("SELECT id, name FROM spree_properties")
        property_id_map = {record["name"]: record["id"] for record in property_records}
        logger.info(f"Found {len(property_id_map)} properties in database")

        # Load option type IDs
        option_type_records = await db_client.fetch("SELECT id, name FROM spree_option_types")
        option_type_id_map = {record["name"]: record["id"] for record in option_type_records}
        logger.info(f"Found {len(option_type_id_map)} option types in database")

        # Process each prototype
        inserted_prototypes = 0
        existing_prototypes = 0

        for prototype_data in prototypes:
            try:
                # Check if prototype already exists
                existing_prototype = await db_client.fetchrow("SELECT id FROM spree_prototypes WHERE name = $1", prototype_data["name"])

                if existing_prototype:
                    existing_prototypes += 1
                    prototype_id = existing_prototype["id"]
                    logger.info(f"Found existing prototype: {prototype_data['name']}")
                else:
                    # Insert new prototype
                    prototype_record = await db_client.fetchrow(
                        """
                        INSERT INTO spree_prototypes (name, created_at, updated_at, public_metadata, private_metadata)
                        VALUES ($1, $2, $3, $4, $5)
                        RETURNING id
                        """,
                        prototype_data["name"],
                        current_time,
                        current_time,
                        prototype_data.get("public_metadata", "{}"),
                        prototype_data.get("private_metadata", "{}"),
                    )

                    if not prototype_record:
                        logger.error(f"Failed to insert prototype: {prototype_data['name']}")
                        continue

                    prototype_id = prototype_record["id"]
                    inserted_prototypes += 1
                    logger.info(f"Inserted prototype: {prototype_data['name']}")

                # Insert prototype-taxon relationships
                taxon_names = prototype_data.get("taxon_names", [])
                for taxon_name in taxon_names:
                    if taxon_name in taxon_id_map:
                        taxon_id = taxon_id_map[taxon_name]

                        # Check if relationship already exists
                        existing_rel = await db_client.fetchrow("SELECT id FROM spree_prototype_taxons WHERE prototype_id = $1 AND taxon_id = $2", prototype_id, taxon_id)

                        if not existing_rel:
                            await db_client.execute(
                                """
                                INSERT INTO spree_prototype_taxons (prototype_id, taxon_id, created_at, updated_at)
                                VALUES ($1, $2, $3, $4)
                                """,
                                prototype_id,
                                taxon_id,
                                current_time,
                                current_time,
                            )
                    else:
                        logger.warning(f"Taxon not found: {taxon_name}")

                # Insert prototype-property relationships
                property_names = prototype_data.get("property_names", [])
                for property_name in property_names:
                    if property_name in property_id_map:
                        property_id = property_id_map[property_name]

                        # Check if relationship already exists
                        existing_rel = await db_client.fetchrow("SELECT id FROM spree_property_prototypes WHERE prototype_id = $1 AND property_id = $2", prototype_id, property_id)

                        if not existing_rel:
                            await db_client.execute(
                                """
                                INSERT INTO spree_property_prototypes (prototype_id, property_id, created_at, updated_at)
                                VALUES ($1, $2, $3, $4)
                                """,
                                prototype_id,
                                property_id,
                                current_time,
                                current_time,
                            )
                            logger.info(f"  Linked to property: {property_name}")
                    else:
                        logger.warning(f"  Property not found: {property_name}")

                # Insert prototype-option type relationships
                option_type_names = prototype_data.get("option_type_names", [])
                for option_type_name in option_type_names:
                    if option_type_name in option_type_id_map:
                        option_type_id = option_type_id_map[option_type_name]

                        # Check if relationship already exists
                        existing_rel = await db_client.fetchrow("SELECT id FROM spree_option_type_prototypes WHERE prototype_id = $1 AND option_type_id = $2", prototype_id, option_type_id)

                        if not existing_rel:
                            await db_client.execute(
                                """
                                INSERT INTO spree_option_type_prototypes (prototype_id, option_type_id, created_at, updated_at)
                                VALUES ($1, $2, $3, $4)
                                """,
                                prototype_id,
                                option_type_id,
                                current_time,
                                current_time,
                            )
                            logger.info(f"  Linked to option type: {option_type_name}")
                    else:
                        logger.warning(f"  Option type not found: {option_type_name}")

            except Exception as e:
                logger.error(f"Failed to process prototype {prototype_data['name']}: {e}")
                continue

        # Log summary
        total_prototypes = await db_client.fetchval("SELECT COUNT(*) FROM spree_prototypes")
        total_taxon_relations = await db_client.fetchval("SELECT COUNT(*) FROM spree_prototype_taxons")
        total_property_relations = await db_client.fetchval("SELECT COUNT(*) FROM spree_property_prototypes")
        total_option_type_relations = await db_client.fetchval("SELECT COUNT(*) FROM spree_option_type_prototypes")

        logger.succeed("Successfully processed prototypes:")
        logger.succeed(f"  - {inserted_prototypes} new prototypes inserted")
        logger.succeed(f"  - {existing_prototypes} existing prototypes found")
        logger.succeed(f"  - {total_prototypes} total prototypes in database")
        logger.succeed(f"  - {total_taxon_relations} prototype-taxon relationships")
        logger.succeed(f"  - {total_property_relations} prototype-property relationships")
        logger.succeed(f"  - {total_option_type_relations} prototype-option type relationships")

    except Exception as e:
        logger.error(f"Error seeding prototypes in database: {e}")
        raise
