"""API utilities for Medusa - API clients and Medusa requests."""

import asyncio
from typing import Any

import aiohttp

from apps.medusa.config.settings import settings
from apps.medusa.utils.api_auth import authenticate_async
from common.logger import logger


class MedusaAPIUtils:
    """Consolidated API utilities for all GET requests in Medusa core operations."""

    def __init__(self):
        self.base_url = settings.MEDUSA_API_URL
        self.auth = None
        self.session = None

    async def __aenter__(self):
        logger.info("Initializing Medusa API utilities...")
        self.auth = await authenticate_async()
        self.session = aiohttp.ClientSession()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()

    async def _make_get_request(self, endpoint: str, params: dict[str, Any] | None = None) -> dict[str, Any] | None:
        """Make a GET request to the Medusa API with proper error handling."""
        if not self.auth or not self.session:
            raise RuntimeError("API utilities not initialized. Use async context manager.")

        try:
            headers = self.auth.get_auth_headers()
            url = f"{self.base_url}{endpoint}"

            async with self.session.get(url, headers=headers, params=params) as response:
                if response.status == 200:
                    return await response.json()
                else:
                    error_text = await response.text()
                    logger.error(f"Failed to fetch from {endpoint}: {response.status} - {error_text}")
                    return None
        except Exception as e:
            logger.error(f"Error fetching from {endpoint}: {e}")
            return None

    async def _make_post_request(self, endpoint: str, payload: dict[str, Any] | None = None) -> tuple[int, dict[str, Any] | None]:
        """Make a POST request to the Medusa API with proper error handling."""
        if not self.auth or not self.session:
            raise RuntimeError("API utilities not initialized. Use async context manager.")

        try:
            headers = self.auth.get_auth_headers()
            url = f"{self.base_url}{endpoint}"

            async with self.session.post(url, headers=headers, json=payload or {}) as response:
                status = response.status
                if status in (200, 201):
                    return status, await response.json()
                else:
                    error_text = await response.text()
                    logger.error(f"Failed to post to {endpoint}: {status} - {error_text}")
                    return status, None
        except Exception as e:
            logger.error(f"Error posting to {endpoint}: {e}")
            return 0, None

    async def _fetch_with_pagination(self, endpoint: str, result_key: str, initial_limit: int = 1000) -> list[dict[str, Any]]:
        """Fetch data with smart pagination."""
        result = await self._make_get_request(endpoint, {"limit": initial_limit})

        if not result:
            logger.warning(f"Failed to fetch {result_key}")
            return []

        items = result.get(result_key, [])

        if len(items) == initial_limit:
            logger.debug("Large dataset detected, using pagination...")
            offset = initial_limit
            limit = 100

            while True:
                page_result = await self._make_get_request(endpoint, {"limit": limit, "offset": offset})

                if not page_result:
                    break

                page_items = page_result.get(result_key, [])

                if not page_items:
                    break

                items.extend(page_items)
                offset += limit

                if len(page_items) < limit:
                    break

        logger.info(f"Fetched {len(items)} {result_key}")
        return items

    async def fetch_categories(self) -> list[dict[str, Any]]:
        """Fetch all existing categories from Medusa API."""
        result = await self._make_get_request("/admin/product-categories")

        if result:
            categories = result.get("product_categories", [])
            logger.info(f"Fetched {len(categories)} categories")
            return categories
        else:
            logger.warning("Failed to fetch categories")
            return []

    async def fetch_sales_channels(self) -> list[dict[str, Any]]:
        """Fetch existing sales channels from Medusa API."""
        result = await self._make_get_request("/admin/sales-channels")

        if result:
            sales_channels = result.get("sales_channels", [])
            logger.info(f"Fetched {len(sales_channels)} sales channels")
            return sales_channels
        else:
            logger.warning("Failed to fetch sales channels")
            return []

    async def fetch_shipping_profiles(self) -> list[dict[str, Any]]:
        """Fetch existing shipping profiles from Medusa API."""
        result = await self._make_get_request("/admin/shipping-profiles")

        if result:
            shipping_profiles = result.get("shipping_profiles", [])
            logger.info(f"Fetched {len(shipping_profiles)} shipping profiles")
            return shipping_profiles
        else:
            logger.warning("Failed to fetch shipping profiles")
            return []

    async def fetch_collections(self) -> list[dict[str, Any]]:
        """Fetch all existing collections from Medusa API with pagination."""
        return await self._fetch_with_pagination("/admin/collections", "collections", initial_limit=100)

    async def fetch_tags(self) -> list[dict[str, Any]]:
        """Fetch all existing product tags from Medusa API with smart pagination."""
        return await self._fetch_with_pagination("/admin/product-tags", "product_tags")

    async def fetch_product_types(self) -> list[dict[str, Any]]:
        """Fetch all existing product types from Medusa API with smart pagination."""
        return await self._fetch_with_pagination("/admin/product-types", "product_types")

    async def fetch_products(self, limit: int = 100, offset: int = 0) -> list[dict[str, Any]]:
        """Fetch products from Medusa API with pagination."""
        result = await self._make_get_request("/admin/products", {"limit": limit, "offset": offset})

        if result:
            products = result.get("products", [])
            logger.info(f"Fetched {len(products)} products")
            return products
        else:
            logger.warning("Failed to fetch products")
            return []

    async def fetch_product_variants(self, product_id: str) -> list[dict[str, Any]]:
        """Fetch variants for a specific product."""
        result = await self._make_get_request(f"/admin/products/{product_id}/variants")

        if result:
            variants = result.get("variants", [])
            logger.debug(f"Fetched {len(variants)} variants for product {product_id}")
            return variants
        else:
            logger.warning(f"Failed to fetch variants for product {product_id}")
            return []

    async def fetch_customers(self) -> list[dict[str, Any]]:
        """Fetch existing customers from Medusa API."""
        result = await self._make_get_request("/admin/customers")

        if result:
            customers = result.get("customers", [])
            logger.info(f"Fetched {len(customers)} customers")
            return customers
        else:
            logger.warning("Failed to fetch customers")
            return []

    async def fetch_customer_groups(self) -> list[dict[str, Any]]:
        """Fetch existing customer groups from Medusa API."""
        result = await self._make_get_request("/admin/customer-groups")

        if result:
            customer_groups = result.get("customer_groups", [])
            logger.info(f"Fetched {len(customer_groups)} customer groups")
            return customer_groups
        else:
            logger.warning("Failed to fetch customer groups")
            return []

    async def fetch_orders(self, limit: int = 100, offset: int = 0) -> list[dict[str, Any]]:
        """Fetch orders from Medusa API with pagination."""
        result = await self._make_get_request("/admin/orders", {"limit": limit, "offset": offset})

        if result:
            orders = result.get("orders", [])
            logger.info(f"Fetched {len(orders)} orders")
            return orders
        else:
            logger.warning("Failed to fetch orders")
            return []

    async def fetch_order_by_id(self, order_id: str) -> dict[str, Any] | None:
        """Fetch a specific order by ID."""
        result = await self._make_get_request(f"/admin/orders/{order_id}")

        if result:
            order = result.get("order")
            logger.debug(f"Fetched order {order_id}")
            return order
        else:
            logger.warning(f"Failed to fetch order {order_id}")
            return None

    async def fetch_draft_orders(self, limit: int = 100, offset: int = 0) -> list[dict[str, Any]]:
        """Fetch draft orders from Medusa API with pagination."""
        result = await self._make_get_request("/admin/draft-orders", {"limit": limit, "offset": offset})

        if result:
            if isinstance(result, dict):
                draft_orders = result.get("draft_orders", [])
            elif isinstance(result, list):
                draft_orders = result
            else:
                draft_orders = []

            logger.info(f"Fetched {len(draft_orders)} draft orders")
            return draft_orders
        else:
            logger.warning("Failed to fetch draft orders")
            return []

    async def fetch_all_draft_orders(self) -> list[dict[str, Any]]:
        """Fetch ALL draft orders from Medusa API with complete pagination."""
        return await self._fetch_with_pagination("/admin/draft-orders", "draft_orders", initial_limit=100)

    async def fetch_draft_order_by_id(self, order_id: str) -> dict[str, Any] | None:
        """Fetch a specific draft order by ID."""
        result = await self._make_get_request(f"/admin/draft-orders/{order_id}")

        if result:
            draft_order = result.get("draft_order")
            logger.debug(f"Fetched draft order {order_id}")
            return draft_order
        else:
            logger.warning(f"Failed to fetch draft order {order_id}")
            return None

    async def fetch_shipping_options(self, cart_id: str | None = None) -> list[dict[str, Any]]:
        """Fetch available shipping options."""
        endpoint = f"/store/shipping-options/{cart_id}" if cart_id else "/admin/shipping-options"
        result = await self._make_get_request(endpoint)

        if result:
            return result.get("shipping_options", [])
        return []

    async def fetch_stock_locations(self) -> list[dict[str, Any]]:
        """Fetch all stock locations from Medusa API."""
        result = await self._make_get_request("/admin/stock-locations")

        if result:
            stock_locations = result.get("stock_locations", [])
            logger.info(f"Fetched {len(stock_locations)} stock locations")
            return stock_locations
        else:
            logger.warning("Failed to fetch stock locations")
            return []

    async def fetch_inventory_items(self, limit: int = 100, offset: int = 0) -> list[dict[str, Any]]:
        """Fetch inventory items from Medusa API with pagination."""
        result = await self._make_get_request("/admin/inventory-items", {"limit": limit, "offset": offset})

        if result:
            inventory_items = result.get("inventory_items", [])
            logger.info(f"Fetched {len(inventory_items)} inventory items")
            return inventory_items
        else:
            logger.warning("Failed to fetch inventory items")
            return []

    async def fetch_price_lists(self) -> list[dict[str, Any]]:
        """Fetch all price lists from Medusa API."""
        result = await self._make_get_request("/admin/price-lists")

        if result:
            price_lists = result.get("price_lists", [])
            logger.info(f"Fetched {len(price_lists)} price lists")
            return price_lists
        else:
            logger.warning("Failed to fetch price lists")
            return []

    async def fetch_promotions(self) -> list[dict[str, Any]]:
        """Fetch all promotions from Medusa API."""
        result = await self._make_get_request("/admin/promotions")

        if result:
            promotions = result.get("promotions", [])
            logger.info(f"Fetched {len(promotions)} promotions")
            return promotions
        else:
            logger.warning("Failed to fetch promotions")
            return []

    async def fetch_campaigns(self) -> list[dict[str, Any]]:
        """Fetch all campaigns from Medusa API."""
        result = await self._make_get_request("/admin/campaigns")

        if result:
            campaigns = result.get("campaigns", [])
            logger.info(f"Fetched {len(campaigns)} campaigns")
            return campaigns
        else:
            logger.warning("Failed to fetch campaigns")
            return []

    async def fetch_product_attributes(self) -> list[dict[str, Any]]:
        """Fetch all product attributes from Medusa API."""
        result = await self._make_get_request("/admin/product-attributes")

        if result:
            attributes = result.get("product_attributes", [])
            logger.info(f"Fetched {len(attributes)} product attributes")
            return attributes
        else:
            logger.warning("Failed to fetch product attributes")
            return []

    async def fetch_return_reasons(self) -> list[dict[str, Any]]:
        """Fetch all return reasons from Medusa API."""
        result = await self._make_get_request("/admin/return-reasons")

        if result:
            return_reasons = result.get("return_reasons", [])
            logger.info(f"Fetched {len(return_reasons)} return reasons")
            return return_reasons
        else:
            logger.warning("Failed to fetch return reasons")
            return []

    async def fetch_regions(self) -> list[dict[str, Any]]:
        """Fetch all regions from Medusa API."""
        result = await self._make_get_request("/admin/regions")

        if result:
            regions = result.get("regions", [])
            logger.info(f"Fetched {len(regions)} regions")
            return regions
        else:
            logger.warning("Failed to fetch regions")
            return []

    async def edit_draft_order(self, order_id: str) -> bool:
        """Start editing a draft order."""
        status, _ = await self._make_post_request(f"/admin/draft-orders/{order_id}/edit")
        return status in (200, 201)

    async def add_shipping_method_to_draft(self, order_id: str, shipping_option_id: str) -> bool:
        """Add shipping method to draft order."""
        payload = {"shipping_option_id": shipping_option_id}
        status, _ = await self._make_post_request(f"/admin/draft-orders/{order_id}/edit/shipping-methods", payload)
        return status in (200, 201)

    async def request_draft_order_confirmation(self, order_id: str) -> bool:
        """Request the draft order changes."""
        status, _ = await self._make_post_request(f"/admin/draft-orders/{order_id}/edit/request")
        return status in (200, 201)

    async def confirm_draft_order_changes(self, order_id: str) -> bool:
        """Confirm the draft order changes."""
        status, _ = await self._make_post_request(f"/admin/draft-orders/{order_id}/edit/confirm")
        return status in (200, 201)

    async def fetch_all_catalog_data(self) -> dict[str, list[dict[str, Any]]]:
        """Fetch all catalog-related data in parallel."""
        logger.info("Fetching all catalog data...")

        results = await asyncio.gather(
            self.fetch_categories(),
            self.fetch_sales_channels(),
            self.fetch_shipping_profiles(),
            self.fetch_collections(),
            self.fetch_tags(),
            self.fetch_product_types(),
            return_exceptions=True,
        )

        def safe_result(result: Any) -> list[dict[str, Any]]:
            return result if not isinstance(result, Exception) else []

        return {
            "categories": safe_result(results[0]),
            "sales_channels": safe_result(results[1]),
            "shipping_profiles": safe_result(results[2]),
            "collections": safe_result(results[3]),
            "tags": safe_result(results[4]),
            "product_types": safe_result(results[5]),
        }

    async def fetch_all_customer_data(self) -> dict[str, list[dict[str, Any]]]:
        """Fetch all customer-related data in parallel."""
        logger.info("Fetching all customer data...")

        results = await asyncio.gather(self.fetch_customers(), self.fetch_customer_groups(), return_exceptions=True)

        def safe_result(result: Any) -> list[dict[str, Any]]:
            return result if not isinstance(result, Exception) else []

        return {
            "customers": safe_result(results[0]),
            "customer_groups": safe_result(results[1]),
        }

    async def fetch_all_inventory_data(self) -> dict[str, list[dict[str, Any]]]:
        """Fetch all inventory-related data in parallel."""
        logger.info("Fetching all inventory data...")

        results = await asyncio.gather(self.fetch_stock_locations(), self.fetch_inventory_items(), return_exceptions=True)

        def safe_result(result: Any) -> list[dict[str, Any]]:
            return result if not isinstance(result, Exception) else []

        return {
            "stock_locations": safe_result(results[0]),
            "inventory_items": safe_result(results[1]),
        }

    async def fetch_all_pricing_data(self) -> dict[str, list[dict[str, Any]]]:
        """Fetch all pricing-related data in parallel."""
        logger.info("Fetching all pricing data...")

        results = await asyncio.gather(
            self.fetch_price_lists(),
            self.fetch_promotions(),
            self.fetch_campaigns(),
            return_exceptions=True,
        )

        def safe_result(result: Any) -> list[dict[str, Any]]:
            return result if not isinstance(result, Exception) else []

        return {
            "price_lists": safe_result(results[0]),
            "promotions": safe_result(results[1]),
            "campaigns": safe_result(results[2]),
        }


