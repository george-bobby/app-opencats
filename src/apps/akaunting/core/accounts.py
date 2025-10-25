import json
import time
from pathlib import Path

from apps.akaunting.utils import api
from common.logger import logger


accounts_file = Path(__file__).parent.joinpath("data/accounts.json")


async def import_payment_accounts():
    """Import accounts from accounts.json file into Akaunting"""

    try:
        # Read the accounts from JSON file
        with accounts_file.open() as f:
            accounts = json.load(f)

        # Import each account
        for account in accounts:
            logger.info(account)
            try:
                await api.add_account(
                    name=account["name"],
                    number=account["number"],
                    currency_code=account["currency_code"],
                    opening_balance=account["opening_balance"],
                    bank_name=account["bank_name"],
                    bank_phone=account["bank_phone"],
                    bank_address=account["bank_address"],
                    enabled=account["enabled"],
                    type=account["type"],
                )
                time.sleep(3)
            except Exception as e:
                logger.warning(f"Error adding account: {e}")

    except Exception as e:
        logger.error(f"Error importing accounts: {e}")


async def delete_generated_payment_accounts():
    try:
        accounts = await api.list_accounts()

        for account in accounts:
            logger.info(account)
            if account.created_from == "core::api":
                try:
                    await api.delete_account(str(account.id))
                except Exception as e:
                    logger.warning(e)

    finally:
        await api.close()
