import base64
import hashlib
import re
from datetime import datetime
from pathlib import Path

from apps.spree.config.settings import settings
from apps.spree.utils.constants import US_COUNTRY_ID
from apps.spree.utils.database import db_client
from common.logger import Logger


logger = Logger()


async def check_user_exists(user_id: int = 1) -> bool:
    """Check if a user exists with the given ID."""
    try:
        result = await db_client.fetchval("SELECT EXISTS(SELECT 1 FROM spree_users WHERE id = $1)", user_id)
        return result if result is not None else False
    except Exception as e:
        logger.error(f"Error checking if user exists: {e}")
        return False


async def get_user_by_id(user_id: int = 1) -> dict | None:
    """Get user information by ID."""
    try:
        result = await db_client.fetchrow("SELECT id, email, first_name, last_name, created_at, updated_at FROM spree_users WHERE id = $1", user_id)
        if result:
            return dict(result)
        return None
    except Exception as e:
        logger.error(f"Error fetching user: {e}")
        return None


async def update_admin_user(user_id: int = 1) -> dict:
    """Update the admin user record with configured email and name."""
    try:
        # Update the user record with id = 1
        query = """
        UPDATE spree_users 
        SET email = $1, first_name = $2, updated_at = NOW()
        WHERE id = $3
        RETURNING id, email, first_name, updated_at
        """

        result = await db_client.fetchrow(query, settings.SPREE_ADMIN_EMAIL, "Fuzzloft", user_id)

        if result:
            return {
                "success": True,
                "message": "Admin user updated successfully",
                "user": {"id": result["id"], "email": result["email"], "first_name": result["first_name"], "updated_at": result["updated_at"]},
            }
        else:
            logger.warning(f"No user record found with id = {user_id}")
            return {"success": False, "message": f"No user record found with id = {user_id}"}

    except Exception as e:
        logger.error(f"Failed to update user record: {e}")
        return {"success": False, "message": f"Failed to update user record: {e!s}"}


async def update_store(store_id: int = 1) -> dict:
    """Update the store record with configured store name, URL, email addresses, and social media info."""
    try:
        # Extract host from SPREE_URL (split by :// and get the latter part)
        url_parts = settings.SPREE_URL.split("://")
        store_url = url_parts[1] if len(url_parts) > 1 else settings.SPREE_URL

        # Create clean store name for email addresses (remove special characters)
        clean_store_name = re.sub(r"[^a-zA-Z0-9]", "", settings.SPREE_STORE_NAME).lower()
        mail_from_address = f"no-reply@{clean_store_name}.com"
        customer_support_email = f"support@{clean_store_name}.com"

        # Set meta information and social media handles using the store name
        description = settings.DATA_THEME_SUBJECT
        meta_description = settings.DATA_THEME_SUBJECT
        seo_title = settings.DATA_THEME_SUBJECT
        facebook = clean_store_name
        twitter = clean_store_name
        instagram = clean_store_name

        # Update the store record with the configured values
        query = """
        UPDATE spree_stores 
        SET name = $1, url = $2, mail_from_address = $3, customer_support_email = $4, 
            meta_description = $5, description = $6, seo_title = $7, 
            facebook = $8, twitter = $9, instagram = $10, default_country_id = $11, updated_at = NOW()
        WHERE id = $12
        RETURNING id, name, url, mail_from_address, customer_support_email, 
                  meta_description, description, seo_title, facebook, twitter, instagram, default_country_id, updated_at
        """

        result = await db_client.fetchrow(
            query,
            settings.SPREE_STORE_NAME,
            store_url,
            mail_from_address,
            customer_support_email,
            meta_description,
            description,
            seo_title,
            facebook,
            twitter,
            instagram,
            US_COUNTRY_ID,
            store_id,
        )

        if result:
            logger.succeed(f"Successfully updated store record: ID={result['id']}, Name={result['name']}, URL={result['url']}")
            return {
                "success": True,
                "message": "Store updated successfully",
                "store": {
                    "id": result["id"],
                    "name": result["name"],
                    "url": result["url"],
                    "mail_from_address": result["mail_from_address"],
                    "customer_support_email": result["customer_support_email"],
                    "meta_description": result["meta_description"],
                    "description": result["description"],
                    "seo_title": result["seo_title"],
                    "facebook": result["facebook"],
                    "twitter": result["twitter"],
                    "instagram": result["instagram"],
                    "default_country_id": result["default_country_id"],
                    "updated_at": result["updated_at"],
                },
            }
        else:
            logger.warning(f"No store record found with id = {store_id}")
            return {"success": False, "message": f"No store record found with id = {store_id}"}

    except Exception as e:
        logger.error(f"Failed to update store record: {e}")
        return {"success": False, "message": f"Failed to update store record: {e!s}"}


async def check_store_exists(store_id: int = 1) -> bool:
    """Check if a store exists with the given ID."""
    try:
        result = await db_client.fetchval("SELECT EXISTS(SELECT 1 FROM spree_stores WHERE id = $1)", store_id)
        return result if result is not None else False
    except Exception as e:
        logger.error(f"Error checking if store exists: {e}")
        return False


