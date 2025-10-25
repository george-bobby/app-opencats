import asyncio
import json
import random
import time
from datetime import datetime, timedelta
from pathlib import Path

from pydantic import BaseModel, Field

from apps.mattermost.config.settings import settings
from apps.mattermost.models.team import Channel, Team, TeamResponse
from apps.mattermost.utils.ai import instructor_client
from apps.mattermost.utils.constants import TEAMS_JSON, USERS_JSON
from apps.mattermost.utils.database import AsyncPostgresClient
from apps.mattermost.utils.faker import faker
from apps.mattermost.utils.mattermost import MattermostClient
from apps.mattermost.utils.openai import get_system_prompt
from common.load_json import load_json
from common.logger import logger


async def update_post_timestamps_for_team(team_id: str, team_name: str, team_data: dict):
    """Update createdat timestamps for posts in all channels of a team using JSON timestamps."""
    try:
        # Create a mapping of channel names to their created_at timestamps from JSON
        channel_timestamps = {}
        for channel_data in team_data.get("channels", []):
            channel_timestamps[channel_data["name"]] = channel_data.get("created_at")

        # Get all channels for this team from the database
        channels_query = """
            SELECT id, name, createat 
            FROM channels 
            WHERE teamid = $1 AND deleteat = 0
        """
        channels = await AsyncPostgresClient.fetch(channels_query, team_id)

        if not channels:
            logger.debug(f"No channels found for team '{team_name}' (ID: {team_id})")
            return

        for channel in channels:
            channel_id = channel["id"]
            channel_name = channel["name"]

            # Use timestamp from JSON data instead of database
            channel_created_at = channel_timestamps.get(channel_name)
            if not channel_created_at:
                logger.debug(f"No created_at timestamp found for channel '{channel_name}' in JSON data")
                continue

            # Get all posts in this channel
            posts_query = """
                SELECT id, createat, userid
                FROM posts 
                WHERE channelid = $1 AND deleteat = 0
                ORDER BY createat ASC
            """
            posts = await AsyncPostgresClient.fetch(posts_query, channel_id)

            if not posts:
                logger.debug(f"No posts found in channel '{channel_name}'")
                continue

            # logger.debug(f"Updating {len(posts)} posts in channel '{channel_name}' using JSON timestamp: {channel_created_at}")

            # Generate realistic timestamps for posts using JSON channel creation time
            current_time = int(datetime.now().timestamp() * 1000)
            time_span = current_time - channel_created_at

            for i, post in enumerate(posts):
                # Distribute posts evenly across the time span since channel creation
                # Add some randomness to make it more realistic
                progress = i / len(posts) if len(posts) > 1 else 0
                base_timestamp = channel_created_at + int(time_span * progress)

                # Add random variation (±6 hours)
                random_offset = random.randint(-6 * 60 * 60 * 1000, 6 * 60 * 60 * 1000)
                new_timestamp = max(channel_created_at + 1000, base_timestamp + random_offset)

                # Ensure timestamp doesn't exceed current time
                new_timestamp = min(new_timestamp, current_time)

                # Update the post's createat and updateat timestamps
                update_query = """
                    UPDATE posts 
                    SET createat = $1, updateat = $2 
                    WHERE id = $3
                """
                await AsyncPostgresClient.execute(update_query, new_timestamp, new_timestamp, post["id"])

            # logger.debug(f"Updated timestamps for {len(posts)} posts in channel '{channel_name}'")

    except Exception as e:
        logger.error(f"Failed to update post timestamps for team '{team_name}': {e}")


