import json
from datetime import datetime
from pathlib import Path

from pydantic import BaseModel, Field

from apps.spree.config.settings import settings
from apps.spree.utils.ai import instructor_client
from common.logger import Logger


logger = Logger()

TAX_CATEGORIES_FILE = settings.DATA_PATH / "generated" / "tax_categories.json"
TAX_RATES_FILE = settings.DATA_PATH / "generated" / "tax_rates.json"


class TaxCategory(BaseModel):
    """Individual tax category model."""

    name: str = Field(description="Clear, descriptive name for the tax category")
    description: str = Field(description="Brief explanation of what products fall under this category")
    tax_code: str = Field(description="Abbreviated tax code for the category (e.g. 'GM-001', 'PF-002', etc.)")
    is_default: bool = Field(description="EXACTLY ONE must be true")
    deleted_at: None = Field(description="Always null for new categories")


class TaxRate(BaseModel):
    """Individual tax rate model."""

    name: str = Field(description="Descriptive name for the tax rate")
    amount: float = Field(description="Tax rate as decimal (0.06-0.25 range)")
    tax_category_code: str = Field(description="Must be one of the available tax category codes")
    zone_id: int = Field(description="Zone ID (1-6) from SHIPPING_ZONES")
    included_in_price: bool = Field(description="Whether tax is included in price (typically true for EU/UK, false for US)")
    show_rate_in_label: bool = Field(description="Whether to display rate in product labels")


class TaxCategoryResponse(BaseModel):
    """Response format for generated tax categories."""

    categories: list[TaxCategory]


class TaxRateResponse(BaseModel):
    """Response format for generated tax rates."""

    tax_rates: list[TaxRate]


async def generate_tax_categories(number_of_categories: int) -> dict | None:
    """Generate realistic US tax categories for a pet supplies eCommerce store."""

    try:
        system_prompt = f"""Generate {number_of_categories} tax categories for a {settings.DATA_THEME_SUBJECT}.
        
        Categories should cover common pet supply product types such as:
        - General merchandise/pet supplies
        - Pet food and treats
        - Prescription medications/veterinary supplies
        - Pet services
        - Digital products/subscriptions
        - Shipping and handling
        - Gift cards
        - etc.
        
        Make the categories realistic and appropriate for US tax compliance."""

        user_prompt = f"""Generate realistic US tax categories for {settings.SPREE_STORE_NAME}."""

        tax_response = await instructor_client.chat.completions.create(
            model="claude-3-5-haiku-latest",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            response_model=TaxCategoryResponse,
            temperature=0.3,
            max_tokens=8192,
        )

        if tax_response and tax_response.categories:
            # Ensure exactly one default tax category
            default_count = sum(1 for cat in tax_response.categories if cat.is_default)

            if default_count == 0:
                # No default found, make the first category default
                tax_response.categories[0].is_default = True
                logger.info("No default tax category found, setting first category as default")
            elif default_count > 1:
                # Multiple defaults found, keep only the first one as default
                found_first_default = False
                for category in tax_response.categories:
                    if category.is_default:
                        if not found_first_default:
                            found_first_default = True
                            logger.info(f"Keeping '{category.name}' as the default tax category")
                        else:
                            category.is_default = False
                            logger.info(f"Removed default flag from '{category.name}'")

            # Convert to dict format for JSON serialization
            categories_list = [cat.model_dump() for cat in tax_response.categories]
            categories_dict = {"tax_categories": categories_list}

            # Save to file
            settings.DATA_PATH.mkdir(parents=True, exist_ok=True)
            with Path.open(TAX_CATEGORIES_FILE, "w", encoding="utf-8") as f:
                json.dump(categories_dict, f, indent=2, ensure_ascii=False)

            logger.succeed(f"Successfully generated and saved {len(tax_response.categories)} tax categories to {TAX_CATEGORIES_FILE}")
            return categories_dict
        else:
            logger.error("Failed to parse tax categories response from OpenAI")
            raise ValueError("Failed to generate tax categories")

    except Exception as e:
        logger.error(f"Error generating tax categories: {e}")
        raise


