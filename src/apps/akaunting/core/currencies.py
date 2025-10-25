import json
from pathlib import Path

from apps.akaunting.utils import api
from common.logger import logger


currencies_file = Path(__file__).parent.joinpath("data/currencies.json")


async def import_currencies():
    """Import currencies from currencies.json file into Akaunting"""

    try:
        # Read the currencies from JSON file
        with currencies_file.open() as f:
            currencies = json.load(f)

        # Import each currency
        for currency in currencies:
            logger.info(currency)
            try:
                await api.add_currency(
                    name=currency["name"],
                    code=currency["code"],
                    rate=currency["rate"],
                    precision=currency["precision"],
                    symbol=currency["symbol"],
                    symbol_first=currency["symbol_first"],
                    decimal_mark=currency["decimal_mark"],
                    thousands_separator=currency["thousands_separator"],
                    enabled=currency["enabled"],
                )
            except Exception as e:
                logger.warning(e)

    except Exception as e:
        logger.error(e)


async def delete_generated_currencies():
    try:
        currencies = await api.list_currencies()

        for currency in currencies:
            logger.info(currency)
            if currency.created_from == "core::api":
                try:
                    await api.delete_currency(str(currency.id))
                except Exception as e:
                    logger.warning(e)

    finally:
        await api.close()
