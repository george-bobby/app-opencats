import asyncio
import json
import random
from datetime import datetime, timedelta
from pathlib import Path

from apps.mattermost.config.settings import settings
from apps.mattermost.models.user import ChannelAssignmentResponse, PositionResponse
from apps.mattermost.utils.ai import instructor_client
from apps.mattermost.utils.constants import BATCH_SIZE, TEAMS_JSON, UNIQUE_POSITIONS, USERS_JSON
from apps.mattermost.utils.database import AsyncPostgresClient
from apps.mattermost.utils.faker import create_faker_with_user_tracking
from apps.mattermost.utils.mattermost import MattermostClient
from apps.mattermost.utils.openai import get_system_prompt
from common.load_json import load_json
from common.logger import logger
from common.save_to_json import save_to_json


def generate_clustered_join_dates(earliest_join: int, latest_join: int, num_users: int) -> list[int]:
    """
    Generate clustered join dates where multiple users join on the same dates.
    Creates realistic "join events" where groups of users join together.

    Args:
        earliest_join: Earliest possible join timestamp (ms)
        latest_join: Latest possible join timestamp (ms)
        num_users: Number of users that need join dates

    Returns:
        List of join timestamps (one per user)
    """
    if num_users <= 0:
        return []

    if earliest_join >= latest_join:
        return [earliest_join] * num_users

    time_range = latest_join - earliest_join

    # Create 3-7 "join events" depending on number of users
    # More users = more potential join events, but still clustered
    if num_users <= 3:
        num_events = 1
    elif num_users <= 8:
        num_events = random.randint(2, 3)
    elif num_users <= 15:
        num_events = random.randint(3, 5)
    else:
        num_events = random.randint(4, 7)

    # Generate event timestamps with bias toward earlier dates
    event_timestamps = []
    for _ in range(num_events):
        # Strong bias toward early adoption (most join events happen early)
        random_factor = random.random() ** 3.5

        # Push 75% of late events to early 25% of timeline
        if random_factor > 0.25:
            random_factor = random_factor * 0.25

        event_time = earliest_join + int(time_range * random_factor)
        event_timestamps.append(event_time)

    # Sort events chronologically
    event_timestamps.sort()

    # Assign users to events with preference for earlier events
    user_assignments = []
    users_remaining = num_users

    for i, event_time in enumerate(event_timestamps):
        events_remaining = len(event_timestamps) - i

        if events_remaining == 1:
            # Last event gets all remaining users
            users_for_event = users_remaining
        else:
            # Earlier events get more users (bias toward early adoption)
            # First event gets 30-60% of remaining users
            # Later events get smaller groups
            if i == 0:
                min_pct, max_pct = 0.3, 0.6
            elif i == 1:
                min_pct, max_pct = 0.2, 0.5
            else:
                min_pct, max_pct = 0.1, 0.4

            min_users = max(1, int(users_remaining * min_pct))
            max_users = min(users_remaining - events_remaining + 1, int(users_remaining * max_pct))
            users_for_event = random.randint(min_users, max_users)

        # Add timestamps for all users in this event
        for _ in range(users_for_event):
            # Add small random variation within the same day (±4 hours)
            variation = random.randint(-4 * 60 * 60 * 1000, 4 * 60 * 60 * 1000)
            user_assignments.append(event_time + variation)

        users_remaining -= users_for_event

        if users_remaining <= 0:
            break

    # Shuffle the final assignments to randomize which user gets which timestamp
    random.shuffle(user_assignments)

    return user_assignments[:num_users]


async def update_channel_member_timestamp(channel_id: str, user_id: str, joined_at: int):
    """Update createat timestamp for a channel member."""
    try:
        update_query = """
            UPDATE posts 
            SET createat = $1 
            WHERE channelid = $2 AND userid = $3
        """
        await AsyncPostgresClient.execute(update_query, joined_at, channel_id, user_id)
    except Exception as e:
        logger.error(f"Failed to update channel member timestamp: {e}")


def validate_positions(generated_positions: list[str], existing_positions: list[str]) -> list[str]:
    """Validate generated positions to ensure no duplicates of unique roles."""
    if not existing_positions:
        existing_positions = []

    validated_positions = []
    existing_set = {pos.lower() for pos in existing_positions}

    for position in generated_positions:
        position_lower = position.lower()

        # Check if this position is unique and already exists
        is_unique_position = any(unique_pos.lower() in position_lower or position_lower in unique_pos.lower() for unique_pos in UNIQUE_POSITIONS)

        if is_unique_position:
            # Check if a similar unique position already exists
            position_exists = any(existing_pos in position_lower or position_lower in existing_pos for existing_pos in existing_set)

            if position_exists:
                logger.warning(f"Skipping duplicate unique position: {position} (similar to existing positions)")
                continue

        validated_positions.append(position)
        existing_set.add(position_lower)

    return validated_positions


