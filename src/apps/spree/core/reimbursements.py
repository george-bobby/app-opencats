import json
from pathlib import Path

from pydantic import BaseModel, Field

from apps.spree.utils.constants import CUSTOMER_RETURNS_FILE, REIMBURSEMENTS_FILE
from common.logger import Logger


logger = Logger()


# Valid Spree reimbursement types
VALID_REIMBURSEMENT_TYPES = ["Spree::ReimbursementType::Credit", "Spree::ReimbursementType::Exchange", "Spree::ReimbursementType::OriginalPayment", "Spree::ReimbursementType::StoreCredit"]


class ReimbursementType(BaseModel):
    """Individual reimbursement type model."""

    name: str = Field(description="Clear, descriptive name for the reimbursement type")
    active: bool = Field(description="Whether this type is currently active", default=True)
    mutable: bool = Field(description="Whether this type can be modified", default=True)
    type: str = Field(description="Must be one of the valid Spree reimbursement types")  # noqa: A003, RUF100


class ReimbursementTypeResponse(BaseModel):
    """Response format for generated reimbursement types."""

    reimbursement_types: list[ReimbursementType]


class Reimbursement(BaseModel):
    """Individual reimbursement model."""

    id: int = Field(description="Unique identifier for the reimbursement")  # noqa: A003, RUF100
    customer_return_id: int = Field(description="ID of the customer return being reimbursed")
    order_id: int = Field(description="ID of the order for this reimbursement")
    total: int = Field(description="Total amount of the reimbursement")
    reimbursement_status: str = Field(description="Status of the reimbursement: pending, reimbursed, or errored")
    created_at: str = Field(description="Timestamp when the reimbursement was created")
    updated_at: str = Field(description="Timestamp when the reimbursement was last updated")


async def generate_reimbursements():
    """Generate reimbursements for customer returns."""
    import random
    from datetime import datetime, timedelta

    logger.info("Generating reimbursements...")

    try:
        # Check if customer returns exist
        if not CUSTOMER_RETURNS_FILE.exists():
            logger.error(f"Customer returns file not found at {CUSTOMER_RETURNS_FILE}. Generate customer returns first.")
            raise FileNotFoundError("Customer returns file not found")

        # Load customer returns
        with Path.open(CUSTOMER_RETURNS_FILE, encoding="utf-8") as f:
            customer_returns_data = json.load(f)
            customer_returns = customer_returns_data.get("customer_returns", [])

        logger.info(f"Loaded {len(customer_returns)} customer returns")

        if not customer_returns:
            logger.warning("No customer returns found to generate reimbursements for")
            return {"reimbursements": []}

        # Generate reimbursements
        reimbursements = []
        now = datetime.now()

        for idx, customer_return in enumerate(customer_returns, 1):
            cr_id = customer_return.get("id")
            order_id = customer_return.get("associated_order_id")

            if not cr_id or not order_id:
                continue

            # Get the actual return items for this customer return to calculate the total
            # Note: We can't access the database directly during generation, but we'll use
            # more realistic amounts during seeding

            # Determine reimbursement status
            # 60% pending, 30% reimbursed, 10% errored
            status = random.choices(["pending", "reimbursed", "errored"], weights=[0.6, 0.3, 0.1], k=1)[0]

            # Set timestamps based on status
            created_at = (now - timedelta(days=random.randint(1, 30))).strftime("%Y-%m-%d %H:%M:%S")
            updated_at = created_at

            # If status is not pending, add an update time difference
            if status != "pending":
                updated_at = (datetime.strptime(created_at, "%Y-%m-%d %H:%M:%S") + timedelta(days=random.randint(1, 5))).strftime("%Y-%m-%d %H:%M:%S")

            # Generate a plausible reimbursement amount between $25-$400
            # During seeding, we'll replace this with the actual sum of return item amounts
            estimated_total = round(random.uniform(25.0, 400.0), 2)

            # Create reimbursement
            reimbursement = Reimbursement(
                id=idx,
                customer_return_id=cr_id,
                order_id=order_id,
                total=int(estimated_total),  # This will be replaced during seeding
                reimbursement_status=status,
                created_at=created_at,
                updated_at=updated_at,
            )

            reimbursements.append(reimbursement)

        # Save to file
        reimbursements_data = {"reimbursements": [r.model_dump() for r in reimbursements]}
        REIMBURSEMENTS_FILE.parent.mkdir(parents=True, exist_ok=True)

        with Path.open(REIMBURSEMENTS_FILE, "w", encoding="utf-8") as f:
            json.dump(reimbursements_data, f, indent=2, ensure_ascii=False)

        logger.succeed(f"Successfully generated {len(reimbursements)} reimbursements")
        return reimbursements_data

    except Exception as e:
        logger.error(f"Error generating reimbursements: {e}")
        raise


