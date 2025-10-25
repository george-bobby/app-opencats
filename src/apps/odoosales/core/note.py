from apps.odoosales.config.constants import POSModelName
from apps.odoosales.config.settings import settings
from apps.odoosales.utils.odoo import OdooClient
from common.load_json import load_json
from common.logger import logger


async def insert_notes():
    notes = load_json(settings.DATA_PATH.joinpath("notes.json"))

    logger.start(f"Inserting {len(notes)} notes...")
    async with OdooClient() as client:
        try:
            await client.create(POSModelName.POS_NOTE.value, [notes])
            logger.succeed(f"Inserted {len(notes)} notes successfully.")
        except Exception as e:
            raise ValueError(f"Error inserting notes: {e}") from e