async def generate_positions(count: int) -> list[str]:
    """Generate realistic company structure using AI based on theme and company size."""
    if count <= 20:
        company_size = "startup (10-20 employees)"
        leadership_guidance = "1-2 founders/executives, mostly individual contributors and 1-2 team leads"
    elif count <= 50:
        company_size = "small company (20-50 employees)"
        leadership_guidance = "Small leadership team (2-3 executives), department heads, team leads, and individual contributors"
    elif count <= 100:
        company_size = "medium company (50-100 employees)"
        leadership_guidance = "Executive team, department directors/managers, team leads, senior and junior individual contributors"
    else:
        company_size = "large company (100+ employees)"
        leadership_guidance = "Full executive team, multiple management layers, team leads, and diverse individual contributors"

    position_prompt = f"""
        Theme: {settings.DATA_THEME_SUBJECT}
        
        Generate exactly {count} realistic and diverse job positions for a {company_size} in the US.
        
        Company Structure Guidance: {leadership_guidance}
        
        Requirements:
        - Create a realistic organizational structure appropriate for {count} employees
        - Include positions from relevant departments: Engineering, Product, Marketing, Sales, Operations, HR, Finance, IT
        - Mix of seniority levels: junior, mid-level, senior, lead, management, executive (as appropriate for company size)
        - Positions should be appropriate for the theme: {settings.DATA_THEME_SUBJECT}
        - Each position should be unique and realistic
        - Use standard job titles that would be found in a modern company
        - Ensure only ONE person has unique executive roles (CEO, CTO, CFO, etc.)
        - Focus on creating a balanced, realistic company structure
        
        Examples by department:
        - Engineering: Software Engineer, Senior Developer, Tech Lead, Engineering Manager, DevOps Engineer
        - Product: Product Manager, UX Designer, Product Analyst, Product Marketing Manager
        - Marketing: Marketing Specialist, Content Manager, Social Media Manager, Marketing Director
        - Sales: Sales Representative, Account Manager, Sales Manager, Business Development
        - Operations: Operations Coordinator, Project Manager, Operations Manager
        - Support: Customer Success Manager, Support Specialist, Technical Writer
        
        Generate a cohesive team structure that makes sense for a {company_size}.
    """

    try:
        response = await instructor_client.chat.completions.create(
            model=settings.DEFAULT_MODEL,
            messages=[
                {"role": "system", "content": get_system_prompt()},
                {"role": "user", "content": position_prompt},
            ],
            response_model=PositionResponse,
            temperature=0.7,
            max_tokens=settings.MAX_OUTPUT_TOKENS,
        )

        if response and response.positions:
            validated_positions = validate_positions(response.positions, [])
            return validated_positions
        else:
            logger.warning("No positions generated by AI, using fallback positions")
            return ["Software Engineer", "Product Manager", "Marketing Specialist", "DevOps Engineer", "UX Designer", "Customer Success Manager"]
    except Exception as e:
        logger.error(f"Failed to generate positions with AI: {e}")
        return ["Software Engineer", "Product Manager", "Marketing Specialist", "HR Manager", "DevOps Engineer", "UX Designer"]


def generate_joined_at_timestamp(faker_instance, position: str, roles: str) -> int:
    """Generate realistic joined_at timestamp based on position and role."""
    current_timestamp = int(datetime.now().timestamp() * 1000)
    current_date = datetime.fromtimestamp(current_timestamp / 1000)

    earliest_join = current_date - timedelta(days=365 * 2.5)
    latest_join = current_date - timedelta(days=30)

    earliest_timestamp = int(earliest_join.timestamp() * 1000)
    latest_timestamp = int(latest_join.timestamp() * 1000)

    position_lower = position.lower()
    is_leadership = any(keyword in position_lower for keyword in ["manager", "director", "lead", "head", "chief", "architect", "senior"])

    if "system_admin" in roles or is_leadership:
        time_range = (latest_timestamp - earliest_timestamp) * 0.6
        joined_timestamp = earliest_timestamp + faker_instance.random_int(0, int(time_range))
    else:
        joined_timestamp = faker_instance.random_int(earliest_timestamp, latest_timestamp)

    return joined_timestamp