async def seed_reimbursements():
    """Insert reimbursements into the database."""
    from datetime import datetime
    from decimal import Decimal

    from apps.spree.utils.database import db_client

    logger.start("Inserting reimbursements into spree_reimbursements table...")

    try:
        # Load reimbursements from JSON file
        if not REIMBURSEMENTS_FILE.exists():
            logger.error(f"Reimbursements file not found at {REIMBURSEMENTS_FILE}. Run generate command first.")
            raise FileNotFoundError("Reimbursements file not found")

        with Path.open(REIMBURSEMENTS_FILE, encoding="utf-8") as f:
            data = json.load(f)

        reimbursements = data.get("reimbursements", [])
        logger.info(f"Loaded {len(reimbursements)} reimbursements from {REIMBURSEMENTS_FILE}")

        # Insert each reimbursement into the database
        inserted_count = 0
        for reimbursement in reimbursements:
            try:
                reimbursement_id = reimbursement.get("id")

                # Parse string timestamps to datetime objects
                created_at = datetime.strptime(reimbursement["created_at"], "%Y-%m-%d %H:%M:%S")
                updated_at = datetime.strptime(reimbursement["updated_at"], "%Y-%m-%d %H:%M:%S")

                # Calculate the actual total from return items' pre-tax amounts
                return_items_total = await db_client.fetchrow(
                    """
                    SELECT COALESCE(SUM(pre_tax_amount), 0) as total
                    FROM spree_return_items 
                    WHERE customer_return_id = $1
                    """,
                    reimbursement["customer_return_id"],
                )

                # Convert all values to Decimal for consistent type handling
                db_total = return_items_total["total"] if return_items_total and return_items_total["total"] > 0 else Decimal("0")
                reimbursement_total = Decimal(str(reimbursement["total"]))  # Convert float to Decimal safely

                # Use database total if available, otherwise use the estimated total
                actual_total = db_total if db_total > Decimal("0") else reimbursement_total

                # # Log the adjustment if there's a significant difference
                # if abs(actual_total - reimbursement_total) > Decimal("0.01"):
                #     logger.debug(f"Adjusting reimbursement total from {reimbursement['total']} to {actual_total} based on actual return items")

                # Check if reimbursement already exists
                existing_reimbursement = await db_client.fetchrow("SELECT id FROM spree_reimbursements WHERE id = $1", reimbursement_id)

                if existing_reimbursement:
                    # Update existing reimbursement
                    await db_client.execute(
                        """
                        UPDATE spree_reimbursements 
                        SET customer_return_id = $1, order_id = $2, total = $3, 
                            reimbursement_status = $4, updated_at = $5
                        WHERE id = $6
                        """,
                        reimbursement["customer_return_id"],
                        reimbursement["order_id"],
                        actual_total,  # Use calculated total based on return items
                        reimbursement["reimbursement_status"],
                        updated_at,
                        reimbursement_id,
                    )
                    logger.info(f"Updated existing reimbursement [ID: {reimbursement_id}]")
                else:
                    # Insert new reimbursement - convert total to Decimal for DB
                    insert_total = Decimal(str(reimbursement["total"]))

                    await db_client.execute(
                        """
                        INSERT INTO spree_reimbursements 
                        (id, customer_return_id, order_id, total, 
                         reimbursement_status, created_at, updated_at)
                        VALUES ($1, $2, $3, $4, $5, $6, $7)
                        """,
                        reimbursement_id,
                        reimbursement["customer_return_id"],
                        reimbursement["order_id"],
                        insert_total,
                        reimbursement["reimbursement_status"],
                        created_at,
                        updated_at,
                    )

                # Associate reimbursement with customer return's return items
                await db_client.execute(
                    """
                    UPDATE spree_return_items 
                    SET reimbursement_id = $1
                    WHERE customer_return_id = $2
                    AND reimbursement_id IS NULL
                    """,
                    reimbursement_id,
                    reimbursement["customer_return_id"],
                )

                # If status is reimbursed, create reimbursement credits
                if reimbursement["reimbursement_status"] == "reimbursed":
                    # Get a reimbursement type
                    reimbursement_type = await db_client.fetchrow(
                        """
                        SELECT id FROM spree_reimbursement_types
                        WHERE active = true
                        LIMIT 1
                        """
                    )

                    if reimbursement_type:
                        # Create a reimbursement credit
                        # Convert to Decimal before inserting into database
                        refund_amount = Decimal(str(reimbursement["total"]))

                        await db_client.execute(
                            """
                            INSERT INTO spree_refunds
                            (reimbursement_id, amount, payment_id, created_at, updated_at)
                            VALUES ($1, $2, NULL, $3, $4)
                            """,
                            reimbursement_id,
                            refund_amount,
                            created_at,
                            updated_at,
                        )

                inserted_count += 1

            except Exception as e:
                logger.error(f"Failed to insert/update reimbursement {reimbursement_id}: {e}")
                continue

        logger.succeed(f"Successfully processed {inserted_count} reimbursements in the database")

    except Exception as e:
        logger.error(f"Error seeding reimbursements in database: {e}")
        raise