async def update_header_change_timestamp(channel_id: str, created_at: int):
    """Update createdat and updateat timestamps for system_header_change messages in a channel."""
    try:
        # Add some realistic delay after team creation (0-7 days for header updates)
        max_delay_ms = 7 * 24 * 60 * 60 * 1000  # 7 days in milliseconds
        random_offset = random.randint(0, max_delay_ms)
        timestamp = created_at + random_offset

        # Ensure timestamp doesn't exceed current time
        current_time = int(datetime.now().timestamp() * 1000)
        timestamp = min(timestamp, current_time)

        # Update the system_header_change message's createat and updateat timestamps
        update_query = """
            UPDATE posts 
            SET createat = $1, updateat = $2 
            WHERE channelid = $3 AND type = 'system_header_change'
        """
        await AsyncPostgresClient.execute(update_query, timestamp, timestamp, channel_id)

    except Exception as e:
        logger.error(f"Failed to update header change message timestamp for channel ID {channel_id}: {e}")


async def update_posts_timestamps_for_channel(channel_id: str, channel_created_at: int):
    """Update createat and updateat timestamps for posts in a specific channel using JSON data."""
    try:
        # Get all posts in this channel
        posts_query = """
            SELECT id, createat, userid
            FROM posts 
            WHERE channelid = $1 AND deleteat = 0
            ORDER BY createat ASC
        """
        posts = await AsyncPostgresClient.fetch(posts_query, channel_id)

        if not posts:
            logger.debug(f"No posts found in channel ID: {channel_id}")
            return

        # logger.debug(f"Updating {len(posts)} posts in channel ID: {channel_id} using channel creation timestamp: {channel_created_at}")

        # Generate realistic timestamps for posts using JSON channel creation time
        current_time = int(datetime.now().timestamp() * 1000)
        time_span = current_time - channel_created_at

        for i, post in enumerate(posts):
            # Distribute posts evenly across the time span since channel creation
            # Add some randomness to make it more realistic
            progress = i / len(posts) if len(posts) > 1 else 0
            base_timestamp = channel_created_at + int(time_span * progress)

            # Add random variation (±6 hours)
            random_offset = random.randint(-6 * 60 * 60 * 1000, 6 * 60 * 60 * 1000)
            new_timestamp = max(channel_created_at + 1000, base_timestamp + random_offset)

            # Ensure timestamp doesn't exceed current time
            new_timestamp = min(new_timestamp, current_time)

            # Update the post's createat and updateat timestamps
            update_query = """
                UPDATE posts 
                SET createat = $1, updateat = $2 
                WHERE id = $3
            """
            await AsyncPostgresClient.execute(update_query, new_timestamp, new_timestamp, post["id"])

        # logger.debug(f"Updated timestamps for {len(posts)} posts in channel ID: {channel_id}")

    except Exception as e:
        logger.error(f"Failed to update post timestamps for channel ID {channel_id}: {e}")


class ChannelResponse(BaseModel):
    channels: list[Channel] = Field(description="A list of channels for the team", min_items=5, max_items=12)


