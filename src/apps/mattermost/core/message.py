import asyncio
import contextlib
import random
from pathlib import Path
from typing import Any

from apps.mattermost.config.settings import settings
from apps.mattermost.utils.database import AsyncPostgresClient
from apps.mattermost.utils.mattermost import MattermostClient
from common.load_json import load_json
from common.logger import logger


CHANNEL_MESSAGES_PATH = settings.DATA_PATH.joinpath("channel-messages")
TEAMS_PATH = settings.DATA_PATH.joinpath("teams.json")

# Note: Timestamp processing system removed - posts now use correct timestamps during creation


async def update_post_timestamp(post_id: str, timestamp: int):
    """Update a post's timestamp in the database."""
    query = """
    UPDATE 
        posts 
    SET 
        createat = $1, 
        updateat = $1
    WHERE 
        id = $2;
    """

    await AsyncPostgresClient.execute(query, timestamp, post_id)


async def _process_timestamp_batch(batch: list):
    """Process a batch of timestamp updates."""
    if not batch:
        return

    try:
        # Build the query for batch update
        query = """
        UPDATE posts 
        SET createat = data.timestamp, updateat = data.timestamp
        FROM (VALUES %s) AS data(post_id, timestamp)
        WHERE posts.id = data.post_id::text;
        """

        # Prepare values for the query
        values = [(item["post_id"], item["timestamp"]) for item in batch]

        # Format the VALUES clause
        values_clause = ", ".join([f"('{post_id}', {timestamp})" for post_id, timestamp in values])
        final_query = query.replace("%s", values_clause)

        await AsyncPostgresClient.execute(final_query)
        # logger.debug(f"Updated timestamps for {len(batch)} posts")

    except Exception as e:
        logger.warning(f"Failed to update timestamp batch: {e}")
        # Fallback to individual updates
        for item in batch:
            try:
                await update_post_timestamp(item["post_id"], item["timestamp"])
            except Exception as individual_error:
                logger.debug(f"Failed to update timestamp for post {item['post_id']}: {individual_error}")


async def _cleanup_timestamp_processor():
    """Clean up the timestamp processor and wait for remaining updates."""
    global timestamp_processor_task, processing_complete

    if timestamp_processor_task:
        # Signal completion and wait for processor to finish
        processing_complete.set()

        remaining_updates = []
        remaining_updates = []

        if remaining_updates:
            logger.info(f"Processing {len(remaining_updates)} remaining timestamp updates...")
            await _process_timestamp_batch(remaining_updates)

        # Wait for the processor task to complete
        try:
            await asyncio.wait_for(timestamp_processor_task, timeout=10.0)
        except TimeoutError:
            logger.warning("Timestamp processor cleanup timed out")
            timestamp_processor_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await timestamp_processor_task

        timestamp_processor_task = None


def _generate_reply_timestamps(replies: list[dict], post_timestamp: int) -> list[dict]:
    """Generate realistic timestamps for replies."""
    replies_with_timestamps = []
    current_timestamp = post_timestamp

    for reply in replies:
        # Add some time between replies (1-30 minutes)
        time_gap = random.randint(60_000, 1_800_000)  # 1-30 minutes in milliseconds
        current_timestamp += time_gap

        reply_copy = reply.copy()
        reply_copy["timestamp"] = current_timestamp
        replies_with_timestamps.append(reply_copy)

    return replies_with_timestamps