class MedusaClient:
    """Client for interacting with Medusa API."""

    def __init__(self, base_url: str | None = None, auth=None):
        self.base_url = base_url or settings.MEDUSA_API_URL
        self.session: aiohttp.ClientSession | None = None
        self.auth = auth

    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        if self.auth and not self.auth.is_authenticated():
            await self.auth.authenticate_async()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()

    async def create_customer(self, customer_data: dict[str, Any]) -> dict[str, Any]:
        """Create a new customer."""
        if not self.session:
            raise RuntimeError("Client not initialized. Use async context manager.")

        url = f"{self.base_url}/admin/customers"
        headers = self.auth.get_auth_headers() if self.auth else {}
        async with self.session.post(url, json=customer_data, headers=headers) as response:
            return await response.json()

    async def create_product(self, product_data: dict[str, Any]) -> dict[str, Any]:
        """Create a new product."""
        if not self.session:
            raise RuntimeError("Client not initialized. Use async context manager.")

        url = f"{self.base_url}/admin/products"
        headers = self.auth.get_auth_headers() if self.auth else {}
        async with self.session.post(url, json=product_data, headers=headers) as response:
            response_data = await response.json()

            if response.status not in (200, 201):
                logger.error(f"Product creation failed (status {response.status}): {product_data.get('title', 'unknown')}")
                logger.debug(f"Response: {response_data}")

            return response_data

    async def create_order(self, order_data: dict[str, Any]) -> dict[str, Any]:
        """Create a new order."""
        if not self.session:
            raise RuntimeError("Client not initialized. Use async context manager.")

        url = f"{self.base_url}/admin/orders"
        headers = self.auth.get_auth_headers() if self.auth else {}
        async with self.session.post(url, json=order_data, headers=headers) as response:
            return await response.json()

    async def _fetch_paginated(self, endpoint: str, result_key: str, limit: int = 100) -> dict[str, Any]:
        """Fetch paginated data from Medusa API."""
        if not self.session:
            raise RuntimeError("Client not initialized. Use async context manager.")

        try:
            all_items = []
            offset = 0

            while True:
                url = f"{self.base_url}{endpoint}"
                headers = self.auth.get_auth_headers() if self.auth else {}
                params = {"limit": limit, "offset": offset}

                async with self.session.get(url, headers=headers, params=params) as response:
                    response.raise_for_status()
                    result = await response.json()

                    items = result.get(result_key, [])
                    if not items:
                        break

                    all_items.extend(items)

                    count = result.get("count", 0)
                    if len(all_items) >= count:
                        break

                    offset += limit

            return {result_key: all_items, "count": len(all_items)}

        except Exception as e:
            logger.error(f"Failed to fetch {result_key} from Medusa: {e}")
            raise

    async def get_tags(self, limit: int = 100) -> dict[str, Any]:
        """Get all product tags from Medusa with pagination."""
        return await self._fetch_paginated("/admin/product-tags", "product_tags", limit)

    async def get_types(self, limit: int = 100) -> dict[str, Any]:
        """Get all product types from Medusa with pagination."""
        return await self._fetch_paginated("/admin/product-types", "product_types", limit)

    async def get_collections(self) -> dict[str, Any]:
        """Get all product collections from Medusa."""
        if not self.session:
            raise RuntimeError("Client not initialized. Use async context manager.")

        try:
            url = f"{self.base_url}/admin/collections"
            headers = self.auth.get_auth_headers() if self.auth else {}

            async with self.session.get(url, headers=headers) as response:
                response.raise_for_status()
                return await response.json()

        except Exception as e:
            logger.error(f"Failed to fetch collections from Medusa: {e}")
            raise

    async def get_categories(self) -> dict[str, Any]:
        """Get all product categories from Medusa."""
        if not self.session:
            raise RuntimeError("Client not initialized. Use async context manager.")

        try:
            url = f"{self.base_url}/admin/product-categories"
            headers = self.auth.get_auth_headers() if self.auth else {}

            async with self.session.get(url, headers=headers) as response:
                response.raise_for_status()
                return await response.json()

        except Exception as e:
            logger.error(f"Failed to fetch categories from Medusa: {e}")
            raise

    async def get_sales_channels(self) -> dict[str, Any]:
        """Get all sales channels from Medusa."""
        if not self.session:
            raise RuntimeError("Client not initialized. Use async context manager.")

        try:
            url = f"{self.base_url}/admin/sales-channels"
            headers = self.auth.get_auth_headers() if self.auth else {}

            async with self.session.get(url, headers=headers) as response:
                response.raise_for_status()
                return await response.json()

        except Exception as e:
            logger.error(f"Failed to fetch sales channels from Medusa: {e}")
            raise
