import json
import logging
import random
from datetime import UTC, datetime, timedelta
from pathlib import Path

from apps.gumroad.config.settings import settings
from apps.gumroad.utils.faker import faker
from apps.gumroad.utils.mysql import AsyncMySQLClient
from common.logger import logger


logging.getLogger("elasticsearch").setLevel(logging.WARNING)

# Constants
FOLLOWERS_JSON_FILENAME = "followers.json"


def get_followers_json_path() -> Path:
    """Get the standard path for followers.json file"""
    return settings.DATA_PATH / "generated" / FOLLOWERS_JSON_FILENAME


def generate_exponential_follower_dates(num_followers: int, start_years_ago: int = 2) -> list[datetime]:
    """
    Generate follower creation dates with exponential growth pattern.
    More followers are created in recent months than in earlier periods.
    """
    dates = []
    now = datetime.now(UTC)
    start_date = now - timedelta(days=start_years_ago * 365)
    total_days = (now - start_date).days

    for _ in range(num_followers):
        # Use exponential distribution (lambda=2.0 gives good exponential growth)
        # Higher lambda = more exponential growth
        exponential_value = random.expovariate(2.0)

        # Normalize to 0-1 range and invert so recent dates are more likely
        # The min() ensures we don't go beyond our range
        normalized_position = min(1.0 - (exponential_value / 4.0), 1.0)

        # Convert to actual days from start
        days_from_start = int(normalized_position * total_days)

        # Create the follower date
        follower_date = start_date + timedelta(days=days_from_start)

        # Add some random hours/minutes for variation
        follower_date = follower_date + timedelta(
            hours=random.randint(0, 23),
            minutes=random.randint(0, 59),
            seconds=random.randint(0, 59),
        )

        dates.append(follower_date)

    # Sort dates chronologically
    dates.sort()
    return dates


