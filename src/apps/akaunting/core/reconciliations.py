from datetime import UTC, datetime, timedelta

from apps.akaunting.utils import api, faker
from common.logger import logger


async def create_generated_reconciliations(number: int = 5):
    """
    Generate and create reconciliations in the system based on existing accounts.
    Only creates reconciliations when there are transactions in the date range.
    """
    try:
        accounts = await api.list_accounts()
        if not accounts:
            raise Exception("No accounts found")

        for _ in range(number):
            account = faker.random_element(accounts)
            logger.info(f"Processing account: {account.id} ({account.name})")

            # Generate a random date within last 2 years for start date
            started_at = faker.date_time_between(start_date="-2y", end_date="now")

            ended_at = faker.date_between(start_date=started_at, end_date=datetime.now() + timedelta(days=90))

            logger.info(f"Date range: {started_at.strftime('%Y-%m-%d')} to {ended_at.strftime('%Y-%m-%d')}")

            # Get all transactions in the date range
            start_date = datetime.strptime(started_at.strftime("%Y-%m-%d"), "%Y-%m-%d")
            end_date = datetime.strptime(ended_at.strftime("%Y-%m-%d"), "%Y-%m-%d")

            # Check for invoices
            invoices = await api.list_documents(document_type="invoice")
            has_invoices = any(
                doc.status == "paid"
                and start_date <= datetime.fromisoformat(doc.issued_at.replace("Z", "+00:00")).astimezone(UTC).replace(tzinfo=None, hour=0, minute=0, second=0, microsecond=0) <= end_date
                for doc in invoices
            )

            # Check for bills
            bills = await api.list_documents(document_type="bill")
            has_bills = any(
                doc.status == "paid"
                and start_date <= datetime.fromisoformat(doc.issued_at.replace("Z", "+00:00")).astimezone(UTC).replace(tzinfo=None, hour=0, minute=0, second=0, microsecond=0) <= end_date
                for doc in bills
            )

            # Check for transfers
            transfers = await api.list_transfers()
            has_transfers = any(
                (transfer.from_account_id == account.id or transfer.to_account_id == account.id)
                and start_date <= transfer.paid_at.astimezone(UTC).replace(tzinfo=None, hour=0, minute=0, second=0, microsecond=0) <= end_date
                for transfer in transfers
            )

            # Only create reconciliation if there are transactions
            if has_invoices or has_bills or has_transfers:
                # Use current balance for reconciliation
                closing_balance = float(account.current_balance)
                logger.info(f"Found transactions in date range, using current balance: {closing_balance}")

                reconciliation = {
                    "account_id": str(account.id),
                    "started_at": started_at.strftime("%Y-%m-%d"),
                    "ended_at": ended_at.strftime("%Y-%m-%d"),
                    "closing_balance": round(closing_balance, 2),
                }

                logger.info(f"Creating reconciliation: {reconciliation}")
                try:
                    await api.add_reconciliation(
                        account_id=reconciliation["account_id"],
                        started_at=reconciliation["started_at"],
                        ended_at=reconciliation["ended_at"],
                        closing_balance=reconciliation["closing_balance"],
                        reconciled=True,
                    )
                    logger.info("Successfully created reconciliation")
                except Exception as e:
                    logger.warning(f"Failed to create reconciliation: {e}")
            else:
                logger.info("No transactions found in date range, skipping reconciliation")

    finally:
        await api.close()


async def delete_generated_reconciliations():
    """
    Delete all reconciliations from the system.
    """
    try:
        reconciliations = await api.list_reconciliations()

        for reconciliation in reconciliations:
            logger.info(reconciliation)
            try:
                await api.delete_reconciliation(str(reconciliation.id))
            except Exception as e:
                logger.warning(f"Failed to delete reconciliation {reconciliation.id}: {e}")

    finally:
        await api.close()
