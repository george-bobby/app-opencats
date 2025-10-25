from typing import Literal

import aiohttp

from apps.akaunting.config.settings import settings
from apps.akaunting.models.accounts import Account, AccountsResponse, SingleAccountResponse
from apps.akaunting.models.categories import (
    CategoriesResponse,
    Category,
    CategoryType,
    SingleCategoryResponse,
)
from apps.akaunting.models.contacts import (
    Contact,
    ContactsResponse,
    ContactType,
    SingleContactResponse,
)
from apps.akaunting.models.currencies import CurrenciesResponse, Currency
from apps.akaunting.models.documents import (
    Document,
    DocumentItem,
    DocumentType,
    ListDocumentsResponse,
    SingleDocumentResponse,
)
from apps.akaunting.models.items import Item, ItemResponse, ItemType, ListItemsResponse
from apps.akaunting.models.reconciliations import (
    Reconciliation,
    ReconciliationsResponse,
    SingleReconciliationResponse,
)
from apps.akaunting.models.taxes import Tax, TaxesResponse
from apps.akaunting.models.transactions import TransactionsResponse
from apps.akaunting.models.transfers import SingleTransferResponse, Transfer, TransfersResponse
from apps.akaunting.utils.faker import faker
from common.logger import logger


class AkauntingAPI:
    def __init__(
        self,
        username: str = settings.ADMIN_USERNAME,
        password: str = settings.ADMIN_PASSWORD,
        base_url: str = settings.API_URL,
        company_id: str = settings.AKAUNTING_COMPANY_ID,
    ):
        self.username = username
        self.password = password
        self.base_url = base_url
        self.headers = {"X-Company": company_id}
        self._session = None

    async def _get_session(self):
        """Ensure that the session exists and is active"""
        if self._session is None:
            logger.info(f"Creating new session for {self.username}@{self.base_url}")
            self._session = aiohttp.ClientSession(auth=aiohttp.BasicAuth(self.username, self.password))
        return self._session

    async def refresh_session(self):
        """Refresh the session"""
        if self._session is not None:
            await self._session.close()
            self._session = None
        await self._get_session()

    async def close(self):
        """Close the aiohttp session"""
        if self._session is not None:
            await self._session.close()
            self._session = None

    async def list_contacts(self, search_type: ContactType, page: int = 1, limit: int = 100000) -> list[Contact]:
        """
        Fetch contacts from the Akaunting API
        """
        endpoint = f"{self.base_url}/api/contacts"
        params = {"search": f"type:{search_type}", "page": page, "limit": limit}
        session = await self._get_session()

        async with session.get(endpoint, params=params) as response:
            response.raise_for_status()
            data = await response.json()
            return ContactsResponse(**data).data

    async def add_contact(
        self,
        name: str,
        email: str,
        type: ContactType,  # noqa: A002
        tax_number: str | None = None,
        currency_code: str = "USD",
        phone: str | None = None,
        website: str | None = None,
        address: str | None = None,
        enabled: bool = True,
        reference: str | None = None,
        city: str | None = None,
        post_code: str | None = None,
        country: str | None = None,
    ) -> SingleContactResponse:
        """
        Add a new contact to Akaunting
        """
        endpoint = f"{self.base_url}/api/contacts"

        params = {
            "name": name,
            "email": email,
            "tax_number": tax_number,
            "currency_code": currency_code,
            "phone": phone,
            "website": website,
            "address": address,
            "enabled": 1 if enabled else 0,
            "reference": reference,
            "type": type,
            "city": city,
            "post_code": post_code,
            "country": country,
            "search": f"type:{type}",
        }

        # Remove None values from params
        params = {k: v for k, v in params.items() if v is not None}
        session = await self._get_session()

        async with session.post(endpoint, params=params, headers=self.headers) as response:
            data = await response.json()
            response.raise_for_status()
            return SingleContactResponse(**data)

    async def delete_contact(self, contact_id: str, type: str = "customer") -> None:  # noqa: A002
        """
        Delete a contact from Akaunting
        """
        endpoint = f"{self.base_url}/api/contacts/{contact_id}"
        params = {"search": f"type:{type}"}
        session = await self._get_session()
        async with session.delete(endpoint, params=params, headers=self.headers) as response:
            response.raise_for_status()

    async def add_item(
        self,
        name: str,
        type: ItemType,  # noqa: A002
        sale_price: float,
        purchase_price: float | None = None,
        category_id: str | None = None,
        description: str | None = None,
        tax_ids: list[str] | None = None,
    ) -> ItemResponse:
        """
        Add a new item to Akaunting
        """
        endpoint = f"{self.base_url}/api/items"

        params = {
            "name": name,
            "sale_price": sale_price,
            "purchase_price": purchase_price,
            "category_id": category_id,
            "description": description,
            "type": type,
        }

        # Add tax_ids to params if provided
        if tax_ids:
            for i, tax_id in enumerate(tax_ids):
                params[f"tax_ids[{i}]"] = tax_id

        # Remove None values from params
        params = {k: v for k, v in params.items() if v is not None}
        session = await self._get_session()

        async with session.post(endpoint, params=params, headers=self.headers) as response:
            response.raise_for_status()
            return await response.json()

    async def list_items(self, page: int = 1, limit: int = 100000) -> list[Item]:
        """
        Fetch items from the Akaunting API
        """
        endpoint = f"{self.base_url}/api/items"
        params = {"page": page, "limit": limit}
        session = await self._get_session()

        async with session.get(endpoint, params=params) as response:
            response.raise_for_status()
            data = await response.json()
            return ListItemsResponse(**data).data

    async def delete_item(self, item_id: str) -> None:
        """
        Delete an item from Akaunting
        """
        endpoint = f"{self.base_url}/api/items/{item_id}"
        session = await self._get_session()

        async with session.delete(endpoint, headers=self.headers) as response:
            response.raise_for_status()

    async def list_taxes(self, page: int = 1, limit: int = 100000) -> list[Tax]:
        """
        Fetch taxes from the Akaunting API
        """
        endpoint = f"{self.base_url}/api/taxes"
        params = {"page": page, "limit": limit}
        session = await self._get_session()

        async with session.get(endpoint, params=params, headers=self.headers) as response:
            response.raise_for_status()
            data = await response.json()
            return TaxesResponse(**data).data

    async def add_tax(
        self,
        name: str,
        rate: float,
        type: str = "compound",  # noqa: A002
        enabled: bool = True,
    ) -> dict:
        """
        Add a new tax to Akaunting
        """
        endpoint = f"{self.base_url}/api/taxes"

        params = {
            "name": name,
            "rate": rate,
            "type": type,
            "enabled": 1 if enabled else 0,
        }

        session = await self._get_session()

        async with session.post(endpoint, params=params, headers=self.headers) as response:
            response.raise_for_status()
            return await response.json()

    async def delete_tax(self, tax_id: str) -> None:
        """
        Delete a tax from Akaunting
        """
        endpoint = f"{self.base_url}/api/taxes/{tax_id}"
        session = await self._get_session()

        async with session.delete(endpoint, headers=self.headers) as response:
            response.raise_for_status()

    async def list_currencies(self, page: int = 1, limit: int = 100000) -> list[Currency]:
        """
        Fetch currencies from the Akaunting API
        """
        endpoint = f"{self.base_url}/api/currencies"
        params = {"page": page, "limit": limit}
        session = await self._get_session()

        async with session.get(endpoint, params=params, headers=self.headers) as response:
            response.raise_for_status()
            data = await response.json()
            return CurrenciesResponse(**data).data

    async def add_currency(
        self,
        name: str,
        code: str,
        rate: float,
        symbol: str,
        precision: int = 2,
        symbol_first: bool = False,
        decimal_mark: str = ".",
        thousands_separator: str = ",",
        enabled: bool = True,
    ) -> dict:
        """
        Add a new currency to Akaunting
        """
        endpoint = f"{self.base_url}/api/currencies"

        params = {
            "name": name,
            "code": code,
            "rate": rate,
            "symbol": symbol,
            "precision": precision,
            "symbol_first": 1 if symbol_first else 0,
            "decimal_mark": decimal_mark,
            "thousands_separator": thousands_separator,
            "enabled": 1 if enabled else 0,
        }

        session = await self._get_session()

        async with session.post(endpoint, params=params, headers=self.headers) as response:
            response.raise_for_status()
            return await response.json()

    async def delete_currency(self, currency_id: str) -> None:
        """
        Delete a currency from Akaunting
        """
        endpoint = f"{self.base_url}/api/currencies/{currency_id}"
        session = await self._get_session()

        async with session.delete(endpoint, headers=self.headers) as response:
            response.raise_for_status()

    async def list_accounts(self, page: int = 1, limit: int = 100000) -> list[Account]:
        """
        Fetch accounts from the Akaunting API
        """
        endpoint = f"{self.base_url}/api/accounts"
        params = {"page": page, "limit": limit}
        session = await self._get_session()

        async with session.get(endpoint, params=params, headers=self.headers) as response:
            response.raise_for_status()
            data = await response.json()
            return AccountsResponse(**data).data

    async def add_account(
        self,
        name: str,
        number: str,
        currency_code: str = "USD",
        opening_balance: float = 0,
        bank_name: str | None = None,
        bank_phone: str | None = None,
        bank_address: str | None = None,
        enabled: bool = True,
        type: str = "bank",  # noqa: A002
    ) -> SingleAccountResponse:
        """
        Add a new account to Akaunting
        """
        endpoint = f"{self.base_url}/api/accounts"

        params = {
            "name": name,
            "number": number,
            "currency_code": currency_code,
            "opening_balance": opening_balance,
            "bank_name": bank_name,
            "bank_phone": bank_phone,
            "bank_address": bank_address,
            "enabled": 1 if enabled else 0,
            "type": type,
        }

        # Remove None values from params
        params = {k: v for k, v in params.items() if v is not None}
        session = await self._get_session()

        async with session.post(endpoint, params=params, headers=self.headers) as response:
            response.raise_for_status()
            data = await response.json()
            return SingleAccountResponse(**data)

    async def delete_account(self, account_id: str) -> None:
        """
        Delete an account from Akaunting
        """
        endpoint = f"{self.base_url}/api/accounts/{account_id}"
        session = await self._get_session()

        async with session.delete(endpoint, headers=self.headers) as response:
            response.raise_for_status()

    async def list_categories(self, type: CategoryType | None = None, page: int = 1, limit: int = 100000) -> list[Category]:  # noqa: A002
        """
        Fetch categories from the Akaunting API
        """
        endpoint = f"{self.base_url}/api/categories"
        params = {
            "search": f"type:{type if type else ''}",
            "page": page,
            "limit": limit,
        }
        session = await self._get_session()

        async with session.get(endpoint, params=params, headers=self.headers) as response:
            response.raise_for_status()
            data = await response.json()
            return CategoriesResponse(**data).data

    async def add_category(
        self,
        name: str,
        type: CategoryType | None = None,  # noqa: A002
        color: str | None = None,
        enabled: bool = True,
    ) -> SingleCategoryResponse:
        """
        Add a new category to Akaunting
        """
        endpoint = f"{self.base_url}/api/categories"

        params = {
            "name": name,
            "type": type,
            "color": color if color else faker.color(luminosity="light"),
            "enabled": 1 if enabled else 0,
        }

        session = await self._get_session()

        async with session.post(endpoint, params=params, headers=self.headers) as response:
            response.raise_for_status()
            data = await response.json()
            return SingleCategoryResponse(**data)

    async def delete_category(self, category_id: str) -> None:
        """
        Delete a category from Akaunting
        """
        endpoint = f"{self.base_url}/api/categories/{category_id}"
        session = await self._get_session()

        async with session.delete(endpoint, headers=self.headers) as response:
            response.raise_for_status()

    async def list_documents(self, document_type: str = "invoice", page: int = 1, limit: int = 100) -> list[Document]:
        """
        Fetch documents from the Akaunting API
        """
        endpoint = f"{self.base_url}/api/documents"
        params = {"search": f"type:{document_type}", "page": page, "limit": limit}
        session = await self._get_session()

        async with session.get(endpoint, params=params, headers=self.headers) as response:
            response.raise_for_status()
            data = await response.json()
            return ListDocumentsResponse(**data).data

    async def add_document(
        self,
        category_id: str,
        document_number: str,
        status: str,
        issued_at: str,
        due_at: str,
        account_id: str,
        currency_code: str,
        currency_rate: float,
        contact_id: str,
        contact_name: str,
        contact_email: str,
        contact_address: str,
        items: list[DocumentItem],
        amount: float,
        document_type: DocumentType,
        notes: str | None = None,
    ) -> SingleDocumentResponse:
        """
        Add a new document to Akaunting
        """
        endpoint = f"{self.base_url}/api/documents"

        params = {
            "category_id": category_id,
            "document_number": document_number,
            "status": status,
            "issued_at": issued_at,
            "due_at": due_at,
            "account_id": account_id,
            "currency_code": currency_code,
            "currency_rate": currency_rate,
            "notes": notes,
            "contact_id": contact_id,
            "contact_name": contact_name,
            "contact_email": contact_email,
            "contact_address": contact_address,
            "amount": amount,
            "type": document_type,
            "search": f"type:{document_type}",
        }

        # Add items to params
        for i, item in enumerate(items):
            item_dict = item.dict()
            for key, value in item_dict.items():
                if key == "tax_ids" and value:
                    for j, tax_id in enumerate(value):
                        params[f"items[{i}][tax_ids][{j}]"] = tax_id
                else:
                    params[f"items[{i}][{key}]"] = value

        # Remove None values from params
        params = {k: v for k, v in params.items() if v is not None}
        session = await self._get_session()

        async with session.post(endpoint, params=params, headers=self.headers) as response:
            response.raise_for_status()
            data = await response.json()
            return SingleDocumentResponse(**data)

    async def add_document_transaction(
        self,
        document_id: str,
        amount: float,
        number: str,
        category_id: str,
        type: Literal["income", "expense"],  # noqa: A002
        currency_code: str = "USD",
        currency_rate: float = 1.0,
        payment_method: str = "offline-payments.bank_transfer.2",
        account_id: str = "1",
        paid_at: str | None = None,
        reference: str | None = None,
        description: str | None = None,
        currency: str | None = None,
    ) -> dict:
        """
        Add a transaction to a document in Akaunting
        """
        endpoint = f"{self.base_url}/api/documents/{document_id}/transactions"

        params = {
            "amount": amount,
            "number": number,
            "category_id": category_id,
            "currency_code": currency_code,
            "currency_rate": currency_rate,
            "type": type,
            "payment_method": payment_method,
            "account_id": account_id,
            "paid_at": paid_at,
            "reference": reference,
            "description": description,
            "currency": currency,
            "document_id": document_id,
        }

        # Remove None values from params
        params = {k: v for k, v in params.items() if v is not None}
        session = await self._get_session()

        async with session.post(endpoint, params=params, headers=self.headers) as response:
            response.raise_for_status()
            return await response.json()

    async def delete_document(self, document_id: str, document_type: str = "invoice") -> None:
        """
        Delete a document from Akaunting
        """
        endpoint = f"{self.base_url}/api/documents/{document_id}"
        params = {"search": f"type:{document_type}"}
        session = await self._get_session()

        async with session.delete(endpoint, params=params, headers=self.headers) as response:
            response.raise_for_status()

    async def list_transfers(self, page: int = 1, limit: int = 100000) -> list[Transfer]:
        """
        Fetch transfers from the Akaunting API
        """
        endpoint = f"{self.base_url}/api/transfers"
        params = {"page": page, "limit": limit}
        session = await self._get_session()

        async with session.get(endpoint, params=params, headers=self.headers) as response:
            response.raise_for_status()
            data = await response.json()
            return TransfersResponse(**data).data

    async def add_transfer(
        self,
        from_account_id: str,
        to_account_id: str,
        amount: float,
        transferred_at: str,
        payment_method: str = "offline-payments.cash.1",
        from_currency_code: str = "USD",
        from_account_rate: float = 1.0,
        to_currency_code: str = "USD",
        to_account_rate: float = 1.0,
        currency_code: str = "USD",
        currency_rate: float = 1.0,
        reference: str | None = None,
    ) -> SingleTransferResponse:
        """
        Add a new transfer to Akaunting
        """
        endpoint = f"{self.base_url}/api/transfers"

        params = {
            "from_account_id": from_account_id,
            "to_account_id": to_account_id,
            "amount": amount,
            "transferred_at": transferred_at,
            "payment_method": payment_method,
            "from_currency_code": from_currency_code,
            "from_account_rate": from_account_rate,
            "to_currency_code": to_currency_code,
            "to_account_rate": to_account_rate,
            "currency_code": currency_code,
            "currency_rate": currency_rate,
            "reference": reference,
        }

        # Remove None values from params
        params = {k: v for k, v in params.items() if v is not None}
        session = await self._get_session()

        async with session.post(endpoint, params=params, headers=self.headers) as response:
            response.raise_for_status()
            data = await response.json()
            return SingleTransferResponse(**data)

    async def delete_transfer(self, transfer_id: str) -> None:
        """
        Delete a transfer from Akaunting
        """
        endpoint = f"{self.base_url}/api/transfers/{transfer_id}"
        session = await self._get_session()

        async with session.delete(endpoint, headers=self.headers) as response:
            response.raise_for_status()

    async def list_reconciliations(self, page: int = 1, limit: int = 100000) -> list[Reconciliation]:
        """
        Fetch reconciliations from the Akaunting API
        """
        endpoint = f"{self.base_url}/api/reconciliations"
        params = {"page": page, "limit": limit}
        session = await self._get_session()

        async with session.get(endpoint, params=params, headers=self.headers) as response:
            response.raise_for_status()
            data = await response.json()
            return ReconciliationsResponse(**data).data

    async def add_reconciliation(
        self,
        account_id: str,
        started_at: str,
        ended_at: str,
        closing_balance: float,
        reconciled: bool = False,
    ) -> SingleReconciliationResponse:
        """
        Add a new reconciliation to Akaunting

        Args:
            account_id: The ID of the account to reconcile
            started_at: Start date of reconciliation period (YYYY-MM-DD)
            ended_at: End date of reconciliation period (YYYY-MM-DD)
            closing_balance: The closing balance amount
            reconciled: Whether the reconciliation is marked as reconciled
            page: Page number for pagination
            limit: Number of items per page
        """
        endpoint = f"{self.base_url}/api/reconciliations"

        params = {
            "account_id": account_id,
            "started_at": started_at,
            "ended_at": ended_at,
            "closing_balance": closing_balance,
            "reconciled": "true" if reconciled else "false",
        }

        session = await self._get_session()

        async with session.post(endpoint, params=params, headers=self.headers) as response:
            response.raise_for_status()
            data = await response.json()
            return SingleReconciliationResponse(**data)

    async def delete_reconciliation(self, reconciliation_id: str) -> None:
        """
        Delete a reconciliation from Akaunting
        """
        endpoint = f"{self.base_url}/api/reconciliations/{reconciliation_id}"
        session = await self._get_session()

        async with session.delete(endpoint, headers=self.headers) as response:
            response.raise_for_status()

    async def list_transactions(
        self,
        account_id: str | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
        type: Literal["income", "expense"] | None = None,  # noqa: A002
        page: int = 1,
        limit: int = 100,
    ) -> TransactionsResponse:
        """
        Fetch transactions from the Akaunting API

        Args:
            account_id: Optional ID of the account to filter transactions for
            start_date: Optional start date in YYYY-MM-DD format
            end_date: Optional end date in YYYY-MM-DD format
            type: Optional transaction type ('income' or 'expense')
            page: Page number for pagination
            limit: Number of items per page
        """
        endpoint = f"{self.base_url}/api/transactions"
        params = {"page": page, "limit": limit}

        search_terms = []

        if type:
            search_terms.append(f"type:{type}")

        if account_id:
            search_terms.append(f"account_id:{account_id}")

        if start_date:
            search_terms.append(f"start_date:{start_date}")

        if end_date:
            search_terms.append(f"end_date:{end_date}")

        if search_terms:
            params["search"] = " ".join(search_terms)

        session = await self._get_session()

        async with session.get(endpoint, params=params, headers=self.headers) as response:
            response.raise_for_status()
            data = await response.json()
            return TransactionsResponse(**data)


api = AkauntingAPI()
