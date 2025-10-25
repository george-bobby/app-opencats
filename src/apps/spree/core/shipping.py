import json
from pathlib import Path

from pydantic import BaseModel, Field

from apps.spree.config.settings import settings
from apps.spree.utils.ai import instructor_client
from apps.spree.utils.constants import SHIPPING_CATEGORIES, SHIPPING_ZONES
from common.logger import Logger


logger = Logger()

SHIPPING_METHODS_FILE = settings.DATA_PATH / "generated" / "shipping_methods.json"


# Removed ShippingZone models as we're using constants directly


class ShippingMethod(BaseModel):
    """Individual shipping method model."""

    id: int = Field(description="Unique ID for the shipping method")  # noqa: A003, RUF100
    name: str = Field(description="Clear, descriptive name for the shipping method")
    admin_name: str = Field(description="Internal admin name for the shipping method")
    display_on: str = Field(description="Where to display: 'both', 'front_end', or 'back_end'")
    tracking_url: str = Field(description="URL template for tracking packages (can be empty)")
    code: str = Field(description="Unique code for the shipping method (e.g. 'STD-001', 'EXP-002', etc.)")
    tax_category_code: str = Field(description="Must be one of the available tax category codes")
    shipping_category_ids: list[int] = Field(description="List of shipping category IDs (1=Default, 2=Digital)")
    calculator_type: str = Field(description="Calculator type: 'flat_rate', 'flexible_rate', 'per_item', 'free', 'price_sack', 'flat_percent', or 'digital'")
    calculator_amount: float = Field(description="Base amount for the calculator (in dollars)")
    zone_ids: list[int] = Field(description="List of shipping zone IDs this method applies to", default=[0])
    deleted_at: None = Field(description="Always null for new shipping methods")


class ShippingMethodResponse(BaseModel):
    """Response format for generated shipping methods."""

    shipping_methods: list[ShippingMethod]


async def seed_shipping_categories():
    """Ensure shipping categories exist in the database."""
    from apps.spree.utils.database import db_client

    logger.start("Ensuring shipping categories exist in spree_shipping_categories table...")

    try:
        inserted_count = 0
        for category in SHIPPING_CATEGORIES:
            category_id = int(category["id"])
            category_name = category["name"]

            # Check if category already exists
            existing_category = await db_client.fetchrow("SELECT id FROM spree_shipping_categories WHERE id = $1", category_id)

            if existing_category:
                # Update existing category
                await db_client.execute(
                    """
                    UPDATE spree_shipping_categories 
                    SET name = $1, updated_at = NOW()
                    WHERE id = $2
                    """,
                    category_name,
                    category_id,
                )
                logger.info(f"Updated existing shipping category: {category_name} (ID: {category_id})")
            else:
                # Insert new category
                await db_client.execute(
                    """
                    INSERT INTO spree_shipping_categories (id, name, created_at, updated_at)
                    VALUES ($1, $2, NOW(), NOW())
                    """,
                    category_id,
                    category_name,
                )
                logger.info(f"Inserted new shipping category: {category_name} (ID: {category_id})")

            inserted_count += 1

        logger.succeed(f"Successfully processed {inserted_count} shipping categories in the database")

    except Exception as e:
        logger.error(f"Error seeding shipping categories in database: {e}")
        raise


