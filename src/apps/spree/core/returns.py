import json
from datetime import datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

from apps.spree.config.settings import settings
from apps.spree.utils.ai import instructor_client
from apps.spree.utils.constants import CUSTOMER_RETURNS_FILE, ORDERS_FILE, RETURN_AUTHORIZATIONS_FILE, STOCK_LOCATIONS_FILE
from common.logger import Logger


logger = Logger()


class ReturnReason(BaseModel):
    """Individual return authorization reason model."""

    id: int = Field(description="Unique identifier for the return reason")  # noqa: A003, RUF100
    name: str = Field(description="Clear, descriptive name for the return authorization reason")
    active: bool = Field(description="Whether this reason is currently active", default=True)
    mutable: bool = Field(description="Whether this reason can be modified", default=True)


class ReturnReasonForGeneration(BaseModel):
    """Return reason model for AI generation (without ID)."""

    name: str = Field(description="Clear, descriptive name for the return authorization reason")
    active: bool = Field(description="Whether this reason is currently active", default=True)
    mutable: bool = Field(description="Whether this reason can be modified", default=True)


class ReturnReasonResponse(BaseModel):
    """Response format for generated return authorization reasons."""

    return_reasons: list[ReturnReasonForGeneration]


async def generate_rma_reasons(number_of_reasons: int) -> dict | None:
    """Generate realistic return authorization reasons for an eCommerce store."""

    logger.info("Generating return authorization reasons...")

    try:
        system_prompt = f"""Generate {number_of_reasons} realistic return authorization reasons for a {settings.DATA_THEME_SUBJECT}.
        
        These are reasons that customers can select when requesting authorization to return products. They should cover common scenarios such as:
        - Product defects or quality issues
        - Wrong item received
        - Size/fit issues
        - Customer changed mind
        - Damaged during shipping
        - Not as described
        - Duplicate order
        - Found better price elsewhere
        - Item expired or near expiration
        - Product didn't meet expectations
        - Ordering error
        - No longer needed
        - etc.
        
        Make the reasons clear, professional, and appropriate for return authorization processing.
        Each reason should be:
        - Clear and easy to understand
        - Professional in tone
        - Specific enough to be useful for processing return authorizations
        - Appropriate for an eCommerce store context
        - Customer-friendly language"""

        user_prompt = f"""Generate {number_of_reasons} realistic return authorization reasons for {settings.SPREE_STORE_NAME}, a {settings.DATA_THEME_SUBJECT}.
        
        Each return authorization reason should have:
        - name: Clear, concise description of the return reason
        - active: Always true (these are active reasons)
        - mutable: Always true (these can be modified by staff)
        
        Focus on common return scenarios that would be helpful for both customers and customer service representatives when processing return requests."""

        return_response = await instructor_client.chat.completions.create(
            model="claude-3-5-haiku-latest",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            response_model=ReturnReasonResponse,
            temperature=0.3,
            max_tokens=8192,
        )

        if return_response and return_response.return_reasons:
            # Add incrementing IDs to all return reasons
            reasons_with_ids = []
            reason_id = 1

            for reason in return_response.return_reasons:
                # Convert to ReturnReason model with ID
                reason_with_id = ReturnReason(id=reason_id, name=reason.name, active=reason.active, mutable=reason.mutable)
                reasons_with_ids.append(reason_with_id)
                reason_id += 1

            # Convert to dict format for JSON serialization
            reasons_list = [reason.model_dump() for reason in reasons_with_ids]

            # Load existing data or create new structure
            data = {"return_reasons": reasons_list, "return_authorizations": []}
            settings.DATA_PATH.mkdir(parents=True, exist_ok=True)
            RETURN_AUTHORIZATIONS_FILE.parent.mkdir(parents=True, exist_ok=True)

            # Save to file
            with Path.open(RETURN_AUTHORIZATIONS_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)

            logger.succeed(f"Successfully generated and saved {len(return_response.return_reasons)} return authorization reasons to {RETURN_AUTHORIZATIONS_FILE}")
            return data
        else:
            logger.error("Failed to parse return authorization reasons response from AI")
            raise ValueError("Failed to generate return authorization reasons")

    except Exception as e:
        logger.error(f"Error generating return authorization reasons: {e}")
        raise


