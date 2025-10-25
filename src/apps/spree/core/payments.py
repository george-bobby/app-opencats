import json
from pathlib import Path

from pydantic import BaseModel, Field

from apps.spree.config.settings import settings
from apps.spree.utils.ai import instructor_client
from apps.spree.utils.constants import PAYMENT_PROVIDERS
from common.logger import Logger


logger = Logger()

PAYMENT_METHODS_FILE = settings.DATA_PATH / "generated" / "payment_methods.json"


class PaymentMethod(BaseModel):
    """Individual payment method model."""

    type: str = Field(description="Must be one of the valid Spree payment providers")  # noqa: A003, RUF100
    name: str = Field(description="Clear, descriptive name for the payment method")
    description: str = Field(description="Brief explanation of the payment method")
    active: bool = Field(description="Whether this method is currently active", default=True)
    display_on: str = Field(description="Where to display this payment method", default="both")
    auto_capture: bool = Field(description="Whether to automatically capture payments", default=False)
    preferences: str = Field(description="JSON string of payment method preferences", default="{}")
    position: int = Field(description="Display order position", default=0)
    public_metadata: str = Field(description="Public metadata as JSON string", default="{}")
    private_metadata: str = Field(description="Private metadata as JSON string", default="{}")
    settings: str = Field(description="Payment method settings as JSON string", default="{}")


class PaymentMethodResponse(BaseModel):
    """Response format for generated payment methods."""

    payment_methods: list[PaymentMethod]


async def generate_payment_methods(number_of_methods: int) -> dict | None:
    """Generate realistic payment methods for an eCommerce store."""

    logger.info("Generating payment methods...")

    try:
        system_prompt = f"""Generate {number_of_methods} realistic payment methods for a {settings.DATA_THEME_SUBJECT}.
        
        Each payment method must have a 'type' field that is EXACTLY one of these valid Spree payment providers:
        {", ".join(PAYMENT_PROVIDERS)}
        
        The payment methods should cover common eCommerce payment options such as:
        - Credit card processors (Stripe, Authorize.Net, PayPal, etc.)
        - Digital wallets (Apple Pay, etc.)
        - Bank transfers and checks
        - Store credit systems
        - Buy now, pay later options
        - Regional payment methods
        
        For each payment method, provide:
        - type: Must match exactly one of the valid providers
        - name: Customer-friendly name (e.g., "Credit Card", "PayPal", "Apple Pay")
        - description: Brief explanation for customers
        - active: Whether it's currently enabled
        - display_on: "both", "front_end", or "back_end"
        - auto_capture: Whether to automatically capture payments
        - preferences: JSON string with provider-specific settings
        - position: Display order (0-based)
        - public_metadata: Customer-visible information
        - private_metadata: Internal administrative data
        - settings: Provider configuration options
        
        Make the payment methods realistic and appropriate for a modern eCommerce store."""

        user_prompt = f"""Generate {number_of_methods} realistic payment methods for {settings.SPREE_STORE_NAME}, a {settings.DATA_THEME_SUBJECT}.
        
        Available payment provider types: {PAYMENT_PROVIDERS}
        
        Each payment method should have:
        - type: Must match exactly one of the available providers
        - name: Customer-friendly display name
        - description: Brief customer-facing description
        - active: Always true (these are active methods)
        - display_on: "both" for most, "front_end" for customer-only, "back_end" for admin-only
        - auto_capture: true for simple methods, false for manual capture
        - preferences: JSON string with realistic provider settings
        - position: Sequential ordering (0, 1, 2, etc.)
        - public_metadata: Customer-visible info like supported cards
        - private_metadata: Internal notes and admin info
        - settings: Provider-specific configuration
        
        Focus on creating a diverse mix of payment options that would be useful for customers."""

        payment_response = await instructor_client.chat.completions.create(
            model="claude-3-5-haiku-latest",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            response_model=PaymentMethodResponse,
            temperature=0.3,
            max_tokens=8192,
        )

        if payment_response and payment_response.payment_methods:
            # Validate that all types are valid Spree payment providers
            for payment_method in payment_response.payment_methods:
                if payment_method.type not in PAYMENT_PROVIDERS:
                    logger.warning(f"Invalid payment provider '{payment_method.type}' for '{payment_method.name}', using default")
                    payment_method.type = PAYMENT_PROVIDERS[0]  # Default to first provider

            # Convert to dict format for JSON serialization
            methods_list = [method.model_dump() for method in payment_response.payment_methods]
            methods_dict = {"payment_methods": methods_list}

            # Save to file
            settings.DATA_PATH.mkdir(parents=True, exist_ok=True)
            PAYMENT_METHODS_FILE.parent.mkdir(parents=True, exist_ok=True)
            with Path.open(PAYMENT_METHODS_FILE, "w", encoding="utf-8") as f:
                json.dump(methods_dict, f, indent=2, ensure_ascii=False)

            logger.succeed(f"Successfully generated and saved {len(payment_response.payment_methods)} payment methods to {PAYMENT_METHODS_FILE}")
            for method in payment_response.payment_methods:
                logger.info(f"Generated payment method: {method.name} ({method.type})")
            return methods_dict
        else:
            logger.error("Failed to parse payment methods response from AI")
            raise ValueError("Failed to generate payment methods")

    except Exception as e:
        logger.error(f"Error generating payment methods: {e}")
        raise