async def generate_shipping_methods(number_of_methods: int) -> dict | None:
    """Generate realistic US shipping methods for a pet supplies eCommerce store.
    At least one shipping method will be associated with North America (zone ID 1).
    """

    logger.info("Generating US shipping methods...")

    try:
        # Load existing tax categories to get their codes
        tax_categories_file = settings.DATA_PATH / "generated" / "tax_categories.json"
        if not tax_categories_file.exists():
            logger.error(f"Tax categories file not found at {tax_categories_file}. Generate tax categories first.")
            raise FileNotFoundError("Tax categories file not found")

        with Path.open(tax_categories_file, encoding="utf-8") as f:
            categories_data = json.load(f)

        tax_categories = categories_data.get("tax_categories", [])
        if not tax_categories:
            logger.error("No tax categories found in the file")
            raise ValueError("No tax categories available")

        category_codes = [cat["tax_code"] for cat in tax_categories]
        logger.info(f"Found {len(category_codes)} tax category codes: {', '.join(category_codes)}")

        # Get shipping category info
        shipping_category_info = ", ".join([f"{cat['id']}={cat['name']}" for cat in SHIPPING_CATEGORIES])

        # Get shipping zone info
        shipping_zone_info = ", ".join([f"{zone['id']}={zone['name']}" for zone in SHIPPING_ZONES])

        system_prompt = f"""Generate {number_of_methods} realistic shipping methods for {settings.SPREE_STORE_NAME}.
        
        Available tax category codes: {", ".join(category_codes)}
        Available shipping categories: {shipping_category_info}
        Available shipping zones: {shipping_zone_info}
        
        Create shipping methods that cover:
        - Standard ground shipping
        - Express/expedited shipping  
        - Overnight/next-day delivery
        - Digital delivery (for digital products)
        - Local delivery/pickup
        - International shipping
        
        IMPORTANT: Do NOT generate any free shipping options. All shipping methods must have a cost.
        
        Make the methods realistic for a US-based pet supplies store with appropriate costs and delivery times.
        Use realistic carrier names like UPS, FedEx, USPS, DHL, etc.
        
        For display_on field, use:
        - 'both' for customer-facing and admin methods
        - 'front_end' for customer-only methods  
        - 'back_end' for admin-only methods
        
        For tracking_url, use realistic tracking URL templates or leave empty.
        Most methods should use shipping_category_ids: [1] (Default), but digital products should use [2] (Digital).
        
        For zone_ids, assign appropriate shipping zones based on the method:
        - For domestic US shipping: use [3] (NORTH AMERICA)
        - For international shipping: use appropriate zones like [1] (EU_VAT), [4] (SOUTH AMERICA), etc.
        - For worldwide shipping: include multiple zone IDs like [1, 2, 3, 4, 5, 6]
        - Each shipping method must have at least one zone
        
        For calculator_type, use:
        - 'flat_rate' for standard fixed-price shipping (most common)
        - 'flexible_rate' for tiered pricing based on order total
        - 'per_item' for per-item shipping charges
        - 'price_sack' for threshold-based pricing (e.g., cheaper if order > $50)
        - 'flat_percent' for percentage-based shipping cost
        - 'digital' for digital product delivery
        
        IMPORTANT: Do NOT use 'free' as a calculator_type. All shipping methods must have a cost greater than 0.00.
        
        For calculator_amount, use realistic shipping costs in USD (e.g., 5.99, 12.95) - all values must be greater than 0.00.
        """

        user_prompt = f"""Generate {number_of_methods} realistic shipping methods for {settings.SPREE_STORE_NAME}."""

        shipping_response = await instructor_client.chat.completions.create(
            model="claude-3-5-haiku-latest",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            response_model=ShippingMethodResponse,
            temperature=0.3,
            max_tokens=8192,
        )

        # Ensure at least one shipping method is associated with North America (zone ID 1)
        if shipping_response and shipping_response.shipping_methods:
            has_north_america = any(1 in method.zone_ids for method in shipping_response.shipping_methods)
            if not has_north_america and shipping_response.shipping_methods:
                # Add North America to the first method if no method has it
                shipping_response.shipping_methods[0].zone_ids.append(1)
                logger.info(f"Added North America zone to shipping method: {shipping_response.shipping_methods[0].name}")

            # Assign sequential IDs to each shipping method
            for i, method in enumerate(shipping_response.shipping_methods, start=1):
                # We manually assign IDs rather than letting the LLM generate them
                method.id = i
                logger.info(f"Assigned ID {i} to shipping method: {method.name}")

        if shipping_response and shipping_response.shipping_methods:
            # Convert to dict format for JSON serialization
            methods_list = [method.model_dump() for method in shipping_response.shipping_methods]
            methods_dict = {"shipping_methods": methods_list}

            # Save to file
            settings.DATA_PATH.mkdir(parents=True, exist_ok=True)
            SHIPPING_METHODS_FILE.parent.mkdir(parents=True, exist_ok=True)
            with Path.open(SHIPPING_METHODS_FILE, "w", encoding="utf-8") as f:
                json.dump(methods_dict, f, indent=2, ensure_ascii=False)

            logger.succeed(f"Successfully generated and saved {len(shipping_response.shipping_methods)} shipping methods to {SHIPPING_METHODS_FILE}")
            return methods_dict
        else:
            logger.error("Failed to parse shipping methods response from AI")
            raise ValueError("Failed to generate shipping methods")

    except Exception as e:
        logger.error(f"Error generating shipping methods: {e}")
        raise