async def generate_followers(number_of_followers: int = 2000, followed_id: int = 1):
    """Generate fake follower data and save to JSON file"""
    logger.info(f"Generating {number_of_followers} followers with exponential growth pattern")

    # Create generated data directory if it doesn't exist
    json_file_path = get_followers_json_path()
    json_file_path.parent.mkdir(parents=True, exist_ok=True)

    # Generate exponentially distributed follower creation dates
    follower_creation_dates = generate_exponential_follower_dates(number_of_followers, start_years_ago=2)

    logger.info("Generated exponential growth pattern:")
    logger.info(f"  Earliest follower: {follower_creation_dates[0].strftime('%Y-%m-%d')}")
    logger.info(f"  Latest follower: {follower_creation_dates[-1].strftime('%Y-%m-%d')}")

    # Count followers by month to show growth pattern
    monthly_counts = {}
    for date in follower_creation_dates:
        month_key = date.strftime("%Y-%m")
        monthly_counts[month_key] = monthly_counts.get(month_key, 0) + 1

    # Log recent months to show exponential growth
    recent_months = sorted(monthly_counts.keys())[-6:]  # Last 6 months
    logger.info(f"  Recent monthly growth: {[(month, monthly_counts[month]) for month in recent_months]}")

    # Generate follower data
    followers_data = []
    audience_data = []

    for i in range(number_of_followers):
        follower_created_at = follower_creation_dates[i]

        # Updated_at can be same as created_at or later (simulate updates)
        updated_at = faker.date_time_between(start_date=follower_created_at, end_date="now", tzinfo=UTC) if faker.boolean(chance_of_getting_true=30) else follower_created_at

        # Audience record creation can be different from follower creation
        audience_created_at = faker.date_time_between(start_date=follower_created_at, end_date="now", tzinfo=UTC)

        # Generate unique email
        email = f"follower_{i}_{faker.random_int(min=1000, max=99999)}@{faker.domain_name()}"

        # Generate confirmed_at date
        confirmed_at = None
        if faker.boolean(chance_of_getting_true=70):
            confirmed_at = faker.date_time_between(
                start_date=follower_created_at,
                end_date=min(
                    follower_created_at + timedelta(weeks=faker.random_int(min=1, max=8)),
                    datetime.now(UTC),
                ),
                tzinfo=UTC,
            )

        # Follower data
        follower_record = {
            "followed_id": followed_id,
            "email": email,
            "created_at": follower_created_at.isoformat(),
            "updated_at": updated_at.isoformat(),
            "follower_user_id": None,
            "source": None,
            "source_product_id": None,
            "confirmed_at": confirmed_at.isoformat() if confirmed_at else None,
            "deleted_at": None,
            "temp_id": i,  # Temporary ID for reference
        }

        followers_data.append(follower_record)

        # Audience member data
        details = {
            "follower": {
                "temp_id": i,  # Will be replaced with actual ID after insertion
                "created_at": follower_created_at.isoformat(),
            }
        }

        audience_record = {
            "seller_id": followed_id,
            "email": email,
            "details": details,
            "created_at": audience_created_at.isoformat(),
            "updated_at": (
                faker.date_time_between(start_date=audience_created_at, end_date="now", tzinfo=UTC) if faker.boolean(chance_of_getting_true=25) else audience_created_at
            ).isoformat(),
            "customer": faker.random_int(min=0, max=1),
            "follower": 1,
            "affiliate": faker.random_int(min=0, max=1),
            "min_paid_cents": None,
            "max_paid_cents": None,
            "min_created_at": follower_created_at.isoformat(),
            "max_created_at": follower_created_at.isoformat(),
            "min_purchase_created_at": None,
            "max_purchase_created_at": None,
            "follower_created_at": follower_created_at.isoformat(),
            "min_affiliate_created_at": None,
            "max_affiliate_created_at": None,
            "temp_id": i,  # Temporary ID for reference
        }

        audience_data.append(audience_record)

    # Generate unfollow data
    unfollow_percentage = faker.random_int(min=15, max=25) / 100
    num_to_unfollow = int(number_of_followers * unfollow_percentage)

    unfollows_data = []
    if num_to_unfollow > 0:
        logger.info(f"Generating {num_to_unfollow} unfollows ({unfollow_percentage:.1%})")

        # Get confirmed followers for unfollowing
        confirmed_followers = [f for f in followers_data if f["confirmed_at"] is not None]

        # Randomly select followers to unfollow
        followers_to_unfollow = faker.random_sample(confirmed_followers, min(num_to_unfollow, len(confirmed_followers)))

        for follower in followers_to_unfollow:
            # Generate unfollow date between follower creation and now
            follower_created_at = datetime.fromisoformat(follower["created_at"])
            max_unfollow_date = min(
                follower_created_at + timedelta(days=365),
                datetime.now(UTC),
            )

            unfollow_date = faker.date_time_between(
                start_date=follower_created_at + timedelta(days=1),
                end_date=max_unfollow_date,
                tzinfo=UTC,
            )

            unfollow_record = {"temp_id": follower["temp_id"], "email": follower["email"], "unfollow_date": unfollow_date.isoformat(), "followed_id": followed_id}

            unfollows_data.append(unfollow_record)

    # Save data to JSON file
    data_to_save = {
        "followers": followers_data,
        "audience_members": audience_data,
        "unfollows": unfollows_data,
        "metadata": {"number_of_followers": number_of_followers, "followed_id": followed_id, "unfollow_percentage": unfollow_percentage, "generated_at": datetime.now(UTC).isoformat()},
    }

    # json_file_path is already defined above
    with Path.open(json_file_path, "w") as f:
        json.dump(data_to_save, f, indent=2, default=str)

    logger.info(f"Generated follower data saved to: {json_file_path}")
    logger.info(f"Total records: {len(followers_data)} followers, {len(audience_data)} audience members, {len(unfollows_data)} unfollows")

    return json_file_path