def generate_user_batch(count: int, faker_instance, seen_usernames: set, seen_emails: set, positions: list[str], start_id: int = 1) -> list[dict]:
    """Generate batch of users using Faker and AI-generated positions."""
    users = []
    current_id = start_id

    for _ in range(count):
        max_attempts = 50
        for attempt in range(max_attempts):
            first_name = faker_instance.first_name()
            last_name = faker_instance.last_name()
            username = f"{first_name.lower()}.{last_name.lower()}"
            email = f"{username}@vertexon.com"

            if username not in seen_usernames and email not in seen_emails:
                seen_usernames.add(username)
                seen_emails.add(email)
                break

            if attempt > 20:
                suffix = faker_instance.random_int(min=1, max=999)
                username = f"{first_name.lower()}.{last_name.lower()}{suffix}"
                email = f"{username}@vertexon.com"

                if username not in seen_usernames and email not in seen_emails:
                    seen_usernames.add(username)
                    seen_emails.add(email)
                    break
        else:
            logger.warning(f"Could not generate unique username/email after {max_attempts} attempts")
            continue

        position = faker_instance.random_element(elements=positions)
        roles = "system_user system_admin" if faker_instance.random_int(min=1, max=10) == 1 else "system_user"
        joined_at = generate_joined_at_timestamp(faker_instance, position, roles)
        gender = faker_instance.random_element(elements=("male", "female"))

        user = {
            "id": current_id,
            "email": email,
            "username": username,
            "first_name": first_name,
            "last_name": last_name,
            "position": position,
            "roles": roles,
            "gender": gender,
            "joined_at": joined_at,
        }
        users.append(user)
        current_id += 1

    return users


async def generate_users(users: int):
    """Generate users and assign them to teams by reading from teams.json."""
    logger.start(f"Generating {users} users...")
    teams = load_json(TEAMS_JSON)

    if not teams:
        logger.warning("No teams found. Please generate teams first.")
        return

    logger.info(f"Loaded {len(teams)} teams")

    global_seen_usernames = set()
    global_seen_emails = set()
    faker_instance = create_faker_with_user_tracking(global_seen_usernames, global_seen_emails)

    global_seen_usernames.add(settings.MATTERMOST_OWNER_USERNAME)
    global_seen_emails.add(settings.MATTERMOST_EMAIL)

    current_timestamp = int(datetime.now().timestamp() * 1000)
    current_date = datetime.fromtimestamp(current_timestamp / 1000)
    earliest_join = current_date - timedelta(days=365 * 2.5)
    earliest_timestamp = int(earliest_join.timestamp() * 1000)
    admin_joined_at = earliest_timestamp + random.randint(0, 86400000 * 30)

    main_admin_profile = {
        "id": 1,  # Main admin gets ID 1
        "email": settings.MATTERMOST_EMAIL,
        "username": settings.MATTERMOST_OWNER_USERNAME,
        "first_name": settings.MATTERMOST_OWNER_FIRST_NAME,
        "last_name": settings.MATTERMOST_OWNER_LAST_NAME,
        "nickname": settings.MATTERMOST_OWNER_NICKNAME,
        "position": settings.MATTERMOST_OWNER_POSITION,
        "roles": "system_user system_admin",
        "gender": "male",
        "joined_at": admin_joined_at,
        "team_channels": {},
    }

    logger.info(f"Generating job positions for {users} employees...")
    ai_positions = await generate_positions(users + 10)

    faker_generated_users = []
    batch_size = BATCH_SIZE
    remaining_users = users
    next_user_id = 2

    while remaining_users > 0:
        current_batch_size = min(batch_size, remaining_users)
        try:
            batch_users = generate_user_batch(current_batch_size, faker_instance, global_seen_usernames, global_seen_emails, ai_positions, next_user_id)
            if batch_users:
                faker_generated_users.extend(batch_users)
                remaining_users -= len(batch_users)
                next_user_id += len(batch_users)
            else:
                break
        except Exception as e:
            logger.error(f"Failed to generate user batch: {e}")
            break

    all_users = []
    for user_dict in faker_generated_users:
        user_dict["nickname"] = user_dict["first_name"]
        user_dict["team_channels"] = {}
        all_users.append(user_dict)

    admin_users = [user for user in all_users if "system_admin" in user.get("roles", "")]
    logger.info(f"Generated {len(admin_users)} admin users out of {len(all_users)} total users")

    all_users.append(main_admin_profile)

    complete_users = []
    for user in all_users:
        complete_user = {
            "id": user["id"],
            "username": user["username"],
            "email": user["email"],
            "first_name": user["first_name"],
            "last_name": user["last_name"],
            "nickname": user["nickname"],
            "position": user["position"],
            "roles": user["roles"],
            "gender": user["gender"],
            "joined_at": user.get("joined_at"),
            "team_channels": {},
        }
        complete_users.append(complete_user)

    save_to_json(complete_users, USERS_JSON)
    logger.succeed(f"Generated {len(complete_users)} users")


def get_avatar_by_index(gender: str, index: int) -> str:
    """Get avatar path by index based on gender."""
    avatar_dir = Path(__file__).parent.parent.parent.parent / "common" / "avatars" / gender

    if not avatar_dir.exists():
        return ""

    avatar_files = list(avatar_dir.glob("*.jpg"))
    if not avatar_files:
        return ""

    avatar_index = index % len(avatar_files)
    return str(avatar_files[avatar_index])


