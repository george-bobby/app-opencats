import json
from pathlib import Path

from apps.teable.config.constants import BASES_FILE
from apps.teable.config.settings import settings
from apps.teable.utils.teable import get_teable_client
from common.logger import Logger


logger = Logger()


async def insert_bases():
    with Path.open(settings.DATA_PATH.joinpath(BASES_FILE)) as f:
        bases = json.load(f)

    teable = await get_teable_client()
    spaces = await teable.get_spaces()
    for space in spaces:
        space_id = space["id"]
        space_name = space["name"]

        for base in bases:
            if base["parent_workspace_name"] != space_name:
                continue

            try:
                await teable.create_base(space_id, base["name"])
                logger.succeed(f"Created base: {base['name']}")
            except Exception as e:
                logger.error(f"Failed to create base: {base['name']}: {e}")


async def get_base_id_by_name(space_name, base_name, teable_client=None):
    if teable_client is None:
        teable_client = await get_teable_client()
    spaces = await teable_client.get_spaces()
    for space in spaces:
        if space["name"] == space_name:
            space_id = space["id"]
            bases = await teable_client.get_bases(space_id)
            for base in bases:
                if base["name"] == base_name:
                    return base["id"]
    return None