async def seed_followers(json_file_path: str | None = None):
    """Insert follower data from JSON file into gumroad database"""
    logger.start("Seeding followers...")

    # Use default path if not provided
    file_path = get_followers_json_path() if json_file_path is None else Path(json_file_path)

    if not file_path.exists():
        logger.error(f"JSON file not found: {file_path}")
        logger.info("Please run generate_followers() first to create the data file")
        return False

    # Load data from JSON file
    with Path.open(file_path) as f:
        data = json.load(f)

    followers_data = data["followers"]
    audience_data = data["audience_members"]
    unfollows_data = data["unfollows"]
    metadata = data["metadata"]

    logger.info(f"Loading follower data from: {file_path}")
    logger.info(f"Data generated at: {metadata['generated_at']}")
    logger.info(f"Inserting {len(followers_data)} followers with {len(unfollows_data)} unfollows")

    # Create and connect to MySQL client
    db = AsyncMySQLClient()
    await db.connect()

    try:
        # Prepare the insert queries
        followers_insert_query = """
        INSERT INTO followers (
            followed_id, email, created_at, updated_at, follower_user_id, source, 
            source_product_id, confirmed_at, deleted_at
        ) VALUES (
            %s, %s, %s, %s, %s, %s, %s, %s, %s
        )
        """

        audience_insert_query = """
        INSERT INTO audience_members (
            seller_id, email, details, created_at, updated_at, customer, follower, affiliate,
            min_paid_cents, max_paid_cents, min_created_at, max_created_at,
            min_purchase_created_at, max_purchase_created_at, follower_created_at,
            min_affiliate_created_at, max_affiliate_created_at
        ) VALUES (
            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
        )
        """

        # Update queries for simulating unfollows
        followers_update_query = """
        UPDATE followers SET deleted_at = %s, updated_at = %s WHERE id = %s
        """

        audience_update_query = """
        UPDATE audience_members SET follower = 0, updated_at = %s WHERE email = %s AND seller_id = %s
        """

        # Track created followers for unfollowing
        created_followers = {}  # temp_id -> actual_id mapping

        # Insert followers
        for follower in followers_data:
            follower_data = (
                follower["followed_id"],
                follower["email"],
                follower["created_at"],
                follower["updated_at"],
                follower["follower_user_id"],
                follower["source"],
                follower["source_product_id"],
                follower["confirmed_at"],
                follower["deleted_at"],
            )

            # Execute single insert and get the follower ID
            async with db.get_cursor() as cursor:
                await cursor.execute(followers_insert_query, follower_data)
                follower_id = cursor.lastrowid
                created_followers[follower["temp_id"]] = follower_id

        # Insert audience members
        for audience in audience_data:
            # Update details with actual follower ID
            details = audience["details"].copy()
            if "follower" in details and "temp_id" in details["follower"]:
                temp_id = details["follower"]["temp_id"]
                if temp_id in created_followers:
                    details["follower"]["id"] = created_followers[temp_id]
                    del details["follower"]["temp_id"]

            audience_data_tuple = (
                audience["seller_id"],
                audience["email"],
                json.dumps(details),
                audience["created_at"],
                audience["updated_at"],
                audience["customer"],
                audience["follower"],
                audience["affiliate"],
                audience["min_paid_cents"],
                audience["max_paid_cents"],
                audience["min_created_at"],
                audience["max_created_at"],
                audience["min_purchase_created_at"],
                audience["max_purchase_created_at"],
                audience["follower_created_at"],
                audience["min_affiliate_created_at"],
                audience["max_affiliate_created_at"],
            )

            # Insert into audience_members
            await db.execute(audience_insert_query, audience_data_tuple)

        # Process unfollows
        for unfollow in unfollows_data:
            temp_id = unfollow["temp_id"]
            if temp_id in created_followers:
                follower_id = created_followers[temp_id]

                # Update follower record with deleted_at (soft delete)
                await db.execute(
                    followers_update_query,
                    (
                        unfollow["unfollow_date"],  # deleted_at
                        unfollow["unfollow_date"],  # updated_at
                        follower_id,  # follower id
                    ),
                )

                # Update audience_members record to set follower = 0
                await db.execute(
                    audience_update_query,
                    (
                        unfollow["unfollow_date"],  # updated_at
                        unfollow["email"],  # email
                        unfollow["followed_id"],  # seller_id
                    ),
                )

        # Verify the insert by counting total followers in the database
        count_query = "SELECT COUNT(*) FROM audience_members WHERE follower = 1"
        result = await db.fetch_one(count_query)
        active_followers = result[0] if result else 0

        # Count deleted followers
        deleted_count_query = """
        SELECT COUNT(*) FROM followers 
        WHERE followed_id = %s AND deleted_at IS NOT NULL
        """
        deleted_result = await db.fetch_one(deleted_count_query, (metadata["followed_id"],))
        deleted_followers = deleted_result[0] if deleted_result else 0

        logger.info(f"Active followers: {active_followers}, Deleted followers: {deleted_followers}")
        logger.info(f"Total follower records created: {len(followers_data)}")

        # Check for duplicates and distribution
        duplicate_query = "SELECT email, COUNT(*) as count FROM audience_members WHERE follower = 1 GROUP BY email HAVING count > 1 LIMIT 5"
        duplicates = await db.fetch_all(duplicate_query)
        if duplicates:
            logger.warning(f"Found duplicate emails: {duplicates}")

        # Check seller_id distribution
        seller_query = "SELECT seller_id, COUNT(*) as follower_count FROM audience_members WHERE follower = 1 GROUP BY seller_id ORDER BY follower_count DESC LIMIT 5"
        seller_dist = await db.fetch_all(seller_query)
        logger.info(f"Top seller_ids by follower count: {seller_dist}")

        return True

    finally:
        # Always disconnect when done
        await db.disconnect()

    logger.succeed("Followers seeded successfully")
