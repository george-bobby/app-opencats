import json
from pathlib import Path

from pydantic import BaseModel, Field

from apps.spree.config.settings import settings
from apps.spree.utils.ai import instructor_client
from common.logger import Logger


logger = Logger()

REFUND_REASONS_FILE = settings.DATA_PATH / "generated" / "refund_reasons.json"


class RefundReason(BaseModel):
    """Individual refund reason model."""

    name: str = Field(description="Clear, descriptive name for the refund reason")
    active: bool = Field(description="Whether this reason is currently active", default=True)
    mutable: bool = Field(description="Whether this reason can be modified", default=True)


class RefundReasonResponse(BaseModel):
    """Response format for generated refund reasons."""

    refund_reasons: list[RefundReason]


async def generate_refund_reasons(number_of_reasons: int) -> dict | None:
    """Generate realistic refund reasons for a pet supplies eCommerce store."""

    logger.info("Generating refund reasons...")

    try:
        system_prompt = f"""Generate {number_of_reasons} realistic refund reasons for a {settings.DATA_THEME_SUBJECT}.
        
        The reasons should cover common scenarios that customers might encounter when returning products or services, such as:
        - Product defects or quality issues
        - Wrong item received
        - Size/fit issues
        - Customer changed mind
        - Damaged during shipping
        - Not as described
        - Duplicate order
        - Found better price elsewhere
        - Item expired or near expiration
        - etc.
        
        Make the reasons clear, professional, and appropriate for customer service use.
        Each reason should be:
        - Clear and easy to understand
        - Professional in tone
        - Specific enough to be useful for processing returns
        - Appropriate for a pet supplies store context"""

        user_prompt = f"""Generate {number_of_reasons} realistic refund reasons for {settings.SPREE_STORE_NAME}, a {settings.DATA_THEME_SUBJECT}.
        
        Each refund reason should have:
        - name: Clear, concise description of the refund reason
        - active: Always true (these are active reasons)
        - mutable: Always true (these can be modified by staff)
        
        Focus on common pet supply return scenarios that would be helpful for customer service representatives."""

        refund_response = await instructor_client.chat.completions.create(
            model="claude-3-5-haiku-latest",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            response_model=RefundReasonResponse,
            temperature=0.3,
            max_tokens=8192,
        )

        if refund_response and refund_response.refund_reasons:
            # Convert to dict format for JSON serialization
            reasons_list = [reason.model_dump() for reason in refund_response.refund_reasons]
            reasons_dict = {"refund_reasons": reasons_list}

            # Save to file
            settings.DATA_PATH.mkdir(parents=True, exist_ok=True)
            REFUND_REASONS_FILE.parent.mkdir(parents=True, exist_ok=True)
            with Path.open(REFUND_REASONS_FILE, "w", encoding="utf-8") as f:
                json.dump(reasons_dict, f, indent=2, ensure_ascii=False)

            logger.succeed(f"Successfully generated and saved {len(refund_response.refund_reasons)} refund reasons to {REFUND_REASONS_FILE}")
            return reasons_dict
        else:
            logger.error("Failed to parse refund reasons response from AI")
            raise ValueError("Failed to generate refund reasons")

    except Exception as e:
        logger.error(f"Error generating refund reasons: {e}")
        raise


async def seed_refund_reasons():
    """Insert refund reasons into the database."""
    from apps.spree.utils.database import db_client

    logger.start("Inserting refund reasons into spree_refund_reasons table...")

    try:
        # Load refund reasons from JSON file
        if not REFUND_REASONS_FILE.exists():
            logger.error(f"Refund reasons file not found at {REFUND_REASONS_FILE}. Run generate command first.")
            raise FileNotFoundError("Refund reasons file not found")

        with Path.open(REFUND_REASONS_FILE, encoding="utf-8") as f:
            data = json.load(f)

        refund_reasons = data.get("refund_reasons", [])
        logger.info(f"Loaded {len(refund_reasons)} refund reasons from {REFUND_REASONS_FILE}")

        # Insert each refund reason into the database
        inserted_count = 0
        for reason in refund_reasons:
            try:
                # Check if reason with this name already exists
                existing_reason = await db_client.fetchrow("SELECT id FROM spree_refund_reasons WHERE name = $1", reason["name"])

                if existing_reason:
                    # Update existing reason
                    await db_client.execute(
                        """
                        UPDATE spree_refund_reasons 
                        SET active = $1, mutable = $2, updated_at = NOW()
                        WHERE name = $3
                        """,
                        reason["active"],
                        reason["mutable"],
                        reason["name"],
                    )
                    logger.info(f"Updated existing refund reason: {reason['name']}")
                else:
                    # Insert new reason
                    await db_client.execute(
                        """
                        INSERT INTO spree_refund_reasons (name, active, mutable, created_at, updated_at)
                        VALUES ($1, $2, $3, NOW(), NOW())
                        """,
                        reason["name"],
                        reason["active"],
                        reason["mutable"],
                    )

                inserted_count += 1

            except Exception as e:
                logger.error(f"Failed to insert/update refund reason {reason['name']}: {e}")
                continue

        logger.succeed(f"Successfully processed {inserted_count} refund reasons in the database")

    except Exception as e:
        logger.error(f"Error seeding refund reasons in database: {e}")
        raise