async def seed_tax_categories():
    """Insert tax categories into the database."""
    from apps.spree.utils.database import db_client

    logger.start("Inserting tax categories into spree_tax_categories table...")

    try:
        # Load tax categories from JSON file
        if not TAX_CATEGORIES_FILE.exists():
            logger.error(f"Tax categories file not found at {TAX_CATEGORIES_FILE}. Run generate command first.")
            raise FileNotFoundError("Tax categories file not found")

        with Path.open(TAX_CATEGORIES_FILE, encoding="utf-8") as f:
            data = json.load(f)

        tax_categories = data.get("tax_categories", [])
        logger.info(f"Loaded {len(tax_categories)} tax categories from {TAX_CATEGORIES_FILE}")

        # Insert each tax category into the database
        inserted_count = 0
        for category in tax_categories:
            try:
                # Check if category with this name already exists
                existing_category = await db_client.fetchrow("SELECT id FROM spree_tax_categories WHERE name = $1", category["name"])

                if existing_category:
                    # Update existing category
                    await db_client.execute(
                        """
                        UPDATE spree_tax_categories 
                        SET description = $1, tax_code = $2, is_default = $3, updated_at = NOW()
                        WHERE name = $4
                        """,
                        category["description"],
                        category.get("tax_code", ""),
                        category["is_default"],
                        category["name"],
                    )
                    logger.info(f"Updated existing tax category: {category['name']}")
                else:
                    # Insert new category
                    await db_client.execute(
                        """
                        INSERT INTO spree_tax_categories (name, description, tax_code, is_default, created_at, updated_at, deleted_at)
                        VALUES ($1, $2, $3, $4, NOW(), NOW(), $5)
                        """,
                        category["name"],
                        category["description"],
                        category.get("tax_code", ""),
                        category["is_default"],
                        category.get("deleted_at"),
                    )

                inserted_count += 1

            except Exception as e:
                logger.error(f"Failed to insert/update tax category {category['name']}: {e}")
                continue

        logger.succeed(f"Successfully processed {inserted_count} tax categories in the database")

    except Exception as e:
        logger.error(f"Error seeding tax categories in database: {e}")
        raise


async def generate_tax_rates(number_of_rates: int) -> dict | None:
    """Generate realistic global tax rates for different zones and tax categories."""

    logger.info("Generating global tax rates...")

    try:
        # First, load existing tax categories to get their codes
        if not TAX_CATEGORIES_FILE.exists():
            logger.error(f"Tax categories file not found at {TAX_CATEGORIES_FILE}. Generate tax categories first.")
            raise FileNotFoundError("Tax categories file not found")

        with Path.open(TAX_CATEGORIES_FILE, encoding="utf-8") as f:
            categories_data = json.load(f)

        tax_categories = categories_data.get("tax_categories", [])
        if not tax_categories:
            logger.error("No tax categories found in the file")
            raise ValueError("No tax categories available")

        category_codes = [cat["tax_code"] for cat in tax_categories]
        logger.info(f"Found {len(category_codes)} tax category codes: {', '.join(category_codes)}")

        system_prompt = f"""You are an expert global tax consultant specializing in eCommerce taxation. 
        Generate realistic tax rates for a {settings.DATA_THEME_SUBJECT} with global presence.
        
        Store Details:
        - Store Name: {settings.SPREE_STORE_NAME}
        - Store Theme: {settings.DATA_THEME_SUBJECT}
        - Today's Date: {datetime.now().strftime("%Y-%m-%d")}
        
        Available Tax Category Codes: {", ".join(category_codes)}
        
        Available Shipping Zones:
        - Zone ID 1: EU_VAT (European Union)
        - Zone ID 2: UK_VAT (United Kingdom)
        - Zone ID 3: NORTH AMERICA (US, Canada, Mexico)
        - Zone ID 4: SOUTH AMERICA
        - Zone ID 5: MIDDLE EAST
        - Zone ID 6: ASIA
        
        Generate tax rates with the following properties:
        - name: Generic tax rate name WITHOUT region/country names (e.g. "Standard Rate", "Reduced Rate", "Zero Rate")
        - amount: Tax rate as decimal (e.g., 0.20 for 20%, 0.19 for 19%)
        - tax_category_code: Must be one of the available codes: {category_codes}
        - zone_id: Zone ID (1-6) from the available shipping zones
        - included_in_price: Boolean (true for EU/UK VAT, false for US/Canada taxes)
        - show_rate_in_label: Boolean (true to show tax rate to customers)
        
        Create a balanced global mix of tax rates covering:
        - Standard rates (typically 17-27%, included in price for zone 1-2)
        - Reduced rates (typically 5-10%)
        - Zero rates (0% for certain categories)
        - Special rates (any other applicable rates)
        
        Distribute the tax rates evenly across all zones, with approximately equal representation.
        Generate {number_of_rates} tax rates total."""

        user_prompt = f"""Generate realistic global tax rates for {settings.SPREE_STORE_NAME}, 
        a {settings.DATA_THEME_SUBJECT} with international presence. 
        
        Available tax category codes: {category_codes}
        
        Each tax rate should have:
        - name (string): generic tax rate name WITHOUT region names (e.g. "Standard Rate", "Reduced Rate")
        - amount (float): tax rate as decimal (e.g., 0.19 for 19%, 0.20 for 20%)
        - tax_category_code (string): must match one of the available codes
        - zone_id (int): must be 1-6 corresponding to the shipping zones
        - included_in_price (boolean): true for EU/UK VAT, false for North American taxes
        - show_rate_in_label (boolean): typically true to display rate
        
        Return as a list of tax rate objects with balanced representation across all global regions."""

        tax_rates_response = await instructor_client.chat.completions.create(
            model="claude-3-5-haiku-latest",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            response_model=TaxRateResponse,
            temperature=0.3,
            max_tokens=8192,
        )

        if tax_rates_response and tax_rates_response.tax_rates:
            # Convert to dict format for JSON serialization
            rates_list = [rate.model_dump() for rate in tax_rates_response.tax_rates]
            rates_dict = {"tax_rates": rates_list}

            # Save to file
            settings.DATA_PATH.mkdir(parents=True, exist_ok=True)
            TAX_RATES_FILE.parent.mkdir(parents=True, exist_ok=True)
            with Path.open(TAX_RATES_FILE, "w", encoding="utf-8") as f:
                json.dump(rates_dict, f, indent=2, ensure_ascii=False)

            logger.succeed(f"Successfully generated and saved {len(tax_rates_response.tax_rates)} tax rates to {TAX_RATES_FILE}")
            for rate in tax_rates_response.tax_rates:
                logger.info(f"Generated tax rate: {rate.name} ({rate.amount * 100:.2f}%) for {rate.tax_category_code}")
            return rates_dict
        else:
            logger.error("Failed to parse tax rates response from OpenAI")
            raise ValueError("Failed to generate tax rates")

    except Exception as e:
        logger.error(f"Error generating tax rates: {e}")
        raise


