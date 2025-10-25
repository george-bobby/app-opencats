from apps.odoosales.config.settings import settings
from apps.odoosales.models.note import Note, NoteResponse
from apps.odoosales.utils.openai import get_system_prompt, openai
from common.logger import logger
from common.save_to_json import save_to_json


FILENAME_TO_SAVE = "notes.json"


async def generate_notes(count: int | None = None):
    if count is None:
        return

    logger.start(f"Generating {count} notes...")

    user_prompt = f"""
        Generate {count} realistic notes for a US-based SME using an Odoo Sales system.
    """
    response = await openai.responses.parse(
        model=settings.DEFAULT_MODEL,
        input=[
            {"role": "system", "content": get_system_prompt()},
            {"role": "user", "content": user_prompt},
        ],
        text_format=NoteResponse,
        temperature=0.7,
    )

    if not response.output_parsed:
        logger.warning("No notes generated. Please generate again.")
        return

    notes: list[Note] = response.output_parsed.notes

    if not notes:
        logger.warning("No notes generated. Please generate again.")
        return

    save_to_json([note.model_dump() for note in notes], settings.DATA_PATH.joinpath(FILENAME_TO_SAVE))

    logger.succeed(f"Generated {len(notes)} notes")