async def insert_users():
    """Insert users and add them to teams."""
    teams = load_json(TEAMS_JSON)
    if not teams:
        logger.warning("No teams found. Please generate teams first.")
        return

    try:
        users = load_json(USERS_JSON)
    except (FileNotFoundError, ValueError):
        logger.warning("No users.json found.")
        users = []

    if not users:
        logger.warning("No users found. Please generate users first.")
        return

    unique_users = []
    seen_usernames = set()
    for user in users:
        username = user["username"]
        if username == settings.MATTERMOST_OWNER_USERNAME:
            continue
        if username not in seen_usernames:
            unique_users.append(user)
            seen_usernames.add(username)

    logger.start(f"Inserting {len(unique_users)} users...")

    async with MattermostClient() as client:
        try:
            created_users = {}
            for index, user in enumerate(unique_users):
                gender = user.get("gender", "male")
                avatar_path = get_avatar_by_index(gender, index)

                user_data = {
                    "username": user["username"],
                    "email": user["email"],
                    "first_name": user["first_name"],
                    "last_name": user["last_name"],
                    "nickname": user["nickname"],
                    "position": user["position"],
                    "roles": user["roles"],
                    "password": settings.MATTERMOST_PASSWORD,
                }

                if avatar_path:
                    user_data["avatar"] = avatar_path

                created_user = await client.create_user(user_data=user_data)
                if created_user and "id" in created_user:
                    created_users[user["username"]] = created_user["id"]

            logger.info(f"Created {len(created_users)} users in Mattermost")

            admin_user = await client.get_user_by_username(settings.MATTERMOST_OWNER_USERNAME)
            admin_user_id = admin_user["id"] if admin_user else None

            for team in teams:
                team_obj = await client.get_team_by_name(team["name"])
                if not team_obj:
                    continue

                if admin_user_id:
                    try:
                        await client.add_user_to_team(team_obj["id"], admin_user_id)
                    except Exception as e:
                        logger.debug(f"Admin user already in team '{team['name']}' or error: {e}")

                # Add team members to team based on simplified users structure
                team_member_count = 0
                team_name = team["name"]

                for user in users:
                    username = user["username"]
                    if username == settings.MATTERMOST_OWNER_USERNAME:
                        continue

                    user_team_channels = user.get("team_channels", {})
                    if user_team_channels.get(team_name):
                        user_id = created_users.get(username)
                        if user_id:
                            try:
                                await client.add_user_to_team(team_obj["id"], user_id)
                                team_member_count += 1
                            except Exception:
                                pass

                logger.info(f"Added {team_member_count} users to team '{team_name}'")

            logger.succeed(f"Successfully inserted {len(created_users)} users and added them to teams")
        except Exception as e:
            raise ValueError(f"Failed to insert users: {e}")


async def insert_users_to_channels():
    """Add users to their assigned channels and set admin roles where specified."""
    # Load teams data
    teams = load_json(TEAMS_JSON)

    if not teams:
        logger.warning("No teams found. Please generate teams first.")
        return

    # Load users data
    try:
        users = load_json(USERS_JSON)
    except (FileNotFoundError, ValueError):
        logger.warning("No users.json found.")
        users = []

    if not users:
        logger.warning("No users found. Please generate users first.")
        return

    logger.start("Adding users to channels...")

    async with MattermostClient() as client:
        try:
            all_mattermost_users = await client.get_users()
            created_users = {user["username"]: user["id"] for user in all_mattermost_users if user["username"] != settings.MATTERMOST_OWNER_USERNAME}

            for team in teams:
                team_obj = await client.get_team_by_name(team["name"])
                if not team_obj:
                    continue

                team_name = team["name"]
                async with MattermostClient(username=settings.MATTERMOST_OWNER_USERNAME, password=settings.MATTERMOST_PASSWORD) as admin_client:
                    channel_member_count = 0
                    system_admin_user = await admin_client.get_user_by_username(settings.MATTERMOST_OWNER_USERNAME)
                    system_admin_id = system_admin_user["id"] if system_admin_user else None

                    if system_admin_id:
                        system_admin_user_data = None
                        for user in users:
                            if user["username"] == settings.MATTERMOST_OWNER_USERNAME:
                                system_admin_user_data = user
                                break

                        for channel_data in team.get("channels", []):
                            channel_name = channel_data["name"]
                            try:
                                channel = await admin_client.get_channel_by_name(team_obj["id"], channel_name)
                                if channel:
                                    await admin_client.add_user_to_channel(channel["id"], [system_admin_id])

                                    if system_admin_user_data:
                                        admin_team_channels = system_admin_user_data.get("team_channels", {})
                                        admin_channel_info = admin_team_channels.get(team_name, {}).get(channel_name)
                                        if isinstance(admin_channel_info, dict):
                                            admin_joined_at = admin_channel_info.get("joined_at")
                                            if admin_joined_at:
                                                await update_channel_member_timestamp(channel["id"], system_admin_id, admin_joined_at)

                                    await admin_client.set_channel_member_roles(channel["id"], system_admin_id, is_admin=True)
                            except Exception:
                                pass

                    for user in users:
                        username = user["username"]
                        user_team_channels = user.get("team_channels", {})
                        user_id = system_admin_id if username == settings.MATTERMOST_OWNER_USERNAME else created_users.get(username)

                        if user_id and team_name in user_team_channels:
                            channels_with_roles = user_team_channels[team_name]
                            for channel_name, channel_info in channels_with_roles.items():
                                if isinstance(channel_info, dict):
                                    role = channel_info.get("role", "member")
                                    joined_at = channel_info.get("joined_at")
                                else:
                                    role = channel_info
                                    joined_at = None

                                try:
                                    channel = await admin_client.get_channel_by_name(team_obj["id"], channel_name)
                                    if channel:
                                        if username != settings.MATTERMOST_OWNER_USERNAME:
                                            await admin_client.add_user_to_channel(channel["id"], [user_id])
                                            if joined_at:
                                                await update_channel_member_timestamp(channel["id"], user_id, joined_at)
                                            channel_member_count += 1

                                        if role == "admin" or username == settings.MATTERMOST_OWNER_USERNAME:
                                            await admin_client.set_channel_member_roles(channel["id"], user_id, is_admin=True)
                                            if username == settings.MATTERMOST_OWNER_USERNAME and joined_at:
                                                await update_channel_member_timestamp(channel["id"], user_id, joined_at)
                                except Exception:
                                    pass

                    logger.info(f"Added {channel_member_count} channel memberships in team '{team['name']}'")

            logger.succeed("Successfully added users to their assigned channels and set admin roles")
        except Exception as e:
            raise ValueError(f"Failed to add users to channels: {e}")


