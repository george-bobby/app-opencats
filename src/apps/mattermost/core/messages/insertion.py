"""Thread insertion utilities for Mattermost messages."""

import asyncio
import time

from apps.mattermost.config.settings import settings
from apps.mattermost.core.message import update_post_timestamp
from apps.mattermost.core.messages.attachments import handle_file_attachments
from apps.mattermost.core.messages.post_features import handle_message_pinning, handle_message_reactions
from apps.mattermost.core.messages.post_utils import create_base_post_data
from apps.mattermost.models.message import Thread
from apps.mattermost.utils.database import AsyncPostgresClient
from apps.mattermost.utils.mattermost import MattermostClient
from common.logger import logger


async def insert_thread_messages_batch(
    threads: list[Thread],
    channel_id: str,
    member_ids: list[str],
    users_by_id: dict[str, dict],
    id_to_username_lookup: dict[int, str],
    username_to_id_lookup: dict[str, str],
    max_concurrent_threads: int = 10,
) -> None:
    """
    Insert thread messages into a Mattermost channel using optimized batch processing.

    Args:
        threads: List of Thread objects to insert
        channel_id: Mattermost channel ID
        member_ids: List of member IDs in the channel
        users_by_id: Dictionary mapping user IDs to user data
        id_to_username_lookup: Dictionary mapping local user IDs to usernames
        username_to_id_lookup: Dictionary mapping usernames to Mattermost user IDs
        max_concurrent_threads: Maximum number of threads to process concurrently
    """
    # Create semaphore to limit concurrent thread processing
    thread_semaphore = asyncio.Semaphore(max_concurrent_threads)

    # Process threads sequentially to maintain chronological order
    for thread in threads:
        try:
            await _insert_single_thread_optimized(
                thread=thread,
                channel_id=channel_id,
                member_ids=member_ids,
                users_by_id=users_by_id,
                id_to_username_lookup=id_to_username_lookup,
                username_to_id_lookup=username_to_id_lookup,
                semaphore=thread_semaphore,
            )
            # Small delay between threads to ensure chronological order
            await asyncio.sleep(0.1)
        except Exception as e:
            logger.error(f"Failed to insert thread: {e}")
            continue


async def _insert_single_thread_optimized(
    thread: Thread,
    channel_id: str,
    member_ids: list[str],
    users_by_id: dict[str, dict],
    id_to_username_lookup: dict[int, str],
    username_to_id_lookup: dict[str, str],
    semaphore: asyncio.Semaphore,
) -> None:
    """Insert a single thread with optimized connection reuse and batching."""
    async with semaphore:
        thread_messages = thread.messages
        has_root_message = getattr(thread, "has_root_message", False)
        root_post_id = None

        # Pre-validate all messages
        validated_messages = []

        for msg_idx, msg in enumerate(thread_messages):
            # Validate user mappings upfront
            local_from_user_id = msg.from_user
            from_username = id_to_username_lookup.get(local_from_user_id)

            if not from_username:
                logger.warning(f"No username found for local ID {local_from_user_id}, skipping message")
                continue

            from_mattermost_id = username_to_id_lookup.get(from_username)
            if not from_mattermost_id:
                logger.warning(f"No Mattermost ID found for username {from_username}, skipping message")
                continue

            user_data = users_by_id.get(from_mattermost_id)
            if not user_data:
                logger.warning(f"User with Mattermost ID {from_mattermost_id} not found, skipping message")
                continue

            validated_messages.append(
                {
                    "msg_idx": msg_idx,
                    "msg": msg,
                    "from_username": from_username,
                    "user_data": user_data,
                    "timestamp": getattr(msg, "timestamp", None),
                }
            )

        # Process messages using pooled connections
        for msg_data in validated_messages:
            msg_idx = msg_data["msg_idx"]
            msg = msg_data["msg"]
            from_username = msg_data["from_username"]
            user_data = msg_data["user_data"]
            timestamp = msg_data["timestamp"]

            try:
                # Create client for this user
                async with MattermostClient(username=user_data["username"], password=settings.MATTERMOST_PASSWORD) as client:
                    # Handle file attachments if any
                    file_ids = await handle_file_attachments(msg.model_dump(), channel_id, client)

                    # Create post data using shared utility
                    post_data = create_base_post_data(
                        channel_id=channel_id,
                        message_content=msg.content,
                        timestamp=timestamp,
                        root_id=root_post_id if (has_root_message and msg_idx > 0 and root_post_id) else None,
                        file_ids=file_ids if file_ids else None,
                    )

                    # Create the message
                    main_post = await client.create_post(post_data=post_data)

                    if not main_post:
                        logger.warning(f"Failed to create post for user {from_username}")
                        continue

                    # Update timestamp in database to ensure it's properly set
                    if main_post.get("id") and timestamp:
                        await update_post_timestamp(main_post["id"], timestamp)

                    # Store the first message ID as root for subsequent threaded replies
                    if main_post.get("id") and msg_idx == 0:
                        root_post_id = main_post["id"]

                    # Handle message features using shared modules
                    if main_post.get("id"):
                        # Handle pinning
                        await handle_message_pinning(msg.model_dump(), main_post["id"], client)

                        # Handle reactions with proper user authentication
                        await handle_message_reactions(msg.model_dump(), main_post["id"], member_ids, users_by_id)

                    # Reduced rate limiting for batch operations
                    await asyncio.sleep(0.2)

            except Exception as e:
                logger.warning(f"Failed to create message for user {from_username}: {e}")
                continue

        # Update threads table if this thread has replies and has_root_message is True
        if has_root_message and root_post_id and len(validated_messages) > 1:
            await _update_thread_metadata(
                root_post_id=root_post_id,
                last_reply_timestamp=validated_messages[-1]["timestamp"] if validated_messages else None,
            )


async def _update_thread_metadata(root_post_id: str, last_reply_timestamp: int | None) -> None:
    """Update only the lastreplyat column in the threads table."""
    try:
        # Use current timestamp if last_reply_timestamp is not provided
        if last_reply_timestamp is None:
            last_reply_timestamp = int(time.time() * 1000)

        # Only update lastreplyat column
        update_query = """
        UPDATE threads 
        SET lastreplyat = $1
        WHERE postid = $2
        """

        await AsyncPostgresClient.execute(update_query, last_reply_timestamp, root_post_id)

    except Exception as e:
        logger.warning(f"Failed to update thread lastreplyat for post {root_post_id}: {e}")


async def insert_thread_messages(
    threads: list[Thread],
    channel_id: str,
    member_ids: list[str],
    users_by_id: dict[str, dict],
    id_to_username_lookup: dict[int, str],
    username_to_id_lookup: dict[str, str],
) -> None:
    """
    Insert thread messages into a Mattermost channel using optimized batch processing.

    This function maintains backward compatibility while using the optimized batch implementation.
    """
    await insert_thread_messages_batch(
        threads=threads,
        channel_id=channel_id,
        member_ids=member_ids,
        users_by_id=users_by_id,
        id_to_username_lookup=id_to_username_lookup,
        username_to_id_lookup=username_to_id_lookup,
        max_concurrent_threads=getattr(settings, "MAX_CONCURRENT_THREADS", 10),
    )