async def _create_tax_calculator(tax_rate_id: int):
    """Create a calculator for a tax rate."""
    from apps.spree.utils.database import db_client

    # For tax rates, we use DefaultTax calculator
    calculator_class = "Spree::Calculator::DefaultTax"

    try:
        # Check if calculator already exists for this tax rate
        existing_calculator = await db_client.fetchrow("SELECT id FROM spree_calculators WHERE calculable_type = 'Spree::TaxRate' AND calculable_id = $1", tax_rate_id)

        if existing_calculator:
            # Update existing calculator
            await db_client.execute(
                """
                UPDATE spree_calculators 
                SET type = $1, updated_at = NOW()
                WHERE calculable_type = 'Spree::TaxRate' AND calculable_id = $2
                """,
                calculator_class,
                tax_rate_id,
            )
        else:
            # Create new calculator
            await db_client.execute(
                """
                INSERT INTO spree_calculators (type, calculable_type, calculable_id, preferences, created_at, updated_at)
                VALUES ($1, $2, $3, $4, NOW(), NOW())
                """,
                calculator_class,
                "Spree::TaxRate",
                tax_rate_id,
                json.dumps({}),  # DefaultTax doesn't need preferences
            )

    except Exception as e:
        logger.error(f"Failed to create calculator for tax rate {tax_rate_id}: {e}")
        raise


async def seed_tax_rates():
    """Insert tax rates into the database."""
    from apps.spree.utils.database import db_client

    logger.start("Inserting tax rates into spree_tax_rates table...")

    try:
        # Load tax rates from JSON file
        if not TAX_RATES_FILE.exists():
            logger.error(f"Tax rates file not found at {TAX_RATES_FILE}. Run generate command first.")
            raise FileNotFoundError("Tax rates file not found")

        with Path.open(TAX_RATES_FILE, encoding="utf-8") as f:
            data = json.load(f)

        tax_rates = data.get("tax_rates", [])
        logger.info(f"Loaded {len(tax_rates)} tax rates from {TAX_RATES_FILE}")

        # Insert each tax rate into the database
        inserted_count = 0
        for rate in tax_rates:
            try:
                # Look up tax_category_id by tax_code
                tax_category = await db_client.fetchrow("SELECT id FROM spree_tax_categories WHERE tax_code = $1", rate["tax_category_code"])

                if not tax_category:
                    logger.warning(f"Tax category not found for code '{rate['tax_category_code']}', skipping rate '{rate['name']}'")
                    continue

                tax_category_id = tax_category["id"]

                # Check if tax rate with this name already exists
                existing_rate = await db_client.fetchrow("SELECT id FROM spree_tax_rates WHERE name = $1", rate["name"])
                tax_rate_id = None

                if existing_rate:
                    # Update existing rate
                    await db_client.execute(
                        """
                        UPDATE spree_tax_rates 
                        SET amount = $1, zone_id = $2, tax_category_id = $3, 
                            included_in_price = $4, show_rate_in_label = $5,
                            updated_at = NOW()
                        WHERE name = $6
                        """,
                        rate["amount"],
                        rate["zone_id"],
                        tax_category_id,
                        rate["included_in_price"],
                        rate["show_rate_in_label"],
                        rate["name"],
                    )
                    tax_rate_id = existing_rate["id"]
                else:
                    # Insert new rate
                    tax_rate_id = await db_client.fetchval(
                        """
                        INSERT INTO spree_tax_rates (name, amount, zone_id, tax_category_id, 
                                                   included_in_price, show_rate_in_label,
                                                   created_at, updated_at, deleted_at)
                        VALUES ($1, $2, $3, $4, $5, $6, NOW(), NOW(), $7)
                        RETURNING id
                        """,
                        rate["name"],
                        rate["amount"],
                        rate["zone_id"],
                        tax_category_id,
                        rate["included_in_price"],
                        rate["show_rate_in_label"],
                        None,
                    )

                # Create calculator for the tax rate
                if tax_rate_id:
                    await _create_tax_calculator(tax_rate_id)

                inserted_count += 1

            except Exception as e:
                logger.error(f"Failed to insert/update tax rate {rate['name']}: {e}")
                continue

        logger.succeed(f"Successfully processed {inserted_count} tax rates in the database")

    except Exception as e:
        logger.error(f"Error seeding tax rates in database: {e}")
        raise
