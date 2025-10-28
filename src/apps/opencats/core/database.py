"""Database operations for OpenCATS."""

import aiomysql
from aiomysql import Pool

from apps.opencats.config.constants import SEEDED_TABLES
from apps.opencats.config.settings import settings
from common.logger import logger


async def get_connection_pool() -> Pool:
    """Create and return a MySQL connection pool."""
    # Parse DATABASE_URL: mysql://user:password@host:port/database
    db_url = settings.DATABASE_URL.replace("mysql://", "")
    
    # Split credentials and host info
    credentials, host_info = db_url.split("@")
    user, password = credentials.split(":")
    host_port, database = host_info.split("/")
    host, port = host_port.split(":")
    
    pool = await aiomysql.create_pool(
        host=host,
        port=int(port),
        user=user,
        password=password,
        db=database,
        autocommit=True,
    )
    
    return pool


async def clear_seeded_data():
    """Clear only the seeded data tables, preserving users and system data."""
    logger.info("🧹 Connecting to OpenCATS database...")
    
    pool = await get_connection_pool()
    
    try:
        async with pool.acquire() as conn:
            async with conn.cursor() as cursor:
                # Disable foreign key checks temporarily for easier deletion
                logger.info("🔓 Disabling foreign key checks...")
                await cursor.execute("SET FOREIGN_KEY_CHECKS = 0")
                
                # Clear each table from SEEDED_TABLES constant
                for table in SEEDED_TABLES:
                    try:
                        # Check if table exists
                        await cursor.execute(f"SHOW TABLES LIKE '{table}'")
                        result = await cursor.fetchone()
                        
                        if result:
                            # Get count before deletion
                            await cursor.execute(f"SELECT COUNT(*) FROM {table}")
                            count_result = await cursor.fetchone()
                            count = count_result[0] if count_result else 0
                            
                            if count > 0:
                                # Truncate the table (faster than DELETE and resets auto-increment)
                                await cursor.execute(f"TRUNCATE TABLE {table}")
                                logger.info(f"🗑️  Cleared {count} rows from table: {table}")
                            else:
                                logger.info(f"⏭️  Table {table} already empty")
                        else:
                            logger.warning(f"⚠️  Table {table} does not exist, skipping...")
                            
                    except Exception as e:
                        logger.error(f"❌ Error clearing table {table}: {e}")
                        # Continue with other tables even if one fails
                        continue
                
                # Re-enable foreign key checks
                logger.info("🔒 Re-enabling foreign key checks...")
                await cursor.execute("SET FOREIGN_KEY_CHECKS = 1")
                
                logger.succeed("✅ Seeded data cleared successfully!")
                
    except Exception as e:
        logger.error(f"❌ Database error: {e}")
        raise
    finally:
        pool.close()
        await pool.wait_closed()
        logger.info("🔌 Database connection closed")
