import asyncio
import re
from typing import Any, Literal

import aiohttp

from apps.gumroad.config.settings import settings
from common.logger import logger


class GumroadAPI:
    """Async HTTP client for interacting with Gumroad API"""

    def __init__(
        self,
        base_url: str = settings.GUMROAD_BASE_URL,
        email: str | None = settings.GUMROAD_EMAIL,
        password: str | None = settings.GUMROAD_PASSWORD,
        auto_login: bool = True,
    ):
        self.base_url = base_url
        self.email = email
        self.password = password
        self.auto_login = auto_login
        self.session: aiohttp.ClientSession | None = None
        self.csrf_token: str | None = None
        self.cookies: dict[str, str] = {}
        self.logged_in: bool = False

        # Default headers
        self.default_headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:139.0) Gecko/20100101 Firefox/139.0",
            "Accept": "application/json, text/html",
            "Accept-Language": "en-US,en;q=0.5",
            "Accept-Encoding": "gzip, deflate, br, zstd",
            "Content-Type": "application/json",
            "Sec-GPC": "1",
            "Connection": "keep-alive",
            "Sec-Fetch-Dest": "empty",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Site": "same-origin",
            "Priority": "u=0",
            "TE": "trailers",
        }

    async def __aenter__(self):
        """Async context manager entry"""
        await self.start_session()
        if self.auto_login and self.email and self.password:
            login_result = await self.login(self.email, self.password)
            if login_result.get("status_code") in [200, 201, 302]:
                self.logged_in = True
                logger.info("Auto-login successful!")
            else:
                logger.warning(f"Auto-login failed: {login_result.get('error', 'Unknown error')}")
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        await self.close_session()

    async def start_session(self):
        """Initialize the aiohttp session"""
        if self.session is None:
            connector = aiohttp.TCPConnector(ssl=False)
            self.session = aiohttp.ClientSession(
                connector=connector,
                headers=self.default_headers,
                timeout=aiohttp.ClientTimeout(total=30),
            )

    async def close_session(self):
        """Close the aiohttp session"""
        if self.session:
            await self.session.close()
            self.session = None

    def _prepare_headers(self, referer: str | None = None, origin: str | None = None, **kwargs) -> dict[str, str]:
        """Prepare headers for requests with common patterns"""
        headers = self.default_headers.copy()
        if referer:
            headers["Referer"] = referer
        if origin:
            headers["Origin"] = origin
        if self.csrf_token:
            headers["x-csrf-token"] = self.csrf_token
        headers.update(kwargs)
        return headers

    def _update_cookies(self, response):
        """Update stored cookies from response"""
        if response.cookies:
            for cookie_name in response.cookies:
                self.cookies[cookie_name] = response.cookies[cookie_name].value

    async def _process_response(self, response) -> dict[str, Any]:
        """Process response and return standardized format"""
        self._update_cookies(response)

        try:
            response_data = await response.json()
        except aiohttp.ContentTypeError:
            response_data = {"text": await response.text(), "status": response.status}

        response_data.update(
            {
                "status_code": response.status,
                "headers": dict(response.headers),
                "cookies": self.cookies,
            }
        )
        return response_data

    def _resolve_url(self, url: str) -> tuple[str, dict[str, str]]:
        """Resolve URL and return actual URL and additional headers for .localhost domains"""
        from urllib.parse import urlparse, urlunparse

        parsed = urlparse(url)
        additional_headers = {}

        # If domain ends with .localhost, use 127.0.0.1 and add Host header
        if parsed.hostname and parsed.hostname.endswith(".localhost"):
            # Replace hostname with 127.0.0.1
            netloc = f"127.0.0.1:{parsed.port}" if parsed.port else "127.0.0.1"
            resolved_url = urlunparse((parsed.scheme, netloc, parsed.path, parsed.params, parsed.query, parsed.fragment))
            # Add Host header to maintain the original domain
            additional_headers["Host"] = parsed.hostname
            return resolved_url, additional_headers

        return url, additional_headers

    async def _make_authenticated_request(
        self,
        method: str,
        endpoint: str,
        json_data: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
        referer: str | None = None,
        origin: str | None = None,
        **header_kwargs,
    ) -> dict[str, Any]:
        """Make an authenticated request with standard error handling"""
        await self.login_if_needed()
        if not self.session:
            await self.start_session()

        url = f"{self.base_url}{endpoint}"
        resolved_url, host_headers = self._resolve_url(url)

        headers = self._prepare_headers(
            referer=referer or f"{self.base_url}{endpoint}",
            origin=origin or self.base_url,
            **header_kwargs,
        )
        # Add Host header if needed for .localhost domains
        headers.update(host_headers)

        try:
            async with self.session.request(
                method,
                resolved_url,
                headers=headers,
                json=json_data,
                params=params,
                cookies=self.cookies,
            ) as response:
                return await self._process_response(response)
        except aiohttp.ClientError as e:
            return {"error": f"Request failed: {e!s}", "status_code": None}

    def ensure_authenticated(self):
        """Raise an exception if not logged in"""
        if not self.logged_in:
            raise Exception("Not authenticated. Please login first or provide credentials for auto-login.")

    async def login_if_needed(self):
        """Login if not already logged in and credentials are available"""
        if not self.logged_in and self.email and self.password:
            login_result = await self.login(self.email, self.password)
            if login_result.get("status_code") in [200, 201, 302]:
                self.logged_in = True
                logger.info("Login successful!")
            else:
                logger.info(login_result)
                raise Exception(f"Login failed: {login_result.get('error', 'Unknown error')}")
        elif not self.logged_in:
            raise Exception("Not logged in and no credentials available.")

    async def get_csrf_token(self, next_url: str = "/settings/profile") -> str | None:
        """Get CSRF token by visiting the login page"""
        if not self.session:
            await self.start_session()

        login_page_url = f"{self.base_url}/login?next={next_url}"
        resolved_url, host_headers = self._resolve_url(login_page_url)

        headers = {
            "User-Agent": self.default_headers["User-Agent"],
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": self.default_headers["Accept-Language"],
            "Upgrade-Insecure-Requests": "1",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
        }
        # Add Host header if needed for .localhost domains
        headers.update(host_headers)

        try:
            async with self.session.get(resolved_url, headers=headers, cookies=self.cookies) as response:
                self._update_cookies(response)
                html_content = await response.text()

                # Try multiple patterns to find CSRF token
                csrf_patterns = [
                    r'<meta\s+name=["\']csrf-token["\']\s+content=["\']([^"\']+)["\']',
                    r'<input\s+[^>]*name=["\']authenticity_token["\']\s+[^>]*value=["\']([^"\']+)["\']',
                    r'window\._token\s*=\s*["\']([^"\']+)["\']',
                    r'csrf_token["\']?\s*:\s*["\']([^"\']+)["\']',
                ]

                for pattern in csrf_patterns:
                    match = re.search(pattern, html_content, re.IGNORECASE)
                    if match:
                        self.csrf_token = match.group(1)
                        logger.info(f"Found CSRF token: {self.csrf_token[:20]}...")
                        return self.csrf_token

                logger.warning("No CSRF token found")
                return None

        except aiohttp.ClientError as e:
            logger.error(f"Error getting CSRF token: {e!s}")
            return None

    async def handle_two_factor(self, user_id: str, token: str = "000000", next_url: str = "/dashboard") -> dict[str, Any]:
        """Handle 2FA authentication with Gumroad"""
        if not self.session:
            await self.start_session()

        # Get fresh CSRF token for 2FA page
        csrf_token = await self.get_csrf_token(next_url)
        if not csrf_token:
            logger.warning("Could not get CSRF token for 2FA, proceeding without it")

        headers = self._prepare_headers(
            referer=f"{self.base_url}/two-factor?next={next_url.replace('/', '%2F')}",
            origin=self.base_url,
        )
        if csrf_token:
            headers["x-csrf-token"] = csrf_token
            self.csrf_token = csrf_token

        payload = {"token": token, "next": next_url}

        try:
            two_factor_json_url = f"{self.base_url}/two-factor.json"
            resolved_two_factor_url, two_factor_host_headers = self._resolve_url(two_factor_json_url)
            headers.update(two_factor_host_headers)

            async with self.session.post(
                resolved_two_factor_url,
                headers=headers,
                json=payload,
                params={"user_id": user_id},
                cookies=self.cookies,
            ) as response:
                response_data = await self._process_response(response)
                if response.status in [200, 201, 302]:
                    self.logged_in = True
                    logger.info("2FA authentication successful")
                return response_data
        except aiohttp.ClientError as e:
            return {"error": f"2FA request failed: {e!s}", "status_code": None}

    def extract_user_id_from_redirect(self, redirect_location: str) -> str | None:
        """Extract user_id from 2FA redirect URL"""
        # The redirect_location might contain user_id as a query parameter
        # or we might need to extract it from the URL
        import urllib.parse

        if "user_id=" in redirect_location:
            parsed = urllib.parse.urlparse(redirect_location)
            query_params = urllib.parse.parse_qs(parsed.query)
            return query_params.get("user_id", [None])[0]

        # If user_id is not in the redirect, we'll need to extract it from cookies
        # or make a request to the 2FA page to get it
        return None

    async def get_user_id_from_two_factor_page(self, next_url: str = "/dashboard") -> str | None:
        """Get user_id by visiting the 2FA page"""
        if not self.session:
            await self.start_session()

        two_factor_url = f"{self.base_url}/two-factor?next={next_url.replace('/', '%2F')}"
        resolved_url, host_headers = self._resolve_url(two_factor_url)

        headers = {
            "User-Agent": self.default_headers["User-Agent"],
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": self.default_headers["Accept-Language"],
            "Upgrade-Insecure-Requests": "1",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
        }
        # Add Host header if needed for .localhost domains
        headers.update(host_headers)

        try:
            async with self.session.get(resolved_url, headers=headers, cookies=self.cookies) as response:
                self._update_cookies(response)
                html_content = await response.text()

                # Look for user_id in the HTML or URL
                user_id_patterns = [
                    r'user_id["\']?\s*[:=]\s*["\']([^"\']+)["\']',
                    r'data-user-id["\']?\s*=\s*["\']([^"\']+)["\']',
                    r'/two-factor\.json\?user_id=([^"\'&\s]+)',
                ]

                for pattern in user_id_patterns:
                    match = re.search(pattern, html_content, re.IGNORECASE)
                    if match:
                        user_id = match.group(1)
                        logger.info(f"Found user_id: {user_id[:20]}...")
                        return user_id

                # Check if user_id is in the current URL
                current_url = str(response.url)
                if "user_id=" in current_url:
                    import urllib.parse

                    parsed = urllib.parse.urlparse(current_url)
                    query_params = urllib.parse.parse_qs(parsed.query)
                    user_id = query_params.get("user_id", [None])[0]
                    if user_id:
                        logger.info(f"Found user_id in URL: {user_id[:20]}...")
                        return user_id

                logger.warning("No user_id found in 2FA page")
                return None

        except aiohttp.ClientError as e:
            logger.error(f"Error getting user_id from 2FA page: {e!s}")
            return None

    async def login(
        self,
        email: str,
        password: str,
        next_url: str = "/settings/profile",
        csrf_token: str | None = None,
        auto_get_csrf: bool = True,
        auto_handle_2fa: bool = True,
    ) -> dict[str, Any]:
        """Login to Gumroad with automatic 2FA handling"""
        if not self.session:
            await self.start_session()

        if not csrf_token and auto_get_csrf:
            csrf_token = await self.get_csrf_token(next_url)
            if not csrf_token:
                return {"error": "Could not obtain CSRF token", "status_code": None}

        headers = self._prepare_headers(referer=f"{self.base_url}/login?next={next_url}", origin=self.base_url)
        if csrf_token:
            headers["x-csrf-token"] = csrf_token
            self.csrf_token = csrf_token

        payload = {
            "user": {"login_identifier": email, "password": password},
            "next": next_url,
            "g-recaptcha-response": None,
        }

        try:
            login_url = f"{self.base_url}/login"
            resolved_login_url, login_host_headers = self._resolve_url(login_url)
            headers.update(login_host_headers)

            async with self.session.post(
                resolved_login_url,
                headers=headers,
                json=payload,
                cookies=self.cookies,
            ) as response:
                response_data = await self._process_response(response)

                # Check if 2FA is required
                if response_data.get("redirect_location") and "/two-factor" in response_data["redirect_location"]:
                    if not auto_handle_2fa:
                        logger.info("2FA required but auto_handle_2fa is disabled")
                        return response_data

                    logger.info("2FA required, attempting automatic authentication...")

                    # Extract user_id from redirect or get it from the 2FA page
                    user_id = self.extract_user_id_from_redirect(response_data["redirect_location"])
                    if not user_id:
                        user_id = await self.get_user_id_from_two_factor_page(next_url)

                    if not user_id:
                        return {
                            "error": "Could not extract user_id for 2FA authentication",
                            "status_code": response.status,
                            "requires_2fa": True,
                            "redirect_location": response_data.get("redirect_location"),
                        }

                    # Handle 2FA with the default token "000000"
                    two_fa_result = await self.handle_two_factor(user_id, "000000", next_url)
                    return two_fa_result

                elif response.status in [200, 201, 302]:
                    self.logged_in = True
                    logger.info("Login successful (no 2FA required)")

                return response_data

        except aiohttp.ClientError as e:
            return {"error": f"Request failed: {e!s}", "status_code": None}

    # Simplified methods using the helper functions
    async def set_settings(self, settings_data: dict[str, Any]) -> dict[str, Any]:
        """Update user settings on Gumroad"""
        result = await self._make_authenticated_request("PUT", "/settings", json_data=settings_data)
        if result.get("status_code") in [200, 201]:
            logger.info("Settings updated successfully")
        return result

    async def get_settings(self) -> dict[str, Any]:
        """Get current user settings from Gumroad"""
        return await self._make_authenticated_request("GET", "/settings")

    async def set_profile(self, profile: dict[str, Any]) -> dict[str, Any]:
        """Update user profile on Gumroad"""
        result = await self._make_authenticated_request("PUT", "/settings/profile", json_data=profile)
        if result.get("status_code") in [200, 201]:
            logger.info("Profile updated successfully")
        return result

    async def get_profile(self) -> dict[str, Any]:
        """Get current user profile from Gumroad"""
        return await self._make_authenticated_request("GET", "/settings/profile")

    def extract_product_id_from_response(self, response: dict[str, Any]) -> str | None:
        """Extract product ID from add_product response"""
        if not response.get("success") or not response.get("redirect_to"):
            return None
        match = re.search(r"/products/([^/]+)/edit", response["redirect_to"])
        return match.group(1) if match else None

    async def add_product(
        self,
        name: str,
        price: str,
        currency: str = "usd",
        is_physical: bool = False,
        is_recurring: bool = False,
        release_date: str | None = None,
        release_time: str | None = None,
        subscription_duration: Literal["monthly", "yearly"] | None = None,
        _type: Literal[
            "course",
            "ebook",
            "membership",
            "physical",
            "digital",
            "bundle",
            "call",
            "coffee",
        ] = "digital",
    ) -> dict[str, Any]:
        """Add a new product to Gumroad"""
        data = {
            "link": {
                "name": name,
                "price_range": price,
                "price_currency_type": currency,
                "is_physical": is_physical,
                "is_recurring_billing": is_recurring,
                "native_type": "physical" if is_physical else "digital",
                "release_at_date": release_date,
                "release_at_time": release_time,
                "subscription_duration": subscription_duration,
            }
        }

        response = await self._make_authenticated_request("POST", "/links", json_data=data, referer=f"{self.base_url}/products/new")

        # Check if the API call was successful first
        if response.get("status_code") not in [200, 201]:
            logger.error(f"Product creation failed: {response.get('error', 'Unknown error')}")
            return response

        # Extract and add product_id to response
        product_id = self.extract_product_id_from_response(response)
        if product_id:
            response["product_id"] = product_id
        else:
            logger.error(f"Failed to extract product_id from response: {response}")
        return response

    async def add_product_cover(self, product_id: str, cover_url: str) -> dict[str, Any]:
        """Add a cover image/asset preview to a Gumroad product"""
        data = {"asset_preview": {"url": cover_url}}
        return await self._make_authenticated_request(
            "POST",
            f"/links/{product_id}/asset_previews",
            json_data=data,
            referer=f"{self.base_url}/products/{product_id}/edit",
        )

    async def update_product_details(self, product_id: str, product_details: dict[str, Any]) -> dict[str, Any]:
        """Update detailed product information on Gumroad"""
        result = await self._make_authenticated_request(
            "POST",
            f"/links/{product_id}",
            json_data=product_details,
            referer=f"{self.base_url}/products/{product_id}/edit",
        )
        if result.get("status_code") in [200, 201]:
            logger.info(f"Product details updated successfully for ID: {product_id}")
        return result

    async def update_product_contents(self, product_id: str, product_content: dict[str, Any]) -> dict[str, Any]:
        """
        Update product contents/files on Gumroad

        Args:
            product_id: The product ID to update
            product_content: Dictionary containing all product content data including:
                - Basic info (name, description, price_cents, etc.)
                - Files and file_attributes
                - Rich content
                - Variants, availability, shipping, etc.
                - Settings and configurations

        Returns:
            Dict containing response data
        """
        result = await self._make_authenticated_request(
            "POST",
            f"/links/{product_id}",
            json_data=product_content,
            referer=f"{self.base_url}/products/{product_id}/edit/content",
        )

        if result.get("status_code") in [200, 201]:
            logger.info(f"Product contents updated successfully for ID: {product_id}")
        else:
            logger.warning(f"Product contents update failed with status: {result.get('status_code')}")

        return result

    async def get_products(self, page: int = 1, if_none_match: str | None = None) -> dict[str, Any]:
        """Get paginated list of products from Gumroad"""
        headers = {}
        if if_none_match:
            headers["If-None-Match"] = if_none_match

        result = await self._make_authenticated_request(
            "GET",
            "/products/paged",
            params={"page": page},
            referer=f"{self.base_url}/products",
            **headers,
        )

        if result.get("status_code") == 200:
            products_count = len(result.get("entries", []))
            total_pages = result.get("pagination", {}).get("pages", 0)
            logger.info(f"Retrieved {products_count} products from page {page} of {total_pages}")
        return result

    async def get_all_products(self) -> list[dict[str, Any]]:
        """Get ALL products from Gumroad across all pages - returns list of products directly"""
        logger.info("Fetching all products from Gumroad...")

        first_page_response = await self.get_products(page=1)
        if first_page_response.get("status_code") != 200:
            logger.error(f"Failed to fetch products: {first_page_response.get('error', 'Unknown error')}")
            return []

        pagination = first_page_response.get("pagination", {})
        total_pages = pagination.get("pages", 1)
        all_entries = first_page_response.get("entries", [])

        if total_pages > 1:
            remaining_page_tasks = [self.get_products(page=page_num) for page_num in range(2, total_pages + 1)]
            remaining_pages_responses = await asyncio.gather(*remaining_page_tasks, return_exceptions=True)

            for page_num, response in enumerate(remaining_pages_responses, start=2):
                if isinstance(response, Exception):
                    logger.error(f"Error fetching page {page_num}: {response!s}")
                    continue
                if response.get("status_code") == 200:
                    all_entries.extend(response.get("entries", []))

        total_products = len(all_entries)
        logger.info(f"Successfully retrieved all {total_products} products from {total_pages} pages.")

        return all_entries

    async def publish_product(self, product_id: str) -> dict[str, Any]:
        """Publish a product on Gumroad"""
        result = await self._make_authenticated_request(
            "POST",
            f"/links/{product_id}/publish",
            referer=f"{self.base_url}/products/{product_id}/edit/content",
            **{"Content-Length": "0"},
        )
        return result

    async def unpublish_product(self, product_id: str) -> dict[str, Any]:
        """Unpublish a product on Gumroad"""
        result = await self._make_authenticated_request(
            "POST",
            f"/links/{product_id}/unpublish",
            referer=f"{self.base_url}/products/{product_id}/edit",
            **{"Content-Length": "0"},
        )
        return result

    async def add_discount(
        self,
        name: str,
        code: str,
        amount_percentage: int | None = None,
        amount_cents: int | None = None,
        selected_product_ids: list | None = None,
        universal: bool = True,
        max_purchase_count: int | None = None,
        currency_type: str | None = None,
        valid_at: str | None = None,
        expires_at: str | None = None,
        minimum_quantity: int = 1,
        duration_in_billing_cycles: int | None = None,
        minimum_amount_cents: int | None = None,
    ) -> dict[str, Any]:
        """Add a new discount code to Gumroad"""
        discount_data = {
            "name": name,
            "code": code,
            "selected_product_ids": selected_product_ids,
            "universal": universal,
            "minimum_quantity": minimum_quantity,
        }

        # Add optional fields
        optional_fields = {
            "amount_percentage": amount_percentage,
            "amount_cents": amount_cents,
            "max_purchase_count": max_purchase_count,
            "currency_type": currency_type,
            "valid_at": valid_at,
            "expires_at": expires_at,
            "duration_in_billing_cycles": duration_in_billing_cycles,
            "minimum_amount_cents": minimum_amount_cents,
        }

        for key, value in optional_fields.items():
            if value is not None:
                discount_data[key] = value

        result = await self._make_authenticated_request(
            "POST",
            "/checkout/discounts",
            json_data=discount_data,
            referer=f"{self.base_url}/checkout/discounts",
        )

        if result.get("status_code") in [200, 201]:
            logger.info(f"Discount '{name}' created successfully with code: {code}")
        return result

    async def set_checkout_form(self, user_settings: dict[str, Any], custom_fields: list[dict[str, Any]]) -> dict[str, Any]:
        """Update checkout form settings on Gumroad"""
        payload = {"user": user_settings, "custom_fields": custom_fields}
        result = await self._make_authenticated_request(
            "PUT",
            "/checkout/form",
            json_data=payload,
            referer=f"{self.base_url}/checkout/form",
        )
        if result.get("status_code") in [200, 201]:
            logger.info("Checkout form settings updated successfully")
        return result

    async def add_workflow(
        self,
        name: str,
        workflow_type: Literal[
            "seller",
            "follower",
            "audience",
            "affiliate",
            "abandoned_cart",
            "product",
            "variant",
        ] = "seller",
        workflow_trigger: str | None = None,
        bought_products: list[str] | None = None,
        bought_variants: list[str] | None = None,
        variant_external_id: str | None = None,
        permalink: str | None = None,
        not_bought_products: list[str] | None = None,
        not_bought_variants: list[str] | None = None,
        paid_more_than: float | None = None,
        paid_less_than: float | None = None,
        created_after: str = "",
        created_before: str = "",
        bought_from: str = "",
        affiliate_products: list[str] | None = None,
        send_to_past_customers: bool = False,
        save_action_name: str = "save_and_publish",
        link_id: str | None = None,
    ) -> dict[str, Any]:
        """Add a new workflow to Gumroad"""
        workflow_data = {
            "name": name,
            "workflow_type": workflow_type,
            "workflow_trigger": workflow_trigger,
            "bought_products": bought_products or [],
            "bought_variants": bought_variants or [],
            "variant_external_id": variant_external_id,
            "permalink": permalink,
            "not_bought_products": not_bought_products or [],
            "not_bought_variants": not_bought_variants or [],
            "paid_more_than": paid_more_than,
            "paid_less_than": paid_less_than,
            "created_after": created_after,
            "created_before": created_before,
            "bought_from": bought_from,
            "affiliate_products": affiliate_products or [],
            "send_to_past_customers": send_to_past_customers,
            "save_action_name": save_action_name,
        }

        payload = {"workflow": workflow_data, "link_id": link_id}
        result = await self._make_authenticated_request(
            "POST",
            "/internal/workflows",
            json_data=payload,
            referer=f"{self.base_url}/workflows/new",
        )

        if result.get("status_code") in [200, 201]:
            logger.info(f"Workflow '{name}' created successfully")
        return result

    async def add_workflow_email(
        self,
        workflow_id: str,
        installments: list[dict[str, Any]],
        send_to_past_customers: bool = True,
        save_action_name: str = "save",
    ) -> dict[str, Any]:
        """Add email installments to a workflow on Gumroad"""
        workflow_data = {
            "send_to_past_customers": send_to_past_customers,
            "save_action_name": save_action_name,
            "installments": installments,
        }

        payload = {"workflow": workflow_data}
        result = await self._make_authenticated_request(
            "PUT",
            f"/internal/workflows/{workflow_id}/save_installments",
            json_data=payload,
            referer=f"{self.base_url}/workflows/{workflow_id}/emails",
        )

        if result.get("status_code") in [200, 201]:
            logger.info(f"Workflow emails saved successfully for workflow: {workflow_id}")
            logger.info(f"  - Added {len(installments)} email installments")
        return result

    async def publish_workflow(
        self,
        workflow_id: str,
        workflow_data: dict[str, Any] = {},  # noqa: B006
        link_id: str | None = None,
    ) -> dict[str, Any]:
        """
        Publish/update a workflow on Gumroad

        Args:
            workflow_id: The workflow ID to publish/update
            workflow_data: Workflow data dictionary containing workflow settings
            link_id: Optional link ID associated with the workflow

        Returns:
            Dict containing response data
        """
        # Ensure save_action_name is set to publish
        if "save_action_name" not in workflow_data:
            workflow_data["save_action_name"] = "save_and_publish"

        payload = {"workflow": workflow_data, "link_id": link_id}

        result = await self._make_authenticated_request(
            "PUT",
            f"/internal/workflows/{workflow_id}",
            json_data=payload,
            referer=f"{self.base_url}/workflows/{workflow_id}/edit",
        )

        return result

    async def add_email(
        self,
        name: str,
        message: str,
        files: list[str] | None = None,
        link_id: str | None = None,
        published_at: str | None = None,
        shown_in_profile_sections: list[str] | None = None,
        paid_more_than_cents: int | None = None,
        paid_less_than_cents: int | None = None,
        bought_from: str | None = None,
        installment_type: str = "audience",
        created_after: str = "",
        created_before: str = "",
        bought_products: list[str] | None = None,
        bought_variants: list[str] | None = None,
        not_bought_products: list[str] | None = None,
        not_bought_variants: list[str] | None = None,
        affiliate_products: list[str] | None = None,
        send_emails: bool = False,
        shown_on_profile: bool = True,
        allow_comments: bool = True,
        variant_external_id: str | None = None,
        send_preview_email: bool = False,
        to_be_published_at: str | None = None,
        publish: bool = False,
    ) -> dict[str, Any]:
        """Add a new email installment to Gumroad"""
        installment_data = {
            "name": name,
            "message": message,
            "files": files or [],
            "link_id": link_id,
            "published_at": published_at,
            "shown_in_profile_sections": shown_in_profile_sections or [],
            "paid_more_than_cents": paid_more_than_cents,
            "paid_less_than_cents": paid_less_than_cents,
            "bought_from": bought_from,
            "installment_type": installment_type,
            "created_after": created_after,
            "created_before": created_before,
            "bought_products": bought_products,
            "bought_variants": bought_variants,
            "not_bought_products": not_bought_products or [],
            "not_bought_variants": not_bought_variants or [],
            "affiliate_products": affiliate_products,
            "send_emails": send_emails,
            "shown_on_profile": shown_on_profile,
            "allow_comments": allow_comments,
        }

        payload = {
            "installment": installment_data,
            "variant_external_id": variant_external_id,
            "send_preview_email": send_preview_email,
            "to_be_published_at": to_be_published_at,
            "publish": publish,
        }

        result = await self._make_authenticated_request(
            "POST",
            "/internal/installments",
            json_data=payload,
            referer=f"{self.base_url}/emails/new",
        )

        if result.get("status_code") in [200, 201]:
            logger.info(f"Email installment '{name}' created successfully")
        else:
            logger.warning(f"Email installment creation failed with status: {result.get('status_code')}")

        return result