async def generate_channels_for_team_internal(team_name: str, team_display_name: str, team_created_at: int, min_channels: int = 5, max_channels: int = 10) -> list[dict]:
    # Determine number of channels to generate - add unique seed per team for better randomization
    team_seed = hash(team_name + str(time.time_ns())) % 1000000
    random.seed(team_seed)
    num_channels = random.randint(min_channels, max_channels)

    user_prompt = f"""
        Theme: {settings.DATA_THEME_SUBJECT}
        
        Generate EXACTLY {num_channels} channels for the "{team_display_name}" team in a Mattermost system.
        
        CRITICAL: You must generate exactly {num_channels} channels - no more, no less.
        
        Team Context: {team_name} ({team_display_name})
        
        Requirements:
        - Generate exactly {num_channels} channels (this is mandatory)
        - Each channel should have a unique name (lowercase, hyphen-separated if needed)
        - Each channel should have a unique description relevant to the team's purpose
        - Each channel should have a unique display name
        - Mix of public (O) and private (P) channels (roughly 60% public, 40% private)
        - Channels should be relevant to the team's function and purpose
        - Avoid generic names, make them specific to this team's domain
        
        Examples of good channel names for different teams:
        - Engineering: code-reviews, architecture, devops, backend-team, frontend-team
        - Product: roadmap, feature-planning, user-research, product-analytics
        - Marketing: campaigns, content-strategy, social-media, market-research
        - Sales: leads, pipeline, customer-calls, sales-ops
    """

    response = await instructor_client.chat.completions.create(
        model=settings.DEFAULT_MODEL,
        messages=[
            {"role": "system", "content": get_system_prompt()},
            {"role": "user", "content": user_prompt},
        ],
        response_model=ChannelResponse,
        temperature=0.7,
        max_tokens=settings.MAX_OUTPUT_TOKENS,
    )

    channels = [channel.model_dump() for channel in response.channels]
    logger.debug(f"Generated {len(channels)} channels for team '{team_name}' (requested: {num_channels})")

    # Add default channels that every team should have
    default_channels = [
        {"name": "off-topic", "display_name": "Off-Topic", "description": "General discussions and casual conversations", "channel_type": "O", "is_default": True},
        {"name": "town-square", "display_name": "Town Square", "description": "Team-wide announcements and general communication", "channel_type": "O", "is_default": True},
    ]

    # Check if default channels already exist and update them or add them
    existing_channel_names = {channel["name"] for channel in channels}

    for default_channel in default_channels:
        if default_channel["name"] in existing_channel_names:
            # Update existing channel to mark as default
            for channel in channels:
                if channel["name"] == default_channel["name"]:
                    channel["is_default"] = True
                    break
        else:
            # Add new default channel
            channels.append(default_channel)

    # Define default channel names for date assignment logic
    default_channel_names = {"town-square", "off-topic"}

    # Convert team_created_at from milliseconds to datetime for faker operations
    team_created_datetime = datetime.fromtimestamp(team_created_at / 1000)

    for channel in channels:
        # Assign creation dates based on channel type
        if channel["name"] in default_channel_names:
            # Default channels created at the exact same time as the team
            channel["created_at"] = team_created_at
        else:
            # Regular channels created after team creation but never in last 6 months
            six_months_ago = datetime.now() - timedelta(days=180)
            channel_start_date = team_created_datetime + timedelta(days=7)

            # Ensure channel creation date is at least 6 months ago
            if channel_start_date > six_months_ago:
                # If team was created too recently, skip this channel or set to 6 months ago
                created_at = six_months_ago - timedelta(days=random.randint(1, 30))
            else:
                # Normal case: channel created between 1 week after team and 6 months ago
                created_at = faker.date_time_between(start_date=channel_start_date, end_date=six_months_ago)
            # Convert to milliseconds since epoch (bigint format for Mattermost)
            channel["created_at"] = int(created_at.timestamp() * 1000)

    default_channels = len([c for c in channels if c.get("is_default", False)])
    return channels


async def generate_channels_for_team(team: dict, min_channels: int = 5, max_channels: int = 10) -> dict:
    """
    Generate channels for a team and add them to the team dictionary.

    Args:
        team: Team dictionary
        min_channels: Minimum number of channels
        max_channels: Maximum number of channels

    Returns:
        Updated team dictionary with channels
    """
    channels = await generate_channels_for_team_internal(
        team_name=team["name"], team_display_name=team["display_name"], team_created_at=team["created_at"], min_channels=min_channels, max_channels=max_channels
    )

    team["channels"] = channels
    return team