def fix_undersized_channels(failed_channels: list, users: list):
    """Fix channels that don't meet minimum size requirements by adding more users."""
    for failed_channel in failed_channels:
        team_name = failed_channel["team_name"]
        channel_name = failed_channel["channel_name"]
        current_size = failed_channel["current_size"]
        required_size = failed_channel["required_size"]
        needed_users = required_size - current_size

        logger.info(f"Fixing channel '{channel_name}' in team '{team_name}': need {needed_users} more users")

        # Find users not already in this channel
        current_members = set()
        for user in users:
            user_channels = user.get("team_channels", {}).get(team_name, {})
            if channel_name in user_channels:
                current_members.add(user["id"])

        # Find available users for this team (users already in the team)
        team_users = []
        for user in users:
            if user["username"] == settings.MATTERMOST_OWNER_USERNAME:
                continue
            user_channels = user.get("team_channels", {}).get(team_name, {})
            if user_channels and user["id"] not in current_members:
                team_users.append(user)

        # Add random users to meet minimum requirement
        added_count = 0
        for user in random.sample(team_users, min(needed_users, len(team_users))):
            if user["id"] not in current_members:
                # Generate realistic timestamp
                user_joined_company = user.get("joined_at", int(datetime.now().timestamp() * 1000))
                current_timestamp = int(datetime.now().timestamp() * 1000)
                thirty_days_ago = current_timestamp - (30 * 24 * 60 * 60 * 1000)
                max_delay_ms = 365 * 24 * 60 * 60 * 1000
                latest_possible_join = min(thirty_days_ago, user_joined_company + max_delay_ms)

                if latest_possible_join > user_joined_company:
                    # Use clustered join dates for additional users too
                    cluster_size = random.choices([1, 2], weights=[0.6, 0.4])[0]  # Smaller clusters for fix-up users
                    clustered_timestamps = generate_clustered_join_dates(user_joined_company, latest_possible_join, cluster_size)
                    channel_joined_at = clustered_timestamps[0]
                else:
                    channel_joined_at = user_joined_company

                # Add user to channel
                if team_name not in user.get("team_channels", {}):
                    user["team_channels"][team_name] = {}

                user["team_channels"][team_name][channel_name] = {"role": "member", "joined_at": channel_joined_at}
                added_count += 1
                current_members.add(user["id"])

                if added_count >= needed_users:
                    break

        logger.info(f"Added {added_count} users to channel '{channel_name}' (new size: {current_size + added_count})")