async def seed_rma_reasons():
    """Insert return authorization reasons into the database."""
    from apps.spree.utils.database import db_client

    logger.start("Inserting return authorization reasons into spree_return_authorization_reasons table...")

    try:
        # Load return authorization data from JSON file
        if not RETURN_AUTHORIZATIONS_FILE.exists():
            logger.error(f"Return authorizations file not found at {RETURN_AUTHORIZATIONS_FILE}. Run generate command first.")
            raise FileNotFoundError("Return authorizations file not found")

        with Path.open(RETURN_AUTHORIZATIONS_FILE, encoding="utf-8") as f:
            data = json.load(f)

        return_reasons = data.get("return_reasons", [])
        logger.info(f"Loaded {len(return_reasons)} return authorization reasons from {RETURN_AUTHORIZATIONS_FILE}")

        # Insert each return authorization reason into the database
        inserted_count = 0
        for reason in return_reasons:
            try:
                reason_id = reason.get("id")

                # Check if reason with this ID already exists
                existing_reason = await db_client.fetchrow("SELECT id FROM spree_return_authorization_reasons WHERE id = $1", reason_id)

                if existing_reason:
                    # Update existing reason
                    await db_client.execute(
                        """
                        UPDATE spree_return_authorization_reasons 
                        SET name = $1, active = $2, mutable = $3, updated_at = NOW()
                        WHERE id = $4
                        """,
                        reason["name"],
                        reason["active"],
                        reason["mutable"],
                        reason_id,
                    )
                    logger.info(f"Updated existing return authorization reason: {reason['name']} [ID: {reason_id}]")
                else:
                    # Insert new reason with specified ID
                    await db_client.execute(
                        """
                        INSERT INTO spree_return_authorization_reasons (id, name, active, mutable, created_at, updated_at)
                        VALUES ($1, $2, $3, $4, NOW(), NOW())
                        """,
                        reason_id,
                        reason["name"],
                        reason["active"],
                        reason["mutable"],
                    )

                inserted_count += 1

            except Exception as e:
                logger.error(f"Failed to insert/update return authorization reason {reason['name']}: {e}")
                continue

        logger.succeed(f"Successfully processed {inserted_count} return authorization reasons in the database")

    except Exception as e:
        logger.error(f"Error seeding return authorization reasons in database: {e}")
        raise


class ReturnAuthorization(BaseModel):
    """Individual return authorization model."""

    id: int = Field(description="Unique identifier for the return authorization")  # noqa: A003, RUF100
    number: str = Field(description="Unique return authorization number")
    state: Literal["authorized", "canceled"] = Field(description="Current state of the return authorization")
    order_id: int = Field(description="ID of the associated order")
    memo: str | None = Field(description="Notes or comments about the return")
    created_at: str = Field(description="Timestamp when the return was created")
    updated_at: str = Field(description="Timestamp when the return was last updated")
    stock_location_id: int = Field(description="ID of the stock location for return")
    return_authorization_reason_id: int = Field(description="ID of the return reason")


class ReturnAuthorizationResponse(BaseModel):
    """Response format for generated return authorizations."""

    return_authorizations: list[ReturnAuthorization]


async def generate_rma_for_order(
    order: dict,
    reason_ids: list[int],
    stock_location_ids: list[int],
    existing_numbers: set[str] | None = None,
) -> ReturnAuthorization | None:
    """Generate a return authorization for a specific completed order."""
    from datetime import datetime

    try:
        # Initialize existing_numbers if not provided
        if existing_numbers is None:
            existing_numbers = set()

        # Extract relevant order details for the prompt
        order_details = {"id": order["id"], "number": order["number"], "completed_at": order.get("completed_at"), "total": order.get("total"), "items": order.get("line_items", [])}

        system_prompt = f"""Generate a realistic return authorization for order {order_details["number"]}.
        
        Order details:
        {json.dumps(order_details, indent=2)}
        
        The return should:
        - Have a unique RA number (format: RA + 9 digits) that is different from any existing RA numbers
        - Have a state value of ONLY 'authorized' or 'canceled' 
        - Include a believable memo that references specific items from this order
        - Reference this specific order ID: {order_details["id"]}
        - Use a return reason ID from this list: {reason_ids}
        - Use a stock location ID from this list: {stock_location_ids}
        - Have timestamp for today's date ({datetime.now().strftime("%Y-%m-%d")})
        - Ensure the return date is after the order's completion date: {order_details["completed_at"]}
        
        Make the return realistic and reference actual items from this specific order.
        IMPORTANT: Only use 'authorized' or 'canceled' as states - no other values are allowed."""

        user_prompt = f"""Generate a return authorization for order {order_details["number"]}.
        
        Using today's date ({datetime.now().strftime("%Y-%m-%d")}) for timestamps.
        
        The return must have:
        - A unique RA number following the format RA + 9 digits (e.g., RA495846917)
        - A valid state MUST BE ONLY 'authorized' or 'canceled' (use 'authorized' for most new returns)
        - A clear, professional memo that mentions specific items being returned from this order
        - Order ID: {order_details["id"]}
        - A valid return reason ID from: {reason_ids}
        - A valid stock location ID from: {stock_location_ids}
        
        Available items to return:
        {json.dumps(order_details["items"], indent=2)}
        
        CRITICAL: The state field MUST ONLY be either 'authorized' or 'canceled' - any other value will cause errors."""

        response = await instructor_client.chat.completions.create(
            model="claude-3-5-haiku-latest",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            response_model=ReturnAuthorizationResponse,
            temperature=0.3,
            max_tokens=8192,
        )

        if response and response.return_authorizations:
            rma = response.return_authorizations[0]

            # Check if the generated RA number already exists
            attempts = 0
            while rma.number in existing_numbers and attempts < 3:
                # If duplicate, generate a new RA number
                import random

                new_number = "RA" + "".join([str(random.randint(0, 9)) for _ in range(9)])
                rma.number = new_number
                attempts += 1

            # Add this number to our tracking set
            existing_numbers.add(rma.number)
            return rma
        return None

    except Exception as e:
        logger.error(f"Error generating return authorization for order {order.get('number', 'unknown')}: {e}")
        return None


