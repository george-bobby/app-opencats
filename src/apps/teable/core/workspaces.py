import json
from pathlib import Path

from apps.teable.config.constants import WORKSPACE_ASSIGNMENTS_FILE, WORKSPACES_FILE
from apps.teable.config.settings import settings
from apps.teable.utils.faker import faker
from apps.teable.utils.teable import get_teable_client
from common.logger import Logger


logger = Logger()


async def insert_workspaces():
    # Read workspaces from JSON file
    json_path = settings.DATA_PATH.joinpath(WORKSPACES_FILE)
    with Path.open(json_path) as f:
        workspaces = json.load(f)

    teable = await get_teable_client()
    for workspace in workspaces:
        await teable.create("space", workspace)
        logger.succeed(f"Created workspace: {workspace['name']}")


async def delete_all_workspace():
    teable = await get_teable_client()
    spaces = await teable.get_spaces()
    for space in spaces:
        try:
            await teable.delete("space", space["id"])
            logger.succeed(f"Deleted space: {space['name']}")
        except Exception as e:
            logger.error(f"Error deleting space: {space['name']} - {e}")


async def get_workspace_domain():
    return settings.TEABLE_ADMIN_EMAIL.split("@")[1]


async def generate_workspace_assignments(number_of_users_per_workspace: int):
    workspace_assignments = []
    domain = await get_workspace_domain()

    async with await get_teable_client() as teable:
        spaces = await teable.get_spaces()
        for space in spaces:
            users = []

            # Calculate role distribution
            # 1 owner (always)
            num_owners = faker.random_int(min=1, max=2)
            # 20% editors (but at least 1 if we have enough users)
            num_editors = max(1, int(number_of_users_per_workspace * 0.2)) if number_of_users_per_workspace > 5 else 0
            # 30% commenters
            num_commenters = int(number_of_users_per_workspace * 0.3)
            # Remaining are viewers
            num_viewers = number_of_users_per_workspace - num_owners - num_editors - num_commenters

            # Generate users for each role
            roles_and_counts = [
                ("owner", num_owners),
                ("editor", num_editors),
                ("commenter", num_commenters),
                ("viewer", num_viewers),
            ]

            for role, count in roles_and_counts:
                for _ in range(count):
                    first_name = faker.first_name()
                    last_name = faker.last_name()
                    email_safe_first_name = "".join([c for c in first_name if c.isalnum()]).lower()
                    email_safe_last_name = "".join([c for c in last_name if c.isalnum()]).lower()
                    email = f"{email_safe_first_name}.{email_safe_last_name}@{domain}"
                    users.append({"email": email, "role": role})

            workspace_assignments.append({"space_name": space["name"], "users": users})
    with Path.open(settings.DATA_PATH.joinpath(WORKSPACE_ASSIGNMENTS_FILE), "w") as f:
        json.dump(workspace_assignments, f)


async def insert_workspace_assignments():
    # Read workspace assignments from JSON file
    with Path.open(settings.DATA_PATH.joinpath(WORKSPACE_ASSIGNMENTS_FILE)) as f:
        workspace_assignments = json.load(f)

    teable = await get_teable_client()
    # Get all spaces to map space names to space IDs
    spaces = await teable.get_spaces()
    space_name_to_id = {space["name"]: space["id"] for space in spaces}

    for assignment in workspace_assignments:
        space_name = assignment["space_name"]
        space_id = space_name_to_id.get(space_name)

        if not space_id:
            logger.warning(f"Space '{space_name}' not found, skipping...")
            continue

        # Insert users for this workspace
        for user in assignment["users"]:
            email = user["email"]
            role = user["role"]

            try:
                # Invite user to the space with the specified role
                await teable.assign_user_to_space(space_id, [email], role)
            except Exception as e:
                logger.error(f"Failed to invite {email} to '{space_name}': {e}")

        logger.succeed(f"Invited {len(assignment['users'])} users to '{space_name}'")