async def process_single_team_assignments(team: dict, available_users: list, total_users: int, teams_count: int, users: list) -> bool:
    """Process channel assignments for a single team."""
    team_name = team["name"]
    team_channels = team.get("channels", [])

    if not team_channels:
        logger.warning(f"No channels found for team '{team_name}', skipping")
        return False

    logger.info(f"Processing team '{team_name}' with {len(team_channels)} channels...")

    base_team_size = total_users // teams_count
    expected_team_size = max(15, int(base_team_size * 1.3))
    min_team_size = max(10, int(base_team_size * 0.7))
    max_team_size = min(total_users // 2, int(base_team_size * 1.8))

    min_channel_size = max(8, expected_team_size // 6)
    max_channel_size = min(int(total_users * 0.6), 50)

    logger.info(f"Team '{team_name}': Expected {expected_team_size} users, channels should have {min_channel_size}-{max_channel_size} members each")

    try:
        batch_size = min(settings.MAX_CONCURRENT_GENERATION_REQUESTS, len(team_channels))
        for i in range(0, len(team_channels), batch_size):
            channel_batch = team_channels[i : i + batch_size]

            channels_info = []
            for channel in channel_batch:
                channels_info.append(
                    {
                        "name": channel["name"],
                        "display_name": channel["display_name"],
                        "description": channel["description"],
                        "type": channel["channel_type"],  # "O" for public, "P" for private
                    }
                )

            users_info = []
            valid_user_ids = []
            for user in available_users:
                user_info = {
                    "id": user["id"],
                    "username": user["username"],
                    "position": user["position"],
                    "roles": user["roles"],
                    "first_name": user["first_name"],
                    "last_name": user["last_name"],
                }
                users_info.append(user_info)
                valid_user_ids.append(user["id"])

            assignment_prompt = f"""
            Team: {team["display_name"]} ({team_name})
            Total available users: {total_users}
            
            TEAM SIZE CONSTRAINTS:
            - Target team size: {expected_team_size} users (preferred)
            - Minimum team size: {min_team_size} users
            - Maximum team size: {max_team_size} users
            - Teams can vary in size - some should be larger, some smaller for realism
            
            CRITICAL: Each channel should have {min_channel_size}-{max_channel_size} members.
            
            Channels to assign users to:
            {json.dumps(channels_info, indent=2)}
            
            Available users (ONLY use these exact user IDs):
            {json.dumps(users_info, indent=2)}
            
            VALID USER IDS (you MUST only use IDs from this list): {valid_user_ids}
            
            Assignment Rules:
            
            CRITICAL SUCCESS CRITERIA: Every single channel must have at least {min_channel_size} members!
            
            1. **TEAM SIZE TARGETS**:
               - Aim for {min_team_size}-{max_team_size} total users in this team
               - Prefer around {expected_team_size} users for this team
               - Some teams should be larger/smaller than others for realism
               - Consider team purpose when deciding size (Engineering teams can be larger, specialized teams smaller)
            
            2. **MANDATORY CHANNEL CONSTRAINTS** (CRITICAL - MUST BE FOLLOWED):
               - Each channel MUST have EXACTLY between {min_channel_size} and {max_channel_size} members
               - NO EXCEPTIONS: Every channel needs at least {min_channel_size} users assigned
               - Default channels (town-square, off-topic) MUST have {max(min_channel_size * 2, int(expected_team_size * 0.6))} or more members
               - If you cannot assign enough users to meet minimums, assign more users to reach the minimum
               - Better to over-assign than under-assign - active channels are better than empty ones
            
            2. **Role-based assignments**:
               - Developers/Engineers → engineering, tech, development, code channels
               - Accountants/Finance → finance, budget, accounting, financial channels  
               - HR/People → hr, people, culture, employee channels
               - Marketing → marketing, social, content, brand channels
               - Sales → sales, revenue, customer, business channels
               - Support → support, help, customer service, escalation channels
               - Product → product, roadmap, feature, planning channels
               - Operations → operations, process, workflow, logistics channels
            
            4. **Seniority-based access**:
               - Senior positions (Senior, Lead, Principal) → relevant channels + some cross-functional
               - Managers/Directors → department channels as admin + cross-functional as member
               - C-Suite (CEO, CTO, CFO, etc.) → strategic channels as admin + oversight access
               - VPs/Heads → broad departmental access as admin
            
            5. **Cross-functional collaboration**:
               - Include non-department members in relevant channels (PMs in engineering channels, engineers in product channels)
               - Leadership should have access to multiple departments
               - Support and operations staff often participate across teams
               - Company-wide channels (announcements, culture) should include most employees
            
            6. **Channel type considerations**:
               - Private channels ("P") → smaller groups, key stakeholders only (10-30% of users)
               - Public channels ("O") → larger groups, broader access (20-80% of users)
            
            7. **ID VALIDATION**:
               - ONLY use user IDs from the valid list: {valid_user_ids}
               - Do NOT invent or hallucinate user IDs
               - If unsure about a user ID, do NOT include it
            
            8. **Role assignment**:
               - "admin": Managers, Directors, C-Suite, Team Leads in relevant channels
               - "member": Regular team members, cross-functional participants
            
            Return assignments that create realistic, well-distributed teams with proper channel sizes.
            """

            response = await instructor_client.chat.completions.create(
                model=settings.DEFAULT_MODEL,
                messages=[
                    {"role": "system", "content": get_system_prompt()},
                    {"role": "user", "content": assignment_prompt},
                ],
                response_model=ChannelAssignmentResponse,
                temperature=0.3,  # Lower temperature for more consistent assignments
                max_tokens=settings.MAX_OUTPUT_TOKENS,
            )

            if response and response.channel_assignments:
                # Apply the AI assignments to users
                for assignment in response.channel_assignments:
                    channel_name = assignment.channel_name

                    # Find the channel in our data
                    channel_found = False
                    for channel in channel_batch:
                        if channel["name"] == channel_name:
                            channel_found = True
                            break

                    if not channel_found:
                        logger.warning(f"AI assigned users to unknown channel '{channel_name}', skipping")
                        continue

                    # Validate and apply assignments to users
                    valid_assignments = 0

                    for member in assignment.members:
                        # STRICT ID validation - only accept IDs from our valid list
                        if member.user_id not in valid_user_ids:
                            logger.warning(f"AI hallucinated invalid user ID {member.user_id} for channel '{channel_name}', skipping")
                            continue

                        # Find user by ID
                        user_found = None
                        for user in users:
                            if user["id"] == member.user_id:
                                user_found = user
                                break

                        if not user_found:
                            logger.warning(f"AI assigned unknown user ID {member.user_id} to channel '{channel_name}', skipping")
                            continue

                        # Initialize team_channels if not exists
                        if "team_channels" not in user_found:
                            user_found["team_channels"] = {}

                        # Initialize team if not exists
                        if team_name not in user_found["team_channels"]:
                            user_found["team_channels"][team_name] = {}

                        # Find channel creation date
                        channel_created_at = None
                        for channel_data in team.get("channels", []):
                            if channel_data["name"] == channel_name:
                                channel_created_at = channel_data.get("created_at")
                                break

                        # Generate realistic joined_at timestamp for this channel
                        user_joined_company = user_found.get("joined_at", int(datetime.now().timestamp() * 1000))

                        # Channel join date should be after both user joined company AND channel was created
                        earliest_join = max(user_joined_company, channel_created_at) if channel_created_at else user_joined_company

                        # Add realistic delay with bias toward earlier dates (0-365 days, biased toward earlier)
                        current_timestamp = int(datetime.now().timestamp() * 1000)
                        max_delay_days = 365  # Extend to 1 year
                        max_delay_ms = max_delay_days * 24 * 60 * 60 * 1000

                        # Ensure we don't go beyond 30 days ago to avoid too many recent joins
                        thirty_days_ago = current_timestamp - (30 * 24 * 60 * 60 * 1000)
                        latest_possible_join = min(thirty_days_ago, earliest_join + max_delay_ms)

                        # Use clustered join dates - create a small cluster of 1-3 users joining together
                        if latest_possible_join > earliest_join:
                            # Generate clustered join dates for this user (treating as single-user cluster)
                            # This creates temporal clustering by using the same logic as multi-user clusters
                            cluster_size = random.choices([1, 2, 3], weights=[0.4, 0.4, 0.2])[0]  # Mostly 1-2 users per cluster
                            clustered_timestamps = generate_clustered_join_dates(earliest_join, latest_possible_join, cluster_size)
                            channel_joined_at = clustered_timestamps[0]  # Use first timestamp from cluster
                        else:
                            channel_joined_at = earliest_join

                        # Assign user to channel with role and joined_at
                        user_found["team_channels"][team_name][channel_name] = {"role": member.role, "joined_at": channel_joined_at}
                        valid_assignments += 1

                    # Log assignment results with validation stats
                    total_attempted = len(assignment.members)
                    logger.info(f"Channel '{channel_name}': {valid_assignments}/{total_attempted} valid assignments")

                    # Error on channels that don't meet minimum requirements
                    if valid_assignments < min_channel_size:
                        logger.error(f"Channel '{channel_name}' has only {valid_assignments} members (minimum required: {min_channel_size}) - AI failed to meet constraints!")
                        # Store failed channels for post-processing fix
                        if not hasattr(process_single_team_assignments, "_failed_channels"):
                            process_single_team_assignments._failed_channels = []
                        process_single_team_assignments._failed_channels.append(
                            {"team_name": team_name, "channel_name": channel_name, "current_size": valid_assignments, "required_size": min_channel_size, "available_users": valid_user_ids}
                        )
                    elif valid_assignments > max_channel_size:
                        logger.warning(f"Channel '{channel_name}' has {valid_assignments} members (maximum: {max_channel_size}) - slightly over capacity")

            else:
                logger.warning(f"No channel assignments returned by AI for team '{team_name}' batch {i // batch_size + 1}")

        return True

    except Exception as e:
        logger.error(f"Failed to get AI channel assignments for team '{team_name}': {e}")
        return False


async def pick_users_for_channels():
    logger.start("Assigning users to channels...")

    teams = load_json(TEAMS_JSON)
    if not teams:
        logger.warning("No teams found.")
        return

    try:
        users = load_json(USERS_JSON)
    except (FileNotFoundError, ValueError):
        logger.warning("No users.json found.")
        users = []

    if not users:
        logger.warning("No users found.")
        return

    available_users = [u for u in users if u["username"] != settings.MATTERMOST_OWNER_USERNAME]
    total_users = len(available_users)
    teams_count = len(teams)

    max_concurrent_teams = min(settings.MAX_CONCURRENT_GENERATION_REQUESTS, len(teams))
    semaphore = asyncio.Semaphore(max_concurrent_teams)

    async def process_team_with_semaphore(team):
        async with semaphore:
            return await process_single_team_assignments(team, available_users, total_users, teams_count, users)

    results = await asyncio.gather(*[process_team_with_semaphore(team) for team in teams], return_exceptions=True)

    successful_teams = 0
    failed_teams = 0
    for i, result in enumerate(results):
        if isinstance(result, Exception):
            logger.error(f"Team '{teams[i]['name']}' processing failed: {result}")
            failed_teams += 1
        elif result:
            successful_teams += 1
        else:
            failed_teams += 1

    logger.info(f"Processing completed: {successful_teams} successful, {failed_teams} failed")

    # Fix undersized channels with post-processing
    if hasattr(process_single_team_assignments, "_failed_channels"):
        failed_channels = process_single_team_assignments._failed_channels
        if failed_channels:
            logger.info(f"Fixing {len(failed_channels)} undersized channels...")
            fix_undersized_channels(failed_channels, users)
            # Clear the failed channels list
            delattr(process_single_team_assignments, "_failed_channels")

    main_admin = None
    for user in users:
        if user["username"] == settings.MATTERMOST_OWNER_USERNAME:
            main_admin = user
            break

    if main_admin:
        if "team_channels" not in main_admin:
            main_admin["team_channels"] = {}

        for team in teams:
            team_name = team["name"]
            if team_name not in main_admin["team_channels"]:
                main_admin["team_channels"][team_name] = {}

            for channel_data in team.get("channels", []):
                channel_name = channel_data["name"]
                channel_created_at = channel_data.get("created_at")
                admin_joined_company = main_admin.get("joined_at", int(datetime.now().timestamp() * 1000))

                earliest_join = max(admin_joined_company, channel_created_at) if channel_created_at else admin_joined_company
                max_delay_ms = 60 * 24 * 60 * 60 * 1000
                current_timestamp = int(datetime.now().timestamp() * 1000)
                thirty_days_ago = current_timestamp - (30 * 24 * 60 * 60 * 1000)
                latest_possible_join = min(thirty_days_ago, earliest_join + max_delay_ms)

                if latest_possible_join > earliest_join:
                    time_range = latest_possible_join - earliest_join
                    random_factor = random.random() ** 1.5
                    admin_channel_joined_at = earliest_join + int(time_range * random_factor)
                else:
                    admin_channel_joined_at = earliest_join

                main_admin["team_channels"][team_name][channel_name] = {"role": "admin", "joined_at": admin_channel_joined_at}

    # Ensure all users have town-square and off-topic for every team they're in
    logger.info("Ensuring all users have default channels (town-square, off-topic)...")
    default_channels = ["town-square", "off-topic"]

    for user in users:
        user_team_channels = user.get("team_channels", {})
        for team_name, assigned_channels in user_team_channels.items():
            # Find the team to get channel creation dates
            team_data = None
            for team in teams:
                if team["name"] == team_name:
                    team_data = team
                    break

            if not team_data:
                continue

            # Ensure user has both default channels
            for default_channel in default_channels:
                if default_channel not in assigned_channels:
                    # Find channel creation date
                    channel_created_at = None
                    for channel_data in team_data.get("channels", []):
                        if channel_data["name"] == default_channel:
                            channel_created_at = channel_data.get("created_at")
                            break

                    if channel_created_at:
                        # Generate realistic joined_at timestamp
                        user_joined_company = user.get("joined_at", int(datetime.now().timestamp() * 1000))
                        earliest_join = max(user_joined_company, channel_created_at)

                        current_timestamp = int(datetime.now().timestamp() * 1000)
                        thirty_days_ago = current_timestamp - (30 * 24 * 60 * 60 * 1000)
                        max_delay_ms = 365 * 24 * 60 * 60 * 1000
                        latest_possible_join = min(thirty_days_ago, earliest_join + max_delay_ms)

                        if latest_possible_join > earliest_join:
                            # Use clustered join dates for default channels too
                            cluster_size = random.choices([1, 2, 3], weights=[0.3, 0.5, 0.2])[0]  # Slightly larger clusters for default channels
                            clustered_timestamps = generate_clustered_join_dates(earliest_join, latest_possible_join, cluster_size)
                            channel_joined_at = clustered_timestamps[0]  # Use first timestamp from cluster
                        else:
                            channel_joined_at = earliest_join

                        # Add default channel assignment
                        assigned_channels[default_channel] = {"role": "member", "joined_at": channel_joined_at}

    save_to_json(users, USERS_JSON)

    total_assignments = 0
    users_with_assignments = 0
    for user in users:
        user_assignments = 0
        for _, channels in user.get("team_channels", {}).items():
            user_assignments += len(channels)
            total_assignments += len(channels)
        if user_assignments > 0:
            users_with_assignments += 1

    logger.succeed("Channel assignment completed!")