async def seed_payment_methods():
    """Insert payment methods into the database."""
    from apps.spree.utils.database import db_client

    logger.start("Inserting payment methods into spree_payment_methods table...")

    try:
        # Load payment methods from JSON file
        if not PAYMENT_METHODS_FILE.exists():
            logger.error(f"Payment methods file not found at {PAYMENT_METHODS_FILE}. Run generate command first.")
            raise FileNotFoundError("Payment methods file not found")

        with Path.open(PAYMENT_METHODS_FILE, encoding="utf-8") as f:
            data = json.load(f)

        payment_methods = data.get("payment_methods", [])
        logger.info(f"Loaded {len(payment_methods)} payment methods from {PAYMENT_METHODS_FILE}")

        # Insert each payment method into the database
        inserted_count = 0
        for method in payment_methods:
            try:
                # Validate type before inserting
                if method["type"] not in PAYMENT_PROVIDERS:
                    logger.warning(f"Invalid payment provider '{method['type']}' for '{method['name']}', skipping")
                    continue

                # Check if payment method with this name already exists
                existing_method = await db_client.fetchrow("SELECT id FROM spree_payment_methods WHERE name = $1", method["name"])

                if existing_method:
                    # Update existing method
                    await db_client.execute(
                        """
                        UPDATE spree_payment_methods 
                        SET type = $1, description = $2, active = $3, display_on = $4,
                            auto_capture = $5, preferences = $6, position = $7,
                            public_metadata = $8, private_metadata = $9, settings = $10,
                            updated_at = NOW()
                        WHERE name = $11
                        """,
                        method["type"],
                        method["description"],
                        method["active"],
                        method["display_on"],
                        method["auto_capture"],
                        method["preferences"],
                        method["position"],
                        method["public_metadata"],
                        method["private_metadata"],
                        method["settings"],
                        method["name"],
                    )
                    logger.info(f"Updated existing payment method: {method['name']}")

                    # For updated payment methods, also ensure store association exists
                    payment_method_id = existing_method["id"]
                    try:
                        # Check if association already exists
                        existing_association = await db_client.fetchrow("SELECT 1 FROM spree_payment_methods_stores WHERE payment_method_id = $1 AND store_id = $2", payment_method_id, 1)

                        if not existing_association:
                            await db_client.execute("INSERT INTO spree_payment_methods_stores (payment_method_id, store_id) VALUES ($1, $2)", payment_method_id, 1)
                            logger.info(f"Associated updated payment method '{method['name']}' with store_id 1")
                    except Exception as e:
                        logger.error(f"Failed to associate updated payment method '{method['name']}' with store: {e}")
                else:
                    # Insert new method
                    await db_client.execute(
                        """
                        INSERT INTO spree_payment_methods (type, name, description, active, display_on,
                                                         auto_capture, preferences, position,
                                                         public_metadata, private_metadata, settings,
                                                         created_at, updated_at, deleted_at)
                        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, NOW(), NOW(), $12)
                        """,
                        method["type"],
                        method["name"],
                        method["description"],
                        method["active"],
                        method["display_on"],
                        method["auto_capture"],
                        method["preferences"],
                        method["position"],
                        method["public_metadata"],
                        method["private_metadata"],
                        method["settings"],
                        None,  # deleted_at
                    )

                # Get the payment method ID for the store association
                payment_method_row = await db_client.fetchrow("SELECT id FROM spree_payment_methods WHERE name = $1", method["name"])

                if payment_method_row:
                    payment_method_id = payment_method_row["id"]

                    # Insert into spree_payment_methods_stores table (associate with store_id 1)
                    try:
                        # Check if association already exists
                        existing_association = await db_client.fetchrow("SELECT 1 FROM spree_payment_methods_stores WHERE payment_method_id = $1 AND store_id = $2", payment_method_id, 1)

                        if not existing_association:
                            await db_client.execute("INSERT INTO spree_payment_methods_stores (payment_method_id, store_id) VALUES ($1, $2)", payment_method_id, 1)
                            # logger.info(f"Associated payment method '{method['name']}' with store_id 1")
                        else:
                            logger.info(f"Payment method '{method['name']}' already associated with store_id 1")
                    except Exception as e:
                        logger.error(f"Failed to associate payment method '{method['name']}' with store: {e}")
                else:
                    logger.error(f"Could not find payment method '{method['name']}' for store association")

                inserted_count += 1

            except Exception as e:
                logger.error(f"Failed to insert/update payment method {method['name']}: {e}")
                continue

        logger.succeed(f"Successfully processed {inserted_count} payment methods in the database")

    except Exception as e:
        logger.error(f"Error seeding payment methods in database: {e}")
        raise