async def generate_teams(count: int, users: int, min_channels: int, max_channels: int):
    """
    Generate teams using AI and save them to teams.json.
    """
    logger.start(f"Generating {count} teams...")

    user_prompt = f"""
        Theme: {settings.DATA_THEME_SUBJECT}

        Generate {count} teams for a Mattermost system.
        There are {users} users available, create teams based on that.

        Requirements:
        - Each team should have a unique name (lowercase, hyphen-separated if needed).
        - Each team should have a unique description.
        - Each team should have a unique display name.
        - Each team should have {min_channels}-{max_channels} channels.
        - Focus on creating realistic team structure, channels, and descriptions only.
    """
    response = await instructor_client.chat.completions.create(
        model=settings.DEFAULT_MODEL,
        messages=[
            {"role": "system", "content": get_system_prompt()},
            {"role": "user", "content": user_prompt},
        ],
        response_model=TeamResponse,
        temperature=0.7,
        max_tokens=settings.MAX_OUTPUT_TOKENS,
    )

    teams: list[Team] = response.teams
    teams_clone = [team.model_dump() for team in teams]

    for team in teams_clone:
        # Ensure teams are created 6 months ago or earlier (never in last 6 months)
        six_months_ago = datetime.now() - timedelta(days=180)
        created_at = faker.date_time_between(start_date="-2y", end_date=six_months_ago)
        team["created_at"] = int(created_at.timestamp() * 1000)

    # Create semaphore to limit concurrent AI requests
    semaphore = asyncio.Semaphore(settings.MAX_CONCURRENT_GENERATION_REQUESTS)
    logger.info(f"Generating channels for {len(teams_clone)} teams concurrently (max {settings.MAX_CONCURRENT_GENERATION_REQUESTS} concurrent requests)...")

    async def process_team_channels(team):
        """Process channel generation for a single team with semaphore control."""
        async with semaphore:
            try:
                team_with_channels = await generate_channels_for_team(team, min_channels=min_channels, max_channels=max_channels)
                return team_with_channels
            except Exception as e:
                logger.error(f"Failed to generate channels for team '{team['name']}': {e}")
                return team

    # Run all team channel generation concurrently with semaphore control
    teams_clone = await asyncio.gather(*[process_team_channels(team) for team in teams_clone])

    # Save teams to JSON
    Path(TEAMS_JSON).parent.mkdir(parents=True, exist_ok=True)
    with Path(TEAMS_JSON).open("w", encoding="utf-8") as f:
        try:
            json.dump(teams_clone, f, ensure_ascii=False, indent=4)
        except TypeError as e:
            raise TypeError(f"Data cannot be serialized to JSON: {e}") from e

    logger.succeed(f"Generated {len(teams_clone)} teams")
    return teams_clone


async def insert_teams():
    """Insert teams into Mattermost (without channels)."""

    teams = load_json(TEAMS_JSON)
    logger.start(f"Inserting {len(teams)} teams...")

    async with MattermostClient() as client:
        try:
            for team in teams:
                response = await client.create_team(
                    name=team["name"],
                    display_name=team["display_name"],
                )
                new_team = await client.get_team_by_name(team["name"])
                team_id = response["id"]

                # Update post timestamps for all channels in this team
                await update_post_timestamps_for_team(team_id, team["name"], team)

                # Only handle default channels here (they already exist in Mattermost)
                for channel in team["channels"]:
                    if channel.get("is_default", False):
                        # logger.debug(f"Processing default channel '{channel['name']}' for team '{team['name']}'")

                        # Get the existing default channel
                        existing_channel = await client.get_channel_by_name(new_team["id"], channel["name"])
                        if existing_channel:
                            # Update posts timestamps for this channel
                            if "created_at" in channel:
                                await update_posts_timestamps_for_channel(existing_channel["id"], channel["created_at"])

                            # Update the channel header with the description
                            if "description" in channel:
                                try:
                                    response = await client.update_channel_header(channel_id=existing_channel["id"], header=channel["description"])
                                    channel_id = response["id"]

                                    # Update the message timestamp to use team's created_at timestamp
                                    team_created_at = team.get("created_at")
                                    if team_created_at and channel_id:
                                        await update_header_change_timestamp(channel_id, team_created_at)

                                except Exception as e:
                                    logger.warning(f"Failed to update header for default channel '{channel['name']}': {e}")

            logger.succeed(f"Inserted {len(teams)} teams")
        except Exception as e:
            raise ValueError(f"Failed to create teams: {e}")


