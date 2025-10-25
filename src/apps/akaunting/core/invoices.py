from datetime import timedelta

from pydantic import BaseModel, Field

from apps.akaunting.models.documents import DocumentItem
from apps.akaunting.utils import api, faker
from common.logger import logger


class InvoiceItem(BaseModel):
    item_id: int
    quantity: int


class InvoiceKeyInfo(BaseModel):
    items: list[InvoiceItem] = Field(..., description="The items in this invoice")
    category_id: int = Field(..., description="Category id for this invoice")
    # notes: float = Field(
    #     ..., description="Invoice notes for the customer"
    # )


class ListInvoiceKeyInfo(BaseModel):
    invoices: list[InvoiceKeyInfo]


async def generate_invoices(number: int = 5):
    existing_items = [
        {
            "id": item.id,
            "name": item.name,
            "type": item.type,
            "sale_price": item.sale_price,
        }
        for item in await api.list_items()
    ]

    existing_categories = [
        {
            "id": category.id,
            "name": category.name,
            "type": category.type,
        }
        for category in await api.list_categories("income")
    ]

    invoices = []
    for _ in range(number):
        # Randomly select 1-4 items for this invoice
        num_items = faker.random_int(min=1, max=4)
        selected_items = faker.random.sample(existing_items, k=min(num_items, len(existing_items)))

        invoice_items = [InvoiceItem(item_id=item["id"], quantity=faker.random_int(min=1, max=10)) for item in selected_items]

        # Randomly select a category
        category = faker.random.choice(existing_categories)

        invoice = InvoiceKeyInfo(items=invoice_items, category_id=category["id"])
        invoices.append(invoice)

    return invoices


async def create_generated_invoices(number: int = 5):
    try:
        invoices = await generate_invoices(number)
        contacts = await api.list_contacts("customer")
        accounts = await api.list_accounts()
        items = await api.list_items()

        if not contacts or not accounts:
            raise Exception("No contacts or accounts found")

        for invoice in invoices:
            logger.info(invoice)
            contact = faker.random_element(contacts)
            account = faker.random_element(accounts)

            # Generate issued_at date within last 3 years
            issued_date = faker.date_time_between(start_date="-2y", end_date="now")
            # Generate due_date between issued_date and 30 days after issued_date
            due_date = faker.date_between(start_date=issued_date, end_date=issued_date + timedelta(days=90))
            paid_at = faker.date_between(start_date=issued_date, end_date=issued_date)
            status = "draft" if faker.random.random() < 0.2 else "sent"  # most invoices are sent

            # Process all items in the invoice
            document_items = []
            for invoice_item in invoice.items:
                current_item = next((item for item in items if item.id == invoice_item.item_id), None)
                if not current_item:
                    logger.warning(f"Item with id {invoice_item.item_id} not found")
                    continue

                # Extract tax_ids from the item's taxes
                tax_ids = [tax_relation.tax_id for tax_relation in current_item.taxes.data]

                # Calculate the subtotal without taxes
                subtotal = current_item.sale_price * invoice_item.quantity

                document_items.append(
                    DocumentItem(
                        item_id=invoice_item.item_id,
                        quantity=invoice_item.quantity,
                        tax_ids=tax_ids,
                        name=current_item.name,
                        price=current_item.sale_price,
                        total=subtotal,  # Use subtotal instead of potentially double-counting
                    )
                )

            added_invoice = await api.add_document(
                category_id=str(invoice.category_id),
                document_number=faker.unique.random_number(digits=8),
                status=status,
                issued_at=issued_date.strftime("%Y-%m-%d"),
                due_at=due_date.strftime("%Y-%m-%d"),
                account_id=str(account.id),
                currency_code="USD",
                currency_rate=1.0,
                contact_id=str(contact.id),
                contact_name=contact.name,
                contact_email=contact.email,
                contact_address=contact.address or "",
                items=document_items,
                amount=0,  # Hasn't got paid yet
                document_type="invoice",
            )
            added_invoice_data = added_invoice.data
            amount = added_invoice_data.amount

            # Randomly determine paid status based on probabilities
            # 60% paid, 30% unpaid, 10% partial
            rand_val = faker.random.random()
            if rand_val < 0.8:  # 80% chance
                # paid_status = "paid"
                amount = added_invoice_data.amount  # Full amount
            elif rand_val < 0.9:  # 10% chance (0.6 to 0.9)
                # paid_status = "unpaid"
                amount = 0  # No payment
            else:  # 10% chance
                # paid_status = "partial"
                # Pay between 25% to 75% of the total amount
                amount = added_invoice_data.amount * faker.random.uniform(0.25, 0.75)

            # Create the document transaction
            if amount > 0:
                await api.add_document_transaction(
                    number=faker.unique.random_number(digits=8),
                    document_id=str(added_invoice_data.id),
                    category_id=str(invoice.category_id),
                    account_id=str(account.id),
                    paid_at=paid_at.strftime("%Y-%m-%d"),
                    amount=amount,
                    currency_code="USD",
                    currency_rate=1.0,
                    description=f"Invoice #{added_invoice_data.id}",
                    type="income",
                )

    finally:
        await api.close()


async def delete_generated_invoices():
    try:
        invoices = await api.list_documents(document_type="invoice")

        for invoice in invoices:
            logger.info(invoice)
            if invoice.created_from == "core::api":
                try:
                    await api.delete_document(str(invoice.id))
                except Exception as e:
                    logger.warning(e)

    finally:
        await api.close()
