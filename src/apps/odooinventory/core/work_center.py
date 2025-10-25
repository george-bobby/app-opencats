import random

from apps.odooinventory.config.constants import MrpModelName
from apps.odooinventory.config.settings import settings
from apps.odooinventory.utils.odoo import OdooClient
from common.load_json import load_json
from common.logger import logger


FIFTEEN_MINUTES = 15
THIRTY_MINUTES = 30


async def insert_work_centers():
    work_centers = load_json(settings.DATA_PATH.joinpath("work_centers.json"))

    data = []

    # async with OdooClient() as client:
    #     expense_accounts = await client.search_read(
    #         model="account.account",
    #         domain=[],
    #         fields=["id", "name"],
    #     )

    for wc_data in work_centers:
        wc_data["time_start"] = random.randint(15, 30)
        wc_data["time_stop"] = random.randint(15, 30)
        # wc_data["expense_account_id"] = random.choice(expense_accounts)["id"]

        data.append(wc_data)

    async with OdooClient() as client:
        try:
            await client.create(MrpModelName.MRP_WORK_CENTER.value, [data])
            logger.succeed("Work centers inserted successfully")
        except Exception as e:
            logger.fail(f"Failed to insert work centers: {e}")