async def _create_calculator(shipping_method_id: int, calculator_type: str, amount: float):
    """Create a calculator for a shipping method."""
    from apps.spree.utils.database import db_client

    # Map our calculator types to Spree calculator classes
    calculator_class_map = {
        "flat_rate": "Spree::Calculator::Shipping::FlatRate",
        "flexible_rate": "Spree::Calculator::Shipping::FlexiRate",
        "per_item": "Spree::Calculator::Shipping::PerItem",
        "free": "Spree::Calculator::Shipping::FlatRate",  # Free shipping uses flat rate with 0 amount
        "price_sack": "Spree::Calculator::Shipping::PriceSack",
        "flat_percent": "Spree::Calculator::Shipping::FlatPercentItemTotal",
        "digital": "Spree::Calculator::Shipping::DigitalDelivery",
    }

    calculator_class = calculator_class_map.get(calculator_type, "Spree::Calculator::Shipping::FlatRate")

    # Use the amount directly as BigDecimal doesn't need conversion to cents
    amount_value = amount if calculator_type != "free" else 0

    # Create YAML preferences based on calculator type
    if calculator_type == "flat_rate" or calculator_type == "free":
        # FlatRate preferences
        preferences = f"""---
:currency: USD
:amount: !ruby/object:BigDecimal 18:{amount_value}
:minimum_item_total:
:maximum_item_total:
:minimum_weight:
:maximum_weight:
"""
    elif calculator_type == "flexible_rate":
        # FlexiRate preferences
        first_item = amount_value
        additional_item = max(1, amount_value / 2)  # Half price for additional items
        preferences = f"""---
:first_item: !ruby/object:BigDecimal 18:{first_item}
:additional_item: !ruby/object:BigDecimal 18:{additional_item}
:max_items: 0
:currency: USD
"""
    elif calculator_type == "per_item":
        # PerItem preferences
        preferences = f"""---
:currency: USD
:amount: !ruby/object:BigDecimal 18:{amount_value}
"""
    elif calculator_type == "price_sack":
        # PriceSack preferences
        minimal_amount = 50.0  # $50.00
        normal_amount = amount_value
        discount_amount = 0 if amount_value == 0 else amount_value / 2
        preferences = f"""---
:currency: USD
:minimal_amount: !ruby/object:BigDecimal 18:{minimal_amount}
:normal_amount: !ruby/object:BigDecimal 18:{normal_amount}
:discount_amount: !ruby/object:BigDecimal 18:{discount_amount}
"""
    elif calculator_type == "flat_percent":
        # FlatPercentItemTotal preferences
        percent = 10  # Default 10%
        preferences = f"""---
:flat_percent: !ruby/object:BigDecimal 18:{percent}.0
"""
    elif calculator_type == "digital":
        # DigitalDelivery preferences
        preferences = """---
:currency: USD
:amount: !ruby/object:BigDecimal 18:0.0
"""
    else:
        # Default FlatRate preferences
        preferences = f"""---
:currency: USD
:amount: !ruby/object:BigDecimal 18:{amount_value}
"""

    try:
        # Check if calculator already exists for this shipping method
        existing_calculator = await db_client.fetchrow("SELECT id FROM spree_calculators WHERE calculable_type = 'Spree::ShippingMethod' AND calculable_id = $1", shipping_method_id)

        if existing_calculator:
            # Mark the existing calculator as deleted
            await db_client.execute(
                """
                UPDATE spree_calculators 
                SET deleted_at = NOW()
                WHERE calculable_type = 'Spree::ShippingMethod' AND calculable_id = $1
                """,
                shipping_method_id,
            )
            logger.info(f"Marked existing calculator for shipping method {shipping_method_id} as deleted")

            # Create new calculator
            await db_client.execute(
                """
                INSERT INTO spree_calculators (type, calculable_type, calculable_id, preferences, created_at, updated_at)
                VALUES ($1, $2, $3, $4, NOW(), NOW())
                """,
                calculator_class,
                "Spree::ShippingMethod",
                shipping_method_id,
                preferences,
            )
            logger.info(f"Created new calculator for shipping method {shipping_method_id}: {calculator_class}")
        else:
            # Create new calculator
            await db_client.execute(
                """
                INSERT INTO spree_calculators (type, calculable_type, calculable_id, preferences, created_at, updated_at)
                VALUES ($1, $2, $3, $4, NOW(), NOW())
                """,
                calculator_class,
                "Spree::ShippingMethod",
                shipping_method_id,
                preferences,
            )
            logger.info(f"Created calculator for shipping method {shipping_method_id}: {calculator_class}")

    except Exception as e:
        logger.error(f"Failed to create calculator for shipping method {shipping_method_id}: {e}")
        raise