async def _process_single_channel(channel_file: Path, semaphore: asyncio.Semaphore, shared_data: dict[str, Any]) -> None:
    """Process messages for a single channel file with concurrency control."""
    async with semaphore:
        try:
            # Load channel threads data (new ChannelThreads format)
            channel_data = load_json(channel_file)
            filename = channel_file.stem

            # Parse team name and channel name from filename (e.g., "human-resources.off-topic" -> "human-resources", "off-topic")
            if "." in filename:
                # Split on first dot to separate team from channel
                parts = filename.split(".", 1)  # Split on first dot only
                team_name = parts[0]
                channel_name = parts[1]
            else:
                # Fallback for files without team prefix (shouldn't happen with new format)
                team_name = "unknown"
                channel_name = filename

            # Look up channel by team-specific key first, fall back to channel name only
            team_channel_key = f"{team_name}-{channel_name}"
            channel_lookup_data = shared_data["channels_lookup"].get(team_channel_key)

            if not channel_lookup_data:
                # Fallback to channel name only (for backward compatibility)
                channel_lookup_data = shared_data["channels_lookup"].get(channel_name, {})

            channel_id = channel_lookup_data.get("id") if channel_lookup_data else None

            if not channel_id:
                logger.debug(f"Channel ID not found for: {team_name}/{channel_name}")
                return

            # logger.debug(f"Inserting channel messages for channel: {team_name}/{channel_name}")

            # Get channel members
            async with MattermostClient() as client:
                channel_members = await client.get_channel_members(channel_id)

            member_ids = [member["user_id"] for member in channel_members]

            # Extract threads from the ChannelThreads format
            threads_data = channel_data.get("threads", [])

            if not threads_data:
                logger.debug(f"No threads found in channel {team_name}/{channel_name}")
                return

            # Convert to Thread objects and use shared insertion logic
            from apps.mattermost.models.message import Message, Thread

            threads = []
            for thread_data in threads_data:
                messages = []
                for msg_data in thread_data.get("messages", []):
                    message = Message(**msg_data)
                    messages.append(message)

                thread = Thread(messages=messages, has_root_message=thread_data.get("has_root_message"), should_have_attachments=thread_data.get("should_have_attachments"))
                threads.append(thread)

            # Use shared insertion logic from core/messages/insertion.py
            from apps.mattermost.core.messages.insertion import insert_thread_messages

            # Create users_by_id lookup for reactions (all channel members)
            users_by_id = {}
            async with MattermostClient() as client:
                mattermost_users = await client.get_users()
                # Build lookup for all users that might be in this channel
                for user in mattermost_users:
                    if user["id"] in member_ids:  # Only include actual channel members
                        users_by_id[user["id"]] = {"username": user["username"]}

            await insert_thread_messages(
                threads=threads,
                channel_id=channel_id,
                member_ids=member_ids,
                users_by_id=users_by_id,
                id_to_username_lookup=shared_data["id_to_username_lookup"],
                username_to_id_lookup=shared_data["username_to_id_lookup"],
            )

            logger.debug(f"Inserted channel messages successfully for channel: {team_name}/{channel_name}")

        except Exception as e:
            logger.error(f"Failed to process channel {channel_file.stem}: {e}")


async def _setup_shared_resources() -> dict[str, Any]:
    """Setup shared resources that all concurrent tasks will use."""
    teams = load_json(TEAMS_PATH)

    # Load users from users.json to get ID-to-username mapping
    users_path = settings.DATA_PATH.joinpath("users.json")
    users_data = load_json(users_path)

    # Create lookup from user ID (from users.json) to username
    id_to_username_lookup = {user["id"]: user["username"] for user in users_data}

    async with MattermostClient() as client:
        # Get all teams first to map team names to IDs
        mattermost_teams = await client.get_teams()
        teams_lookup = {team["name"]: team["id"] for team in mattermost_teams}

        # Get Mattermost users for username-to-id mapping
        mattermost_users = await client.get_users()
        username_to_id_lookup = {user["username"]: user["id"] for user in mattermost_users}

        # Build team-aware channels lookup (using general channels endpoint to include private channels)
        channels_lookup = {}
        all_channels = await client.get_channels()

        if all_channels:
            for channel in all_channels:
                # Find the team name for this channel
                team_name = None
                for team_data in teams:
                    if teams_lookup.get(team_data["name"]) == channel["team_id"]:
                        team_name = team_data["name"]
                        break

                if team_name:
                    # Store channels by both team-specific key and channel name only (for backward compatibility)
                    channel_key = f"{team_name}-{channel['name']}"
                    channels_lookup[channel_key] = channel
                    # Also store by channel name only (will be overwritten if multiple teams have same channel name)
                    channels_lookup[channel["name"]] = channel

    return {
        "id_to_username_lookup": id_to_username_lookup,
        "username_to_id_lookup": username_to_id_lookup,
        "channels_lookup": channels_lookup,
        "teams_lookup": teams_lookup,
    }


async def insert_channel_messages():
    try:
        # Setup shared resources
        shared_data = await _setup_shared_resources()

        # Get all channel files
        channel_files = [entry for entry in Path.iterdir(CHANNEL_MESSAGES_PATH) if entry.is_file()]

        if not channel_files:
            logger.info("No channel message files found")
            return

        # Create semaphore to limit concurrent processing
        semaphore = asyncio.Semaphore(settings.MAX_THREADS)

        logger.start("Inserting channel messages...")

        # Create tasks for all channel message files
        tasks = [_process_single_channel(channel_file, semaphore, shared_data) for channel_file in channel_files]

        # Execute all tasks concurrently
        await asyncio.gather(*tasks, return_exceptions=True)

        logger.succeed("Completed processing all channel messages")

    finally:
        logger.succeed("Completed timestamp updates")