async def generate_rmas(number_of_rmas: int, cancelled_percentage: float = 0.3):
    """Generate return authorizations for an eCommerce store.

    Args:
        number_of_rmas: Number of RMAs to generate
        cancelled_percentage: Percentage of RMAs that should be in 'canceled' state (default: 0.3 or 30%)
    """
    import asyncio
    import random

    # Create a semaphore to limit concurrent API calls
    semaphore = asyncio.Semaphore(settings.MAX_CONCURRENT_GENERATION_REQUESTS)

    logger.info(f"Generating return authorizations (max {settings.MAX_CONCURRENT_GENERATION_REQUESTS} concurrent, {cancelled_percentage * 100:.0f}% cancelled)...")

    try:
        # First, ensure we have all required data files
        required_files = {"Return Data": RETURN_AUTHORIZATIONS_FILE, "Orders": ORDERS_FILE, "Stock Locations": STOCK_LOCATIONS_FILE}

        for name, file_path in required_files.items():
            if not file_path.exists():
                logger.error(f"{name} file not found at {file_path}. Please generate required data first.")
                raise FileNotFoundError(f"{name} file not found")

        # Load return reasons
        with Path.open(RETURN_AUTHORIZATIONS_FILE, encoding="utf-8") as f:
            data = json.load(f)
            reason_ids = [reason["id"] for reason in data.get("return_reasons", [])]

        if not reason_ids:
            raise ValueError("No return authorization reasons found")

        # Load completed orders and filter to requested number
        with Path.open(ORDERS_FILE, encoding="utf-8") as f:
            orders_data = json.load(f)
            # Filter only completed orders and limit to requested number
            completed_orders = [order for order in orders_data.get("orders", []) if order.get("state") == "complete"][:number_of_rmas]  # Limit to requested number of RMAs

            if not completed_orders:
                raise ValueError("No completed orders found to associate with returns")

            logger.info(f"Found {len(completed_orders)} completed orders to process")

        # Load stock locations
        with Path.open(STOCK_LOCATIONS_FILE, encoding="utf-8") as f:
            stock_locations_data = json.load(f)
            stock_location_ids = [loc["id"] for loc in stock_locations_data.get("stock_locations", [])]

        if not stock_location_ids:
            logger.warning("No stock locations found, defaulting to ID 1")
            stock_location_ids = [1]

        # Track existing RA numbers to avoid duplicates
        existing_numbers = set()

        # If the file exists, extract existing RA numbers
        if RETURN_AUTHORIZATIONS_FILE.exists():
            try:
                with Path.open(RETURN_AUTHORIZATIONS_FILE, "r", encoding="utf-8") as f:
                    existing_data = json.load(f)
                    for rma in existing_data.get("return_authorizations", []):
                        if "number" in rma:
                            existing_numbers.add(rma["number"])
            except Exception as e:
                logger.warning(f"Could not read existing RA numbers: {e}")

        # Generate RMAs for each completed order in parallel with concurrency limit
        logger.info(f"Generating {len(completed_orders)} return authorizations...")

        async def generate_with_semaphore(order):
            async with semaphore:
                return await generate_rma_for_order(order=order, reason_ids=reason_ids, stock_location_ids=stock_location_ids, existing_numbers=existing_numbers)

        # Create tasks for parallel processing
        rma_tasks = [generate_with_semaphore(order) for order in completed_orders]

        # Use asyncio.gather to run all tasks concurrently, but limited by semaphore
        rmas = await asyncio.gather(*rma_tasks)

        # Filter out any None results from failed generations
        rmas = [rma for rma in rmas if rma is not None]

        if not rmas:
            logger.error("Failed to generate any valid return authorizations")
            raise ValueError("No return authorizations were generated successfully")

        # Enforce cancelled_percentage by overriding states for some RMAs
        num_rmas = len(rmas)
        num_to_cancel = int(num_rmas * cancelled_percentage)

        # Randomly select RMAs to cancel
        cancel_indices = random.sample(range(num_rmas), num_to_cancel)

        # Apply state changes
        for idx in cancel_indices:
            rmas[idx].state = "canceled"

        # Log cancellation statistics
        logger.info(f"Set {num_to_cancel} of {num_rmas} RMAs to 'canceled' state ({cancelled_percentage * 100:.0f}%)")

        # Add incrementing IDs to all RMAs
        for idx, rma in enumerate(rmas, start=1):
            rma.id = idx

        # Convert RMAs to dict format
        new_rmas = [rma.model_dump() for rma in rmas]

        # Load existing data or create new structure
        settings.DATA_PATH.mkdir(parents=True, exist_ok=True)
        RETURN_AUTHORIZATIONS_FILE.parent.mkdir(parents=True, exist_ok=True)

        try:
            if RETURN_AUTHORIZATIONS_FILE.exists():
                with Path.open(RETURN_AUTHORIZATIONS_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
            else:
                data = {"return_reasons": [], "return_authorizations": []}
        except Exception:
            data = {"return_reasons": [], "return_authorizations": []}

        # Update return authorizations while preserving return reasons
        data["return_authorizations"] = new_rmas

        # Save updated data
        with Path.open(RETURN_AUTHORIZATIONS_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        logger.succeed(f"Successfully generated and saved {len(rmas)} return authorizations to {RETURN_AUTHORIZATIONS_FILE}")
        return data

    except Exception as e:
        logger.error(f"Error generating return authorizations: {e}")
        raise


async def seed_rmas():
    """Insert return authorizations into the database."""
    from apps.spree.utils.database import db_client

    logger.start("Inserting return authorizations into spree_return_authorizations table...")

    try:
        # Load return authorizations from JSON file
        if not RETURN_AUTHORIZATIONS_FILE.exists():
            logger.error(f"Return authorizations file not found at {RETURN_AUTHORIZATIONS_FILE}. Run generate command first.")
            raise FileNotFoundError("Return authorizations file not found")

        with Path.open(RETURN_AUTHORIZATIONS_FILE, encoding="utf-8") as f:
            data = json.load(f)

        rmas = data.get("return_authorizations", [])
        logger.info(f"Loaded {len(rmas)} return authorizations from {RETURN_AUTHORIZATIONS_FILE}")

        # Insert each return authorization into the database
        inserted_count = 0
        for rma in rmas:
            try:
                rma_id = rma.get("id")

                # Check if RMA with this ID already exists
                existing_rma = await db_client.fetchrow("SELECT id FROM spree_return_authorizations WHERE id = $1", rma_id)

                if existing_rma:
                    # Update existing RMA
                    await db_client.execute(
                        """
                        UPDATE spree_return_authorizations 
                        SET number = $1, state = $2, order_id = $3, memo = $4,
                            stock_location_id = $5, return_authorization_reason_id = $6,
                            updated_at = NOW()
                        WHERE id = $7
                        """,
                        rma["number"],
                        rma["state"],
                        rma["order_id"],
                        rma["memo"],
                        rma["stock_location_id"],
                        rma["return_authorization_reason_id"],
                        rma_id,
                    )
                    logger.info(f"Updated existing return authorization: {rma['number']} [ID: {rma_id}]")
                else:
                    # Insert new RMA with specified ID
                    await db_client.execute(
                        """
                        INSERT INTO spree_return_authorizations 
                        (id, number, state, order_id, memo, stock_location_id, 
                         return_authorization_reason_id, created_at, updated_at)
                        VALUES ($1, $2, $3, $4, $5, $6, $7, NOW(), NOW())
                        """,
                        rma_id,
                        rma["number"],
                        rma["state"],
                        rma["order_id"],
                        rma["memo"],
                        rma["stock_location_id"],
                        rma["return_authorization_reason_id"],
                    )

                inserted_count += 1

            except Exception as e:
                logger.error(f"Failed to insert/update return authorization {rma.get('number', 'unknown')}: {e}")
                continue

        logger.succeed(f"Successfully processed {inserted_count} return authorizations in the database")

    except Exception as e:
        logger.error(f"Error seeding return authorizations in database: {e}")
        raise


class CustomerReturn(BaseModel):
    """Individual customer return model."""

    id: int = Field(description="Unique identifier for the customer return")  # noqa: A003, RUF100
    number: str = Field(description="Unique customer return number")
    stock_location_id: int = Field(description="ID of the stock location for return")
    created_at: str = Field(description="Timestamp when the return was created")
    updated_at: str = Field(description="Timestamp when the return was last updated")
    store_id: int = Field(description="ID of the store processing the return", default=1)
    public_metadata: dict | None = Field(description="Public metadata for the return", default=None)
    private_metadata: dict | None = Field(description="Private metadata for the return", default=None)
    return_authorizations: list[int] | None = Field(description="List of associated return authorization IDs", default=None)
    # We track order_id for association purposes but it won't be stored in the customer_returns table
    # In Spree, the order-customer return relationship is managed through return items
    associated_order_id: int = Field(description="ID of the order this return is associated with (for internal use only)")


class CustomerReturnResponse(BaseModel):
    """Response format for generated customer returns."""

    customer_returns: list[CustomerReturn]


async def generate_customer_returns(number_of_returns: int):
    """Generate customer returns for an eCommerce store."""
    import random
    from datetime import timedelta

    logger.info("Generating customer returns...")

    try:
        # First, ensure we have all required data files
        required_files = {"Return Authorizations": RETURN_AUTHORIZATIONS_FILE, "Stock Locations": STOCK_LOCATIONS_FILE, "Orders": ORDERS_FILE}

        for name, file_path in required_files.items():
            if not file_path.exists():
                logger.error(f"{name} file not found at {file_path}. Please generate required data first.")
                raise FileNotFoundError(f"{name} file not found")

        # Load stock locations
        with Path.open(STOCK_LOCATIONS_FILE, encoding="utf-8") as f:
            stock_locations_data = json.load(f)
            stock_location_ids = [loc["id"] for loc in stock_locations_data.get("stock_locations", [])]

        if not stock_location_ids:
            logger.warning("No stock locations found, defaulting to ID 1")
            stock_location_ids = [1]

            # Load return authorizations with their orders - ONLY AUTHORIZED RMAs
        with Path.open(RETURN_AUTHORIZATIONS_FILE, encoding="utf-8") as f:
            rma_data = json.load(f)
            rmas = rma_data.get("return_authorizations", [])

            # Filter to only include authorized RMAs
            authorized_rmas = [rma for rma in rmas if rma.get("state") == "authorized"]

            if not authorized_rmas:
                logger.warning("No authorized return authorizations found - customer returns require authorized RMAs")
                raise ValueError("No authorized return authorizations available for customer returns")

            logger.info(f"Found {len(authorized_rmas)} authorized return authorizations for customer returns")

            # Group RMAs by order for easy lookup
            rmas_by_order = {}
            for rma in authorized_rmas:
                order_id = rma.get("order_id")
                if order_id:
                    if order_id not in rmas_by_order:
                        rmas_by_order[order_id] = []
                    rmas_by_order[order_id].append(rma)

            # Only use orders that have RMAs
            orders_with_rmas = list(rmas_by_order.keys())

            if not orders_with_rmas:
                logger.warning("No orders found with authorized return authorizations")
                raise ValueError("No orders with return authorizations available")

        # Track existing customer return numbers to avoid duplicates
        existing_numbers = set()

        # If the file exists, extract existing customer return numbers
        if CUSTOMER_RETURNS_FILE.exists():
            try:
                with Path.open(CUSTOMER_RETURNS_FILE, "r", encoding="utf-8") as f:
                    existing_data = json.load(f)
                    for cr in existing_data.get("customer_returns", []):
                        if "number" in cr:
                            existing_numbers.add(cr["number"])
            except Exception as e:
                logger.warning(f"Could not read existing customer return numbers: {e}")

        # Generate customer returns
        customer_returns = []
        now = datetime.now()

        for i in range(1, number_of_returns + 1):
            # Generate a unique CR number (format: CR + 9 digits)
            cr_number = "CR" + "".join([str(random.randint(0, 9)) for _ in range(9)])

            # Ensure number is unique
            while cr_number in existing_numbers:
                cr_number = "CR" + "".join([str(random.randint(0, 9)) for _ in range(9)])

            existing_numbers.add(cr_number)

            # Random dates within the past 6 months
            days_ago = random.randint(0, 180)
            cr_date = (now - timedelta(days=days_ago)).strftime("%Y-%m-%d %H:%M:%S")

            # Generate metadata
            public_metadata = {
                "source": random.choice(["in_store", "phone", "email", "website"]),
                "tags": random.sample(["priority", "damaged", "incomplete", "refund_pending", "exchange"], k=random.randint(0, 3)),
            }

            private_metadata = {
                "staff_notes": random.choice(
                    [
                        "Customer very upset about product quality",
                        "Items in good condition, eligible for resale",
                        "Package damaged during return shipping",
                        "Missing components noted during inspection",
                        "Return processed outside normal policy window",
                        None,
                    ]
                ),
                "inspection_status": random.choice(["passed", "failed", "pending", None]),
            }

            # Filter None values from metadata
            if private_metadata["staff_notes"] is None:
                del private_metadata["staff_notes"]

            if private_metadata["inspection_status"] is None:
                del private_metadata["inspection_status"]

            if not private_metadata:
                private_metadata = None

            if not public_metadata["tags"]:
                del public_metadata["tags"]

            if not public_metadata:
                public_metadata = None

                # Select a random order ID from orders that have RMAs
            order_id = random.choice(orders_with_rmas) if orders_with_rmas else None
            if not order_id:
                logger.error("No valid order ID with RMAs available for customer return")
                continue

            # Get the RMAs for this order (we already know they exist because we filtered above)
            order_rmas = rmas_by_order[order_id]
            order_rma_ids = [rma["id"] for rma in order_rmas]

            # Associate with at least one RMA from the order
            num_rmas = min(random.randint(1, len(order_rma_ids)), len(order_rma_ids))
            associated_rmas = random.sample(order_rma_ids, num_rmas)

            # Create customer return
            customer_return = CustomerReturn(
                id=i,
                number=cr_number,
                stock_location_id=random.choice(stock_location_ids),
                created_at=cr_date,
                updated_at=cr_date,
                store_id=1,
                public_metadata=public_metadata,
                private_metadata=private_metadata,
                return_authorizations=associated_rmas,
                associated_order_id=order_id,  # Track order_id for association but it won't be stored in DB
            )

            customer_returns.append(customer_return)

        # Convert to dict format for JSON serialization
        cr_list = [cr.model_dump() for cr in customer_returns]

        # Load existing data or create new structure
        settings.DATA_PATH.mkdir(parents=True, exist_ok=True)
        CUSTOMER_RETURNS_FILE.parent.mkdir(parents=True, exist_ok=True)

        # Save to file
        data = {"customer_returns": cr_list}
        with Path.open(CUSTOMER_RETURNS_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        logger.succeed(f"Successfully generated and saved {len(customer_returns)} customer returns to {CUSTOMER_RETURNS_FILE}")
        return data

    except Exception as e:
        logger.error(f"Error generating customer returns: {e}")
        raise


async def seed_customer_returns():
    """Insert customer returns into the database."""

    from apps.spree.utils.database import db_client

    logger.start("Inserting customer returns into spree_customer_returns table...")

    try:
        # Load customer returns from JSON file
        if not CUSTOMER_RETURNS_FILE.exists():
            logger.error(f"Customer returns file not found at {CUSTOMER_RETURNS_FILE}. Run generate command first.")
            raise FileNotFoundError("Customer returns file not found")

        with Path.open(CUSTOMER_RETURNS_FILE, encoding="utf-8") as f:
            data = json.load(f)

        customer_returns = data.get("customer_returns", [])
        logger.info(f"Loaded {len(customer_returns)} customer returns from {CUSTOMER_RETURNS_FILE}")

        # Insert each customer return into the database
        inserted_count = 0
        for cr in customer_returns:
            try:
                cr_id = cr.get("id")

                # Check if customer return with this ID already exists
                existing_cr = await db_client.fetchrow("SELECT id FROM spree_customer_returns WHERE id = $1", cr_id)

                # Convert JSON metadata to JSONB
                public_metadata = json.dumps(cr.get("public_metadata", {})) if cr.get("public_metadata") else "{}"
                private_metadata = json.dumps(cr.get("private_metadata", {})) if cr.get("private_metadata") else "{}"

                # Get return authorizations IDs
                return_authorization_ids = cr.get("return_authorizations", [])

                # Parse string timestamps to datetime objects
                created_at = datetime.strptime(cr["created_at"], "%Y-%m-%d %H:%M:%S")
                updated_at = datetime.strptime(cr["updated_at"], "%Y-%m-%d %H:%M:%S")

                if existing_cr:
                    # Update existing customer return
                    await db_client.execute(
                        """
                        UPDATE spree_customer_returns 
                        SET number = $1, stock_location_id = $2,
                            store_id = $3, public_metadata = $4, private_metadata = $5,
                            updated_at = $6
                        WHERE id = $7
                        """,
                        cr["number"],
                        cr["stock_location_id"],
                        cr["store_id"],
                        public_metadata,
                        private_metadata,
                        updated_at,
                        cr_id,
                    )
                    logger.info(f"Updated existing customer return: {cr['number']} [ID: {cr_id}]")
                else:
                    # Insert new customer return with specified ID
                    await db_client.execute(
                        """
                        INSERT INTO spree_customer_returns 
                        (id, number, stock_location_id, store_id, 
                         public_metadata, private_metadata, created_at, updated_at)
                        VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                        """,
                        cr_id,
                        cr["number"],
                        cr["stock_location_id"],
                        cr["store_id"],
                        public_metadata,
                        private_metadata,
                        created_at,
                        updated_at,
                    )
                    logger.info(f"Inserted new customer return: {cr['number']} [ID: {cr_id}]")

                    # CRITICAL: Every customer return in Spree MUST have return_items that belong to a return_authorization
                # Get the associated return authorizations and order ID
                order_id = cr.get("associated_order_id")
                return_authorization_ids = cr.get("return_authorizations", [])

                if not return_authorization_ids or not order_id:
                    logger.warning(f"Customer return {cr['number']} missing required RMA or order associations")
                    continue

                # Step 1: Find available inventory units for the order
                try:
                    # Verify RMAs actually exist in the database
                    existing_rmas = []
                    for ra_id in return_authorization_ids:
                        ra_exists = await db_client.fetchrow(
                            """
                            SELECT id, order_id FROM spree_return_authorizations
                            WHERE id = $1 AND state = 'authorized'
                            """,
                            ra_id,
                        )

                        if ra_exists:
                            # Make sure RMA belongs to this order
                            if ra_exists["order_id"] == order_id:
                                existing_rmas.append(ra_id)
                            else:
                                logger.warning(f"RMA {ra_id} belongs to order {ra_exists['order_id']}, not {order_id}")

                    if not existing_rmas:
                        logger.warning(f"No valid RMAs found for customer return {cr['number']}")
                        continue

                        # Find inventory units that can be returned with detailed product information
                    # This ensures we're only returning items that were actually in the customer's order
                    inventory_units = await db_client.fetch(
                        """
                        SELECT iu.id, li.price, v.sku, p.name, p.description,
                               COALESCE(iu.state, 'on_hand') as state
                        FROM spree_inventory_units iu
                        JOIN spree_line_items li ON li.id = iu.line_item_id
                        JOIN spree_variants v ON v.id = iu.variant_id
                        JOIN spree_products p ON p.id = v.product_id
                        LEFT JOIN spree_return_items ri ON ri.inventory_unit_id = iu.id
                        WHERE iu.order_id = $1 
                          AND ri.id IS NULL
                          AND iu.state != 'returned'
                        ORDER BY li.price DESC
                        LIMIT 5
                        """,
                        order_id,
                    )

                    # If no available inventory units found, get any inventory units for this order
                    # that haven't been returned yet, regardless of return items
                    if not inventory_units:
                        inventory_units = await db_client.fetch(
                            """
                            SELECT iu.id, li.price, v.sku, p.name,
                                  COALESCE(iu.state, 'on_hand') as state
                            FROM spree_inventory_units iu
                            JOIN spree_line_items li ON li.id = iu.line_item_id
                            JOIN spree_variants v ON v.id = iu.variant_id
                            JOIN spree_products p ON p.id = v.product_id
                            WHERE iu.order_id = $1
                              AND iu.state != 'returned'
                            ORDER BY li.price DESC
                            LIMIT 3
                            """,
                            order_id,
                        )

                    # We must have inventory units to proceed
                    if not inventory_units:
                        logger.warning(f"No inventory units available for customer return {cr['number']} with order {order_id}")
                        # Try to find any inventory units for this order, even if they're already returned
                        inventory_units = await db_client.fetch(
                            """
                            SELECT iu.id, li.price, v.sku, p.name,
                                  COALESCE(iu.state, 'on_hand') as state
                            FROM spree_inventory_units iu
                            JOIN spree_line_items li ON li.id = iu.line_item_id
                            JOIN spree_variants v ON v.id = iu.variant_id
                            JOIN spree_products p ON p.id = v.product_id
                            WHERE iu.order_id = $1
                            ORDER BY li.price DESC
                            LIMIT 3
                            """,
                            order_id,
                        )

                        if not inventory_units:
                            logger.error(f"No inventory units found at all for customer return {cr['number']} with order {order_id}")
                            continue
                        else:
                            logger.info(f"Found {len(inventory_units)} inventory units for order {order_id} (some may be already returned)")

                    # Use the valid RMAs that we've already verified
                    # We can proceed since we've already validated that existing_rmas is not empty

                    # Step 3: Create return items for each inventory unit
                    # The key change: each customer return must have at least one return item
                    # and each return item must belong to a valid return authorization
                    items_created = 0

                    # Distribute inventory units across RMAs
                    for i, unit in enumerate(inventory_units):
                        inventory_unit_id = unit["id"]

                        # Select an RMA for this inventory unit
                        # Using modulo to rotate through the available RMAs
                        ra_id = existing_rmas[i % len(existing_rmas)]

                        # Check if this inventory unit is already associated with a return item
                        existing_return_item = await db_client.fetchrow(
                            """
                            SELECT id FROM spree_return_items 
                            WHERE inventory_unit_id = $1
                            """,
                            inventory_unit_id,
                        )

                        if existing_return_item:
                            # Skip units already being returned
                            logger.info(f"Inventory unit {inventory_unit_id} already has return item, skipping")
                            continue

                        # Use the price that we already fetched with the inventory unit
                        # Each unit in inventory_units now has price, sku, and name information
                        pre_tax_amount = unit["price"]
                        product_name = unit["name"]
                        product_sku = unit["sku"]
                        logger.info(f"Processing return of {product_name} (SKU: {product_sku}) at price {pre_tax_amount}")

                        # Create return item linking customer return, return authorization and inventory unit
                        await db_client.execute(
                            """
                            INSERT INTO spree_return_items 
                            (customer_return_id, return_authorization_id, inventory_unit_id, 
                             pre_tax_amount, acceptance_status, reception_status, created_at, updated_at)
                            VALUES ($1, $2, $3, $4, $5, $6, NOW(), NOW())
                            """,
                            cr_id,
                            ra_id,
                            inventory_unit_id,
                            pre_tax_amount,  # Use the actual price from the order
                            "accepted",
                            "received",  # Set as received per the process_return! method
                        )
                        items_created += 1

                        # A customer return must have at least one return item, but we can create more if available
                        if items_created >= 3:  # Limit to 3 items per customer return
                            break

                    logger.info(f"Created {items_created} return items for customer return {cr['number']} with order {order_id}")

                    # Update inventory units to 'returned' state (only if not already returned)
                    if items_created > 0:
                        for unit in inventory_units[:items_created]:
                            await db_client.execute(
                                """
                                UPDATE spree_inventory_units
                                SET state = 'returned'
                                WHERE id = $1 AND state != 'returned'
                                """,
                                unit["id"],
                            )

                except Exception as e:
                    logger.error(f"Failed to set up return items for customer return {cr['number']}: {e}")

                inserted_count += 1

            except Exception as e:
                logger.error(f"Failed to insert/update customer return {cr.get('number', 'unknown')}: {e}")
                continue

        logger.succeed(f"Successfully processed {inserted_count} customer returns in the database")

    except Exception as e:
        logger.error(f"Error seeding customer returns in database: {e}")
        raise


async def fix_customer_returns():
    """Diagnose and fix customer returns that don't have proper order associations."""

    from apps.spree.utils.database import db_client

    try:
        # Find customer returns that don't have valid return items or order associations
        problematic_returns = await db_client.fetch(
            """
            SELECT cr.id, cr.number
            FROM spree_customer_returns cr
            LEFT JOIN spree_return_items ri ON ri.customer_return_id = cr.id
            LEFT JOIN spree_inventory_units iu ON ri.inventory_unit_id = iu.id
            WHERE ri.id IS NULL OR iu.order_id IS NULL
            GROUP BY cr.id, cr.number
            """
        )

        if not problematic_returns:
            logger.info("0 customer returns fixed (all already have valid associations)")
            return

        fixed_count = 0
        unchanged_count = 0

        # For each problematic return, try to fix it
        for cr in problematic_returns:
            cr_id = cr["id"]

            # Find any inventory units that could be used for this customer return
            # We'll look for any available inventory units from any order
            available_units = await db_client.fetch(
                """
                SELECT iu.id, iu.order_id, li.price, v.sku, p.name
                FROM spree_inventory_units iu
                JOIN spree_line_items li ON li.id = iu.line_item_id
                JOIN spree_variants v ON v.id = iu.variant_id
                JOIN spree_products p ON p.id = v.product_id
                LEFT JOIN spree_return_items ri ON ri.inventory_unit_id = iu.id
                WHERE ri.id IS NULL
                AND iu.state != 'returned'
                ORDER BY iu.order_id
                LIMIT 1
                """
            )

            if not available_units:
                unchanged_count += 1
                continue

            unit = available_units[0]
            order_id = unit["order_id"]

            # Find or create a return authorization for this order
            ra = await db_client.fetchrow(
                """
                SELECT id 
                FROM spree_return_authorizations
                WHERE order_id = $1 AND state = 'authorized'
                LIMIT 1
                """,
                order_id,
            )

            if not ra:
                # Try to find any existing return authorization for this order first
                existing_ra = await db_client.fetchrow(
                    """
                    SELECT id 
                    FROM spree_return_authorizations
                    WHERE order_id = $1
                    LIMIT 1
                    """,
                    order_id,
                )

                if existing_ra:
                    ra_id = existing_ra["id"]
                else:
                    # Skip creating new return authorizations for now
                    # Just use any existing return authorization
                    any_ra = await db_client.fetchrow(
                        """
                        SELECT id, order_id 
                        FROM spree_return_authorizations
                        WHERE state = 'authorized'
                        LIMIT 1
                        """
                    )

                    if any_ra:
                        ra_id = any_ra["id"]
                    else:
                        unchanged_count += 1
                        continue
            else:
                ra_id = ra["id"]

            # Create a return item linking the customer return to the inventory unit
            try:
                await db_client.execute(
                    """
                    INSERT INTO spree_return_items
                    (customer_return_id, return_authorization_id, inventory_unit_id,
                     pre_tax_amount, acceptance_status, reception_status, created_at, updated_at)
                    VALUES ($1, $2, $3, $4, $5, $6, NOW(), NOW())
                    """,
                    cr_id,
                    ra_id,
                    unit["id"],
                    unit["price"],
                    "accepted",
                    "received",
                )

                # Update inventory unit status
                await db_client.execute(
                    """
                    UPDATE spree_inventory_units
                    SET state = 'returned'
                    WHERE id = $1
                    """,
                    unit["id"],
                )

                fixed_count += 1

            except Exception:
                unchanged_count += 1

        logger.info(f"{fixed_count} customer returns fixed, {unchanged_count} unchanged")

    except Exception as e:
        logger.error(f"Error diagnosing customer returns: {e}")
        raise
