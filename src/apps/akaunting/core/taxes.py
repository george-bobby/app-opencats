import json
from pathlib import Path

from apps.akaunting.utils import api
from common.logger import logger


taxes_file = Path(__file__).parent.joinpath("data/taxes.json")


async def import_taxes():
    """Import taxes from taxes.json file into Akaunting"""

    try:
        # Read the taxes from JSON file
        with taxes_file.open() as f:
            taxes = json.load(f)

        # Import each tax
        for tax in taxes:
            await api.add_tax(name=tax["name"], rate=tax["rate"])

        return True

    except Exception as e:
        print(f"Error importing taxes: {e!s}")
        return False


async def delete_generated_taxes():
    try:
        items = await api.list_taxes()

        for item in items:
            logger.info(item)
            if item.created_from == "core::api":
                try:
                    await api.delete_tax(str(item.id))
                except Exception as e:
                    logger.warning(e)

    finally:
        await api.close()