async def get_store_by_id(store_id: int = 1) -> dict | None:
    """Get store information by ID."""
    try:
        result = await db_client.fetchrow("SELECT id, name, url, code, created_at, updated_at FROM spree_stores WHERE id = $1", store_id)
        if result:
            return dict(result)
        return None
    except Exception as e:
        logger.error(f"Error fetching store: {e}")
        return None


async def setup_store_logo(store_id: int = 1) -> dict:
    """Upload and set the store logo from the config/logo.svg file."""
    from apps.spree.core.images import DirectImageSeeder

    try:
        # Check if the logo file exists
        logo_path = Path(__file__).parent.parent.joinpath("config/logo.svg")
        if not logo_path.exists():
            logger.error(f"Logo file not found at {logo_path}")
            return {"success": False, "message": f"Logo file not found at {logo_path}"}

        # Check if store exists
        store_exists = await check_store_exists(store_id)
        if not store_exists:
            logger.error(f"Store with ID = {store_id} does not exist in spree_stores table")
            return {"success": False, "message": f"Store with ID = {store_id} does not exist"}

        # First, check if a StoreLogo already exists
        logo_exists = await db_client.fetchval(
            """
            SELECT EXISTS(
                SELECT 1 FROM spree_assets 
                WHERE viewable_id = $1 
                AND viewable_type = 'Spree::Store' 
                AND type = 'Spree::StoreLogo'
            )
            """,
            store_id,
        )

        # If logo exists, get its ID for updating
        logo_id = None
        if logo_exists:
            logo_id = await db_client.fetchval(
                """
                SELECT id FROM spree_assets 
                WHERE viewable_id = $1 
                AND viewable_type = 'Spree::Store' 
                AND type = 'Spree::StoreLogo'
                LIMIT 1
                """,
                store_id,
            )

        # Use DirectImageSeeder to handle the file upload
        async with DirectImageSeeder() as seeder:
            # Generate unique storage key
            storage_key = seeder._generate_storage_key()

            # Read the file content and calculate MD5 checksum
            with logo_path.open("rb") as f:
                file_content = f.read()
                file_size = len(file_content)

                md5_hash = hashlib.md5(file_content)
                checksum = base64.b64encode(md5_hash.digest()).decode("ascii")

            # Create storage directory and save file
            storage_file_path = seeder._get_storage_path_for_key(storage_key)
            storage_path = Path(storage_file_path)
            storage_path.parent.mkdir(parents=True, exist_ok=True)
            with storage_path.open("wb") as f:
                f.write(file_content)

            # Insert blob record
            blob_id = await seeder._insert_blob_record(storage_key=storage_key, filename="logo.svg", file_size=file_size, checksum=checksum, content_type="image/svg+xml")

            # If logo exists, update it; otherwise create new one
            if logo_id:
                # First, check if there's an existing attachment
                existing_attachment = await db_client.fetchrow(
                    """
                    SELECT id, blob_id FROM active_storage_attachments 
                    WHERE record_type = 'Spree::Asset' 
                    AND record_id = $1 
                    AND name = 'attachment'
                    LIMIT 1
                    """,
                    logo_id,
                )

                if existing_attachment:
                    # Delete existing attachment
                    await db_client.execute("DELETE FROM active_storage_attachments WHERE id = $1", existing_attachment["id"])

                # Update the asset record
                await db_client.execute(
                    """
                    UPDATE spree_assets 
                    SET updated_at = $1
                    WHERE id = $2
                    """,
                    datetime.utcnow(),
                    logo_id,
                )

                asset_id = logo_id
            else:
                # Create new asset record
                asset_id = await seeder._insert_spree_asset(
                    variant_id=store_id,  # Using store_id as viewable_id
                    alt_text="Store Logo",
                    position=1,
                )

                # Update the asset record to be a StoreLogo
                await db_client.execute(
                    """
                    UPDATE spree_assets 
                    SET viewable_type = 'Spree::Store', type = 'Spree::StoreLogo'
                    WHERE id = $1
                    """,
                    asset_id,
                )

            # Create attachment record
            attachment_id = await seeder._insert_attachment_record(asset_id, blob_id)

            logger.succeed(f"Successfully uploaded store logo: blob_id={blob_id}, asset_id={asset_id}")
            return {
                "success": True,
                "message": "Store logo updated successfully",
                "logo": {
                    "asset_id": asset_id,
                    "blob_id": blob_id,
                    "attachment_id": attachment_id,
                },
            }

    except Exception as e:
        logger.error(f"Failed to upload store logo: {e}")
        return {"success": False, "message": f"Failed to upload store logo: {e!s}"}


async def setup_spree():
    """Setup Spree by updating the admin user record and store."""
    logger.start("Starting Spree setup...")

    try:
        # Check if user exists first
        user_exists = await check_user_exists(1)

        if not user_exists:
            logger.error("User with ID = 1 does not exist in spree_users table")
            return

        # Check if store exists
        store_exists = await check_store_exists(1)

        if not store_exists:
            logger.error("Store with ID = 1 does not exist in spree_stores table")
            return

        # Update the admin user
        await update_admin_user(1)

        # Update the store
        await update_store(1)

        # Set up store logo
        await setup_store_logo(1)

    except Exception as e:
        logger.error(f"Spree setup failed with exception: {e}")
        return
