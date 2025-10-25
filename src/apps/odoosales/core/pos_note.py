from apps.odoosales.config.settings import settings
from apps.odoosales.utils.odoo import OdooClient
from common.load_json import load_json
from common.logger import logger


async def insert_pos_notes():
    notes = load_json(settings.DATA_PATH.joinpath("pos_notes.json"))

    note_records = []
    for note in notes:
        note_records.append({"name": note["name"]})

    logger.start(f"Inserting {len(notes)} notes...")
    async with OdooClient() as client:
        try:
            await client.create("pos.note", [note_records])
            logger.succeed(f"Inserted {len(notes)} pos notes successfully.")
        except Exception as e:
            raise ValueError(f"Failed to insert notes: {e}")