async def create_team_channels(client: MattermostClient, team: dict, channels: list[dict]):
    """
    Create channels for a specific team.
    """
    for channel in channels:
        # Skip default channels (they already exist in Mattermost)
        if channel.get("is_default", False):
            # Update the channel header with the description for default channels
            try:
                existing_channel = await client.get_channel_by_name(team["id"], channel["name"])
                if existing_channel and "description" in channel:
                    await client.update_channel_header(channel_id=existing_channel["id"], header=channel["description"])
            except Exception as e:
                logger.warning(f"Failed to update header for default channel '{channel['name']}': {e}")
            continue

        # Create regular channels
        try:
            new_channel = await client.create_channel(team_id=team["id"], channel_data=channel)
            if not new_channel or "id" not in new_channel:
                # Channel might already exist, try to get it by name
                existing_channel = await client.get_channel_by_name(team["id"], channel["name"])
                if not existing_channel:
                    logger.error(f"Failed to create or find channel '{channel['name']}' in team '{team['name']}'")
                else:
                    logger.debug(f"Found existing channel '{channel['name']}' in team '{team['name']}'")
                    # Update posts timestamps for existing channel
                    if "created_at" in channel:
                        await update_posts_timestamps_for_channel(existing_channel["id"], channel["created_at"])
            else:
                logger.debug(f"Successfully created channel '{channel['name']}' in team '{team['name']}'")
                # Update posts timestamps for newly created channel
                if "created_at" in channel:
                    await update_posts_timestamps_for_channel(new_channel["id"], channel["created_at"])
        except Exception as e:
            logger.error(f"Exception creating channel '{channel['name']}' in team '{team['name']}': {e}")
            continue


async def insert_channels():
    """Insert channels into teams using appropriate team admins."""

    # Load teams data
    teams = load_json(TEAMS_JSON)

    # Load users data
    try:
        users = load_json(USERS_JSON)
    except (FileNotFoundError, ValueError):
        logger.warning("No users.json found.")
        users = []

    logger.start(f"Creating channels for {len(teams)} teams...")

    async with MattermostClient() as client:
        try:
            for team in teams:
                new_team = await client.get_team_by_name(team["name"])
                if not new_team:
                    logger.warning(f"Team '{team['name']}' not found, skipping channel creation")
                    continue

                # Get channels for this team from teams.json
                team_channels = team.get("channels", [])
                if not team_channels:
                    logger.warning(f"No channels found for team '{team['name']}', skipping")
                    continue

                # Find team admin users from the users data (users should exist in Mattermost by now)
                team_admins = []
                team_name = team["name"]

                for user in users:
                    user_team_channels = user.get("team_channels", {})
                    # Check if user has channels in this team and is system admin
                    if user_team_channels.get(team_name) and "system_admin" in user.get("roles", ""):
                        team_admins.append({"username": user["username"]})

                # Select a team admin user for channel creation
                if team_admins:
                    selected_admin = random.choice(team_admins)
                    admin_username = selected_admin["username"]
                    logger.debug(f"Using team admin '{admin_username}' to create channels for team '{team['name']}'")
                else:
                    # Fallback to system admin if no team admins found
                    admin_username = settings.MATTERMOST_OWNER_USERNAME
                    logger.debug(f"No team admins found, using system admin for team '{team['name']}'")

                async with MattermostClient(username=admin_username, password=settings.MATTERMOST_PASSWORD) as admin_client:
                    await create_team_channels(admin_client, new_team, team_channels)

        except Exception as e:
            raise ValueError(f"Failed to create channels: {e}")

        logger.succeed(f"Created channels for {len(teams)} teams")


def get_default_channels() -> list[dict]:
    """Get the default channels that should exist in every team."""
    return [
        {"name": "off-topic", "display_name": "Off-Topic", "description": "General discussions and casual conversations", "channel_type": "O", "is_default": True},
        {"name": "town-square", "display_name": "Town Square", "description": "Team-wide announcements and general communication", "channel_type": "O", "is_default": True},
    ]