async def seed_shipping_methods():
    """Insert shipping methods into the database."""
    from apps.spree.utils.database import db_client

    logger.start("Inserting shipping methods into spree_shipping_methods table...")

    try:
        # First ensure shipping categories exist
        await seed_shipping_categories()

        # Load shipping methods from JSON file
        if not SHIPPING_METHODS_FILE.exists():
            logger.error(f"Shipping methods file not found at {SHIPPING_METHODS_FILE}. Run generate command first.")
            raise FileNotFoundError("Shipping methods file not found")

        with Path.open(SHIPPING_METHODS_FILE, encoding="utf-8") as f:
            data = json.load(f)

        shipping_methods = data.get("shipping_methods", [])
        logger.info(f"Loaded {len(shipping_methods)} shipping methods from {SHIPPING_METHODS_FILE}")

        # Insert each shipping method into the database
        inserted_count = 0
        for method in shipping_methods:
            try:
                # Look up tax_category_id by tax_code
                tax_category = await db_client.fetchrow("SELECT id FROM spree_tax_categories WHERE tax_code = $1", method["tax_category_code"])

                if not tax_category:
                    logger.warning(f"Tax category not found for code '{method['tax_category_code']}', skipping method '{method['name']}'")
                    continue

                tax_category_id = tax_category["id"]

                # Get the pre-generated ID
                shipping_method_id = method["id"]

                # Check if shipping method with this ID already exists
                existing_method = await db_client.fetchrow("SELECT id FROM spree_shipping_methods WHERE id = $1", shipping_method_id)

                if existing_method:
                    # Update existing method
                    await db_client.execute(
                        """
                        UPDATE spree_shipping_methods 
                        SET name = $1, display_on = $2, tracking_url = $3, admin_name = $4, 
                            tax_category_id = $5, code = $6, 
                            public_metadata = $7, private_metadata = $8, updated_at = NOW()
                        WHERE id = $9
                        """,
                        method["name"],
                        method["display_on"],
                        method.get("tracking_url", ""),
                        method["admin_name"],
                        tax_category_id,
                        method["code"],
                        json.dumps({}),
                        json.dumps({}),
                        shipping_method_id,
                    )
                    logger.info(f"Updated existing shipping method: {method['name']} (ID: {shipping_method_id})")
                else:
                    # Insert new method with the pre-generated ID
                    await db_client.execute(
                        """
                        INSERT INTO spree_shipping_methods (id, name, display_on, tracking_url, admin_name, 
                                                          tax_category_id, code, public_metadata, private_metadata,
                                                          created_at, updated_at, deleted_at)
                        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, NOW(), NOW(), $10)
                        """,
                        shipping_method_id,
                        method["name"],
                        method["display_on"],
                        method.get("tracking_url", ""),
                        method["admin_name"],
                        tax_category_id,
                        method["code"],
                        json.dumps({}),
                        json.dumps({}),
                        method.get("deleted_at"),
                    )
                    logger.info(f"Inserted new shipping method: {method['name']} (ID: {shipping_method_id})")

                # Create calculator for the shipping method
                if shipping_method_id:
                    await _create_calculator(shipping_method_id, method.get("calculator_type", "flat_rate"), method.get("calculator_amount", 5.99))

                    # Handle shipping method categories
                    await _seed_shipping_method_categories(shipping_method_id, method.get("shipping_category_ids", [1]))

                    # Handle shipping method zones
                    await _seed_shipping_method_zones(shipping_method_id, method.get("zone_ids", [0]))

                inserted_count += 1

            except Exception as e:
                logger.error(f"Failed to insert/update shipping method {method['name']}: {e}")
                continue

        logger.succeed(f"Successfully processed {inserted_count} shipping methods in the database")

    except Exception as e:
        logger.error(f"Error seeding shipping methods in database: {e}")
        raise


