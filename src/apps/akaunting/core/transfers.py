import json

from pydantic import BaseModel, Field

from apps.akaunting.config.settings import settings
from apps.akaunting.utils import api, faker
from apps.akaunting.utils.ai import aopenai
from common.logger import logger


class TransferKeyInfo(BaseModel):
    from_account_id: str = Field(..., description="Source account ID for the transfer")
    to_account_id: str = Field(..., description="Destination account ID for the transfer")
    amount: float = Field(..., description="Amount to transfer")
    description: str | None = Field(None, description="Optional description for the transfer")


class ListTransferKeyInfo(BaseModel):
    transfers: list[TransferKeyInfo]


async def generate_transfers(number: int = 5):
    existing_accounts = [
        {
            "id": account.id,
            "name": account.name,
            "type": account.type,
            "currency_code": account.currency_code,
            "current_balance": account.current_balance,
        }
        for account in await api.list_accounts()
    ]

    completion = await aopenai.beta.chat.completions.parse(
        model="gpt-4o-mini",
        messages=[
            {
                "role": "system",
                "content": "Generate JSON data for an accounting software",
            },
            {
                "role": "user",
                "content": f"""
                    Create {number} transfers between accounts for {settings.DATA_THEME_SUBJECT}.
                    Try to create data that is realistic and makes sense for the business context.
                    Here are the existing accounts:    
                    ```json
                    {json.dumps(existing_accounts)}
                    ```
                """,
            },
        ],
        response_format=ListTransferKeyInfo,
    )
    response = completion.choices[0].message.parsed
    if not response:
        raise Exception("Invalid GPT response")
    return response.transfers


async def create_generated_transfers(number: int = 5):
    try:
        transfers = await generate_transfers(number)

        for transfer in transfers:
            logger.info(transfer)

            transfer_date = faker.date_time_between(start_date="-1y", end_date="now")

            # Get account details to handle currency information
            accounts = await api.list_accounts()
            from_account = next((acc for acc in accounts if str(acc.id) == transfer.from_account_id), None)
            to_account = next((acc for acc in accounts if str(acc.id) == transfer.to_account_id), None)

            if not from_account or not to_account:
                logger.warning(f"Could not find accounts for transfer: {transfer}")
                continue

            # Create the transfer with proper currency handling
            try:
                await api.add_transfer(
                    from_account_id=transfer.from_account_id,
                    to_account_id=transfer.to_account_id,
                    amount=transfer.amount,
                    transferred_at=transfer_date.strftime("%Y-%m-%d"),
                    from_currency_code=from_account.currency_code,
                    to_currency_code=to_account.currency_code,
                    currency_code=from_account.currency_code,  # Use source account's currency as base
                    reference=transfer.description,
                    payment_method="offline-payments.bank_transfer.2",
                )
            except Exception as e:
                logger.error(f"Failed to create transfer: {e}")
                continue

    finally:
        await api.close()


async def delete_generated_transfers():
    try:
        transfers = await api.list_transfers()

        for transfer in transfers:
            logger.info(transfer)
            if transfer.created_from == "core::api":
                try:
                    await api.delete_transfer(str(transfer.id))
                except Exception as e:
                    logger.warning(e)

    finally:
        await api.close()
