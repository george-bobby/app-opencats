from apps.spree.utils.constants import ROLES
from apps.spree.utils.database import db_client
from common.logger import Logger


async def seed_roles():
    """Insert roles into the database."""

    logger = Logger()

    logger.start("Inserting roles into spree_roles table...")

    try:
        # Insert each role into the database
        inserted_count = 0
        for role_name in ROLES:
            try:
                # Check if role with this name already exists
                existing_role = await db_client.fetchrow("SELECT id FROM spree_roles WHERE name = $1", role_name)

                if existing_role:
                    # Update existing role
                    await db_client.execute(
                        """
                        UPDATE spree_roles 
                        SET updated_at = NOW()
                        WHERE name = $1
                        """,
                        role_name,
                    )
                    logger.info(f"Updated existing role: {role_name}")
                else:
                    # Insert new role
                    await db_client.execute(
                        """
                        INSERT INTO spree_roles (name, created_at, updated_at)
                        VALUES ($1, NOW(), NOW())
                        """,
                        role_name,
                    )

                inserted_count += 1

            except Exception as e:
                logger.error(f"Failed to insert/update role {role_name}: {e}")
                continue

        logger.succeed(f"Successfully processed {inserted_count} roles in the database")

    except Exception as e:
        logger.error(f"Error seeding roles in database: {e}")
        raise