async def _seed_shipping_method_categories(shipping_method_id: int, shipping_category_ids: list[int]):
    """Insert shipping method categories associations."""
    from apps.spree.utils.database import db_client

    try:
        # First, remove existing associations for this shipping method
        await db_client.execute("DELETE FROM spree_shipping_method_categories WHERE shipping_method_id = $1", shipping_method_id)

        # Insert new associations
        for category_id in shipping_category_ids:
            await db_client.execute(
                """
                INSERT INTO spree_shipping_method_categories (shipping_method_id, shipping_category_id, created_at, updated_at)
                VALUES ($1, $2, NOW(), NOW())
                """,
                shipping_method_id,
                category_id,
            )

    except Exception as e:
        logger.error(f"Failed to associate shipping method {shipping_method_id} with categories: {e}")
        raise


async def _seed_shipping_method_zones(shipping_method_id: int, zone_ids: list[int]):
    """Insert shipping method zones associations.
    Ensures that at least one shipping method is associated with North America (zone ID 1).
    """
    from apps.spree.utils.database import db_client

    try:
        # First, remove existing associations for this shipping method
        await db_client.execute("DELETE FROM spree_shipping_method_zones WHERE shipping_method_id = $1", shipping_method_id)

        # Ensure North America (zone ID 3) is included if no zones are specified
        if not zone_ids:
            zone_ids = [3]  # Default to North America

        logger.info(f"Associating shipping method {shipping_method_id} with zones: {zone_ids}")

        # Get all zones from the database first
        all_zones = await db_client.fetch("SELECT id, name FROM spree_zones")
        logger.info(f"Found {len(all_zones)} zones in database")

        # Create a mapping of zone names to IDs
        zone_name_to_id = {}
        for zone in all_zones:
            zone_name_to_id[zone["name"]] = zone["id"]

        # Log the mapping for debugging
        logger.info(f"Zone mapping: {zone_name_to_id}")

        # Insert new associations
        for zone_id in zone_ids:
            # Get the zone name from constants
            zone_name = next((zone["name"] for zone in SHIPPING_ZONES if zone["id"] == zone_id), None)
            if not zone_name:
                logger.warning(f"Zone ID {zone_id} not found in SHIPPING_ZONES, skipping")
                continue

            # Try to find the zone by name
            db_zone_id = None

            # Direct lookup
            if zone_name in zone_name_to_id:
                db_zone_id = zone_name_to_id[zone_name]
                logger.info(f"Found zone by exact name: {zone_name} (ID: {db_zone_id})")
            else:
                # Try case-insensitive lookup
                for db_name, db_id in zone_name_to_id.items():
                    if db_name.upper() == zone_name.upper():
                        db_zone_id = db_id
                        logger.info(f"Found zone by case-insensitive name: {db_name} (ID: {db_zone_id})")
                        break

            # If we still can't find it, use the first zone as a fallback
            if not db_zone_id and all_zones:
                db_zone_id = all_zones[0]["id"]
                logger.warning(f"Zone '{zone_name}' not found, using fallback zone ID: {db_zone_id}")

            if not db_zone_id:
                logger.error(f"Could not find or create zone for '{zone_name}', skipping")
                continue

            # Insert the association
            await db_client.execute(
                """
                INSERT INTO spree_shipping_method_zones (shipping_method_id, zone_id, created_at, updated_at)
                VALUES ($1, $2, NOW(), NOW())
                """,
                shipping_method_id,
                db_zone_id,
            )
            logger.info(f"Associated shipping method {shipping_method_id} with zone ID: {db_zone_id}")

        logger.info(f"Successfully associated shipping method {shipping_method_id} with zones")

    except Exception as e:
        logger.error(f"Failed to associate shipping method {shipping_method_id} with zones: {e}")
        raise
