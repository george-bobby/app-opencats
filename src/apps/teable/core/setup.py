from apps.teable.utils.teable import TeableAPIError, get_teable_client
from common.logger import Logger


logger = Logger()


async def setup_teable():
    """
    Setup Teable connection by getting a reusable client that automatically logs in.

    Returns:
        TeableClient: Authenticated client instance
    """
    try:
        # Get the global reusable client that automatically handles login/signup
        client = await get_teable_client()
        return client

    except Exception as e:
        logger.error(f"❌ Teable setup failed: {e}")
        raise


async def verify_teable_connection():
    """
    Verify that Teable connection is working properly

    Returns:
        bool: True if connection is working, False otherwise
    """
    try:
        # Use the global client
        client = await get_teable_client()

        # Get current user info
        user_info = await client.get_current_user()
        logger.info(f"✓ Teable connection verified for user: {user_info.get('email', 'Unknown')}")

        # Try to get spaces to verify API access
        spaces = await client.get_spaces()
        logger.info(f"✓ API access verified - found {len(spaces.get('spaces', []))} spaces")

        return True

    except Exception as e:
        logger.error(f"✗ Teable connection verification failed: {e}")
        return False


async def setup_teable_with_retry(max_retries: int = 3, delay: float = 2.0):
    """
    Setup Teable with retry logic

    Args:
        max_retries: Maximum number of retry attempts
        delay: Delay between retries in seconds

    Returns:
        Authentication result or raises exception
    """
    import asyncio

    for attempt in range(max_retries + 1):
        try:
            logger.info(f"Teable setup attempt {attempt + 1}/{max_retries + 1}")
            result = await setup_teable()

            # Verify the connection works
            if await verify_teable_connection():
                logger.info("✅ Teable setup completed successfully")
                return result
            else:
                raise TeableAPIError("Connection verification failed")

        except Exception as e:
            if attempt == max_retries:
                logger.error(f"❌ Teable setup failed after {max_retries + 1} attempts")
                raise
            else:
                logger.fail(f"⚠ Attempt {attempt + 1} failed: {e}")
                print(f"Retrying in {delay} seconds...")
                await asyncio.sleep(delay)
                delay *= 1.5  # Exponential backoff
