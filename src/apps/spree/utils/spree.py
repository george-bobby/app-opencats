"""
Async Spree API client using aiohttp.

Supports username/password OAuth2 authentication, listing storefront products,
and uploading images to a variant (with helpers to attach to a product's
master variant).
"""

from __future__ import annotations

import asyncio
import json
import mimetypes
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any
from urllib.parse import urljoin

import aiohttp

from apps.spree.config.settings import settings
from common.logger import Logger

from .database import db_client


logger = Logger()


class SpreeAPIError(Exception):
    """Base exception for Spree API errors."""

    def __init__(self, message: str, status_code: int | None = None, response_data: dict | None = None):
        super().__init__(message)
        self.status_code = status_code
        self.response_data = response_data


class SpreeAuthError(SpreeAPIError):
    """Authentication related errors."""

    pass


class SpreeClient:
    """
    Minimal async Spree API client.

    - Authenticates via OAuth2 password grant (username/password)
    - Lists products from Storefront API
    - Uploads images to a variant (Platform API)
    """

    def __init__(
        self,
        base_url: str | None = None,
        email: str | None = None,
        password: str | None = None,
        auto_authenticate: bool = True,
        request_timeout_seconds: float = 60.0,
    ) -> None:
        self.base_url = (base_url or settings.SPREE_URL).rstrip("/")
        self.email = email or settings.SPREE_ADMIN_EMAIL
        self.password = password or settings.SPREE_ADMIN_PASSWORD
        self._session: aiohttp.ClientSession | None = None
        self._access_token: str | None = None
        self._auto_authenticate = auto_authenticate
        self._auth_attempted = False
        self._auth_lock = asyncio.Lock()
        self._timeout = aiohttp.ClientTimeout(total=request_timeout_seconds)

    async def __aenter__(self) -> SpreeClient:
        await self.setup()
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        await self.close()

    async def setup(self) -> None:
        if self._session is None:
            self._session = aiohttp.ClientSession(
                timeout=self._timeout,
                headers={
                    "Accept": "application/json",
                    "User-Agent": "Spree-Python-Client/1.0",
                },
            )

        if self._auto_authenticate and not self._auth_attempted:
            await self._ensure_authenticated()

    async def close(self) -> None:
        if self._session:
            await self._session.close()
            self._session = None
        self._access_token = None
        self._auth_attempted = False
        self._auth_lock = asyncio.Lock()

    async def _ensure_authenticated(self) -> None:
        if self._access_token:
            return
        async with self._auth_lock:
            if self._access_token or self._auth_attempted:
                return
            self._auth_attempted = True
            await self.authenticate()

    async def authenticate(self) -> None:
        """
        Authenticate via OAuth2 password grant.

        Tries `/spree_oauth/token` first, then falls back to `/oauth/token`.
        """
        if not self._session:
            await self.setup()

        # Session is guaranteed to exist after setup()
        assert self._session is not None

        token_paths = ("/spree_oauth/token", "/oauth/token")
        data = {
            "grant_type": "password",
            "username": self.email,
            "password": self.password,
        }
        headers = {"Content-Type": "application/x-www-form-urlencoded"}

        last_error: SpreeAuthError | None = None
        for token_path in token_paths:
            token_url = urljoin(self.base_url + "/", token_path.lstrip("/"))
            try:
                async with self._session.post(token_url, data=data, headers=headers) as response:
                    text = await response.text()
                    try:
                        payload = json.loads(text) if text else {}
                    except json.JSONDecodeError:
                        payload = {"message": text}

                    if response.status in (200, 201):
                        access_token = payload.get("access_token") or payload.get("token")
                        if not access_token:
                            raise SpreeAuthError("Token response missing access_token", response.status, payload)
                        self._access_token = access_token
                        return
                    elif response.status == 401:
                        last_error = SpreeAuthError("Invalid credentials", response.status, payload)
                    else:
                        last_error = SpreeAuthError(f"Auth error: {response.status}", response.status, payload)
            except aiohttp.ClientError as e:
                last_error = SpreeAuthError(f"Network error during auth: {e!s}")

        raise last_error or SpreeAuthError("Authentication failed")

    async def authenticate_admin(self) -> bool:
        """
        Authenticate with admin interface using session-based login.
        Returns True if successful, False otherwise.
        """
        if not self._session:
            await self.setup()

        # Session is guaranteed to exist after setup()
        assert self._session is not None

        try:
            # Step 1: Get admin login page and CSRF token
            login_url = f"{self.base_url}/admin/login"

            # Set proper headers for GET request to get HTML page
            get_headers = {
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
                "Accept-Language": "en-US,en;q=0.9",
                "Cache-Control": "max-age=0",
                "DNT": "1",
                "Sec-Fetch-Dest": "document",
                "Sec-Fetch-Mode": "navigate",
                "Sec-Fetch-Site": "none",
                "Sec-Fetch-User": "?1",
                "Upgrade-Insecure-Requests": "1",
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/139.0.0.0 Safari/537.36",
            }

            async with self._session.get(login_url, headers=get_headers) as response:
                if response.status != 200:
                    return False

                html = await response.text()
                import re

                # Look for CSRF token in meta tag
                csrf_match = re.search(r'name="csrf-token" content="([^"]+)"', html)
                # Look for authenticity token in form
                auth_match = re.search(r'name="authenticity_token" value="([^"]+)"', html)

                csrf_token = csrf_match.group(1) if csrf_match else ""
                auth_token = auth_match.group(1) if auth_match else ""

            # Use auth_token for both (same token in working curl)
            token_to_use = auth_token if auth_token else csrf_token

            # Step 2: Submit login form with exact structure from working curl
            # Build raw form data to match curl exactly (including duplicate remember_me)
            from urllib.parse import quote

            login_data = (
                f"authenticity_token={quote(token_to_use)}&"
                f"spree_user%5Bemail%5D={quote(self.email)}&"
                f"spree_user%5Bpassword%5D={quote(self.password)}&"
                f"spree_user%5Bremember_me%5D=0&"
                f"spree_user%5Bremember_me%5D=1&"
                f"commit=Login"
            )

            headers = {
                "Accept-Language": "en-US,en;q=0.9",
                "Connection": "keep-alive",
                "Content-Type": "application/x-www-form-urlencoded;charset=UTF-8",
                "DNT": "1",
                "Origin": self.base_url,
                "Referer": login_url,
                "Sec-Fetch-Dest": "empty",
                "Sec-Fetch-Mode": "cors",
                "Sec-Fetch-Site": "same-origin",
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/139.0.0.0 Safari/537.36",
                "accept": "text/vnd.turbo-stream.html, text/html, application/xhtml+xml",  # lowercase like curl
                "sec-ch-ua": '"Chromium";v="139", "Not;A=Brand";v="99"',
                "sec-ch-ua-mobile": "?0",
                "sec-ch-ua-platform": '"macOS"',
                "x-csrf-token": token_to_use,  # Same token as in form
                "x-turbo-request-id": "640669c5-41ad-4233-a38e-5cc621083662",
            }

            async with self._session.post(login_url, data=login_data, headers=headers) as response:
                # Check if login was successful (redirect or success)
                if response.status in (200, 302, 303):
                    # Verify we can access admin area with proper headers
                    admin_url = f"{self.base_url}/admin"

                    # Use same headers as initial GET request for admin dashboard
                    admin_headers = {
                        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
                        "Accept-Language": "en-US,en;q=0.9",
                        "Cache-Control": "max-age=0",
                        "DNT": "1",
                        "Referer": login_url,  # Coming from login page
                        "Sec-Fetch-Dest": "document",
                        "Sec-Fetch-Mode": "navigate",
                        "Sec-Fetch-Site": "same-origin",
                        "Sec-Fetch-User": "?1",
                        "Upgrade-Insecure-Requests": "1",
                        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/139.0.0.0 Safari/537.36",
                    }

                    async with self._session.get(admin_url, headers=admin_headers) as admin_response:
                        return admin_response.status == 200

        except Exception:
            pass

        return False

    async def _request(
        self,
        method: str,
        endpoint: str,
        *,
        params: dict[str, Any] | None = None,
        json_body: dict[str, Any] | None = None,
        data: Any | None = None,
        expected_statuses: tuple[int, ...] = (200, 201),
        headers: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        if not self._session:
            await self.setup()

        # Ensure auth for non-auth endpoints
        if not endpoint.endswith("/token") and self._auto_authenticate:
            await self._ensure_authenticated()

        # Session is guaranteed to exist after setup()
        assert self._session is not None

        url = urljoin(self.base_url.rstrip("/") + "/", endpoint.lstrip("/"))
        request_headers = dict(headers or {})
        if self._access_token:
            request_headers["Authorization"] = f"Bearer {self._access_token}"

        request_kwargs: dict[str, Any] = {"params": params, "headers": request_headers}
        if json_body is not None:
            request_kwargs["json"] = json_body
        if data is not None:
            request_kwargs["data"] = data

        try:
            async with self._session.request(method, url, **request_kwargs) as response:
                text = await response.text()
                try:
                    payload = json.loads(text) if text else {}
                except json.JSONDecodeError:
                    payload = {"message": text}

                if response.status in expected_statuses:
                    if isinstance(payload, dict):
                        return payload
                    return {"data": payload}
                elif response.status == 401:
                    # Reset token so next call can reauth if desired
                    self._access_token = None
                    raise SpreeAuthError("Unauthorized", response.status, payload)
                else:
                    raise SpreeAPIError(f"API error: {response.status}", response.status, payload)
        except aiohttp.ClientError as e:
            raise SpreeAPIError(f"Network error: {e!s}")

    # ---- Storefront (read) ----
    async def list_storefront_products(
        self,
        *,
        page: int = 1,
        per_page: int = 25,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        query = {"page": page, "per_page": per_page}
        if params:
            query.update(params)
        return await self._request("GET", "/api/v2/storefront/products", params=query)

    async def list_platform_products(
        self,
        *,
        page: int = 1,
        per_page: int = 25,
        params: dict[str, Any] | None = None,
        include_drafts: bool = True,
    ) -> dict[str, Any]:
        """
        List products via Platform API (includes drafts and all product states).

        Args:
            page: Page number
            per_page: Products per page
            params: Additional query parameters
            include_drafts: Whether to include draft products (default: True)
        """
        query: dict[str, Any] = {"page": page, "per_page": per_page}
        if params:
            query.update(params)

        # If we want drafts, don't filter by status
        # If we don't want drafts, filter to only active products
        if not include_drafts:
            query["filter[status_eq]"] = "active"

        return await self._request("GET", "/api/v2/platform/products", params=query)

    async def iter_all_products(
        self,
        *,
        per_page: int = 50,
        params: dict[str, Any] | None = None,
        use_platform_api: bool = False,
        include_drafts: bool = False,
    ) -> AsyncIterator[dict[str, Any]]:
        """
        Iterate through all products.

        Args:
            per_page: Products per page
            params: Additional query parameters
            use_platform_api: Use Platform API instead of Storefront API
            include_drafts: Include draft products (only works with Platform API)
        """
        page = 1
        while True:
            if use_platform_api:
                resp = await self.list_platform_products(page=page, per_page=per_page, params=params, include_drafts=include_drafts)
            else:
                resp = await self.list_storefront_products(page=page, per_page=per_page, params=params)

            data = resp.get("data") or []
            if not data:
                break
            for item in data:
                yield item
            page += 1

    async def get_all_products(
        self,
        *,
        per_page: int = 50,
        params: dict[str, Any] | None = None,
        use_platform_api: bool = False,
        include_drafts: bool = False,
    ) -> list[dict[str, Any]]:
        """
        Get all products as a list.

        Args:
            per_page: Products per page
            params: Additional query parameters
            use_platform_api: Use Platform API instead of Storefront API
            include_drafts: Include draft products (only works with Platform API)
        """
        products: list[dict[str, Any]] = []
        async for item in self.iter_all_products(per_page=per_page, params=params, use_platform_api=use_platform_api, include_drafts=include_drafts):
            products.append(item)
        return products

    # ---- Platform (write/admin) ----
    async def get_platform_variants_for_product(self, product_id: int | str) -> list[dict[str, Any]]:
        """
        Get variants for a product via Platform API.

        Tries two common endpoints depending on Spree version.
        """
        # Try nested under product
        try:
            resp = await self._request("GET", f"/api/v2/platform/products/{product_id}/variants")
            variants = resp.get("data") or []
            if variants:
                return variants
        except SpreeAPIError:
            pass

        # Fallback: filter on variants collection
        try:
            resp = await self._request(
                "GET",
                "/api/v2/platform/variants",
                params={"filter[product_id_eq]": str(product_id)},
            )
            return resp.get("data") or []
        except SpreeAPIError as e:
            raise SpreeAPIError("Failed to fetch variants for product", e.status_code, e.response_data)

    async def get_master_variant_id(self, product_id: int | str) -> int | None:
        variants = await self.get_platform_variants_for_product(product_id)
        for variant in variants:
            attrs = variant.get("attributes") or {}
            if attrs.get("is_master") is True:
                # JSON:API id is a string
                variant_id = variant.get("id")
                if variant_id is not None:
                    try:
                        return int(variant_id)
                    except (TypeError, ValueError):
                        return None
                return None
        # Fallback: first variant id
        if variants:
            first_variant_id = variants[0].get("id")
            if first_variant_id is not None:
                try:
                    return int(first_variant_id)
                except (TypeError, ValueError):
                    return None
        return None

    async def upload_image_to_variant(self, variant_id: int | str, image_path: str | Path) -> dict[str, Any]:
        """Upload an image to a specific variant via Platform API."""
        if not self._session:
            await self.setup()

        # Session is guaranteed to exist after setup()
        assert self._session is not None

        image_path = str(image_path)
        content_type, _ = mimetypes.guess_type(image_path)
        if not content_type:
            content_type = "application/octet-stream"

        form = aiohttp.FormData()
        # Keep file open during request
        url = urljoin(
            self.base_url.rstrip("/") + "/",
            f"/api/v2/platform/variants/{variant_id}/images".lstrip("/"),
        )

        headers = {}
        if self._access_token:
            headers["Authorization"] = f"Bearer {self._access_token}"

        try:
            with Path.open(Path(image_path), "rb") as f:
                filename = Path(image_path).name
                form.add_field(
                    "image[attachment]",
                    f,
                    filename=filename,
                    content_type=content_type,
                )

                async with self._session.post(url, data=form, headers=headers) as response:
                    text = await response.text()
                    try:
                        payload = json.loads(text) if text else {}
                    except json.JSONDecodeError:
                        payload = {"message": text}

                    if response.status in (200, 201):
                        if isinstance(payload, dict):
                            return payload
                        return {"data": payload}
                    elif response.status == 401:
                        self._access_token = None
                        raise SpreeAuthError("Unauthorized", response.status, payload)
                    else:
                        raise SpreeAPIError(f"Image upload failed: {response.status}", response.status, payload)
        except aiohttp.ClientError as e:
            raise SpreeAPIError(f"Network error: {e!s}")

    async def upload_image_to_product_admin(self, product_id: int | str, image_path: str | Path, *, variant_id: int | str | None = None, alt_text: str = "") -> dict[str, Any]:
        """
        Upload an image directly to a product via Admin interface.

        Args:
            product_id: Product ID or slug
            image_path: Path to image file
            variant_id: Variant ID to attach to (defaults to 1 = master variant/all variants)
            alt_text: Alt text for the image
        """
        if not self._session:
            await self.setup()

        # Session is guaranteed to exist after setup()
        assert self._session is not None

        image_path = str(image_path)
        content_type, _ = mimetypes.guess_type(image_path)
        if not content_type:
            content_type = "application/octet-stream"

        # Get product slug from database if product_id is integer
        if isinstance(product_id, int) or (isinstance(product_id, str) and product_id.isdigit()):
            product_slug = await get_product_slug_by_id(int(product_id))
            if not product_slug:
                raise SpreeAPIError(f"Product with ID {product_id} not found or has no slug")
        else:
            # Assume it's already a slug
            product_slug = str(product_id)

        # If no variant_id provided, use 1 for master variant (applies to all variants)
        if variant_id is None:
            variant_id = 1  # Master variant viewable_id is always 1
            logger.debug("Using master variant (viewable_id=1) - applies to all variants")
        else:
            logger.debug(f"Using specified variant ID: {variant_id}")

        # First get CSRF token by visiting the admin page
        csrf_token = await self._get_csrf_token(product_slug)

        form = aiohttp.FormData()
        url = urljoin(
            self.base_url.rstrip("/") + "/",
            f"/admin/products/{product_slug}/images".lstrip("/"),
        )

        headers = {
            "Accept": "text/vnd.turbo-stream.html, text/html, application/xhtml+xml",
            "Accept-Language": "en-US,en;q=0.9",
            "Connection": "keep-alive",
            "DNT": "1",
            "Origin": self.base_url,
            "Referer": f"{self.base_url}/admin/products/{product_slug}/images/new",
            "Sec-Fetch-Dest": "empty",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Site": "same-origin",
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/139.0.0.0 Safari/537.36",
            "X-CSRF-Token": csrf_token,
            "x-turbo-request-id": "600586c8-4cdd-4441-93e6-236d8477e95a",  # Turbo request ID
            "sec-ch-ua": '"Chromium";v="139", "Not;A=Brand";v="99"',
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": '"macOS"',
        }

        try:
            # Add authenticity token to form data
            form.add_field("authenticity_token", csrf_token)

            # Add required form fields that Spree expects
            form.add_field("image[viewable_id]", str(variant_id))  # Target specific variant!
            form.add_field("image[alt]", alt_text)  # Custom alt text
            form.add_field("button", "")  # Empty button field

            logger.debug(f"Form data fields: authenticity_token, image[viewable_id]={variant_id}, image[alt]='{alt_text}', button=, image[attachment]")

            with Path.open(Path(image_path), "rb") as f:
                filename = Path(image_path).name
                form.add_field(
                    "image[attachment]",
                    f,
                    filename=filename,
                    content_type=content_type,
                )

                async with self._session.post(url, data=form, headers=headers) as response:
                    text = await response.text()

                    if response.status in (200, 201, 302, 303):  # Rails redirects after successful upload
                        return {"status": "success", "message": "Image uploaded successfully", "redirect_status": response.status}
                    elif response.status == 401:
                        raise SpreeAuthError("Unauthorized - check admin login", response.status, {"message": text})
                    else:
                        # Add more detailed error info for debugging
                        error_details = {
                            "message": text[:500],  # First 500 chars of response
                            "headers": dict(response.headers),
                            "url": str(url),
                            "product_slug": product_slug,
                            "product_id": str(product_id),
                            "variant_id": str(variant_id),
                            "alt_text": alt_text,
                            "form_data": {field.name: field.value if field.name != "image[attachment]" else f"<file: {filename}>" for field in form._fields},
                        }
                        raise SpreeAPIError(f"Admin image upload failed: {response.status}", response.status, error_details)
        except aiohttp.ClientError as e:
            raise SpreeAPIError(f"Network error: {e!s}")

    async def _get_csrf_token(self, product_slug: str) -> str:
        """Get CSRF token from admin interface."""
        # Session should already be initialized by caller
        assert self._session is not None

        # Try to get CSRF token from the new image page
        url = f"{self.base_url}/admin/products/{product_slug}/images/new"

        # Use proper headers for GET request
        get_headers = {
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
            "Accept-Language": "en-US,en;q=0.9",
            "Cache-Control": "max-age=0",
            "DNT": "1",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "same-origin",
            "Sec-Fetch-User": "?1",
            "Upgrade-Insecure-Requests": "1",
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/139.0.0.0 Safari/537.36",
        }

        try:
            async with self._session.get(url, headers=get_headers) as response:
                if response.status == 200:
                    html = await response.text()
                    # Look for CSRF token in meta tag or form
                    import re

                    csrf_match = re.search(r'name="csrf-token" content="([^"]+)"', html)
                    if csrf_match:
                        return csrf_match.group(1)

                    # Fallback: look for authenticity_token in forms
                    auth_match = re.search(r'name="authenticity_token" value="([^"]+)"', html)
                    if auth_match:
                        return auth_match.group(1)

                # Fallback: try admin dashboard
                admin_url = f"{self.base_url}/admin"
                async with self._session.get(admin_url, headers=get_headers) as admin_response:
                    if admin_response.status == 200:
                        admin_html = await admin_response.text()
                        csrf_match = re.search(r'name="csrf-token" content="([^"]+)"', admin_html)
                        if csrf_match:
                            return csrf_match.group(1)

        except Exception:
            pass

        # If all else fails, return a dummy token (some Spree installs don't require CSRF)
        return "dummy-csrf-token"

    async def add_images_to_product(
        self,
        product_id: int | str,
        image_paths: list[str | Path],
        *,
        to_master_variant: bool = True,
        use_admin_interface: bool = False,
        variant_id: int | str | None = None,
        alt_text: str = "",
    ) -> list[dict[str, Any]]:
        """
        Upload a list of images to a product.

        Args:
            product_id: The product ID
            image_paths: List of image file paths
            to_master_variant: Whether to attach to master variant (ignored if use_admin_interface=True)
            use_admin_interface: Use admin interface instead of Platform API
            variant_id: Specific variant ID to attach to (defaults to 1 = master variant/all variants)
            alt_text: Alt text for the images
        """
        if use_admin_interface:
            # Use admin interface - simpler, uploads directly to product/variant
            results: list[dict[str, Any]] = []
            for path in image_paths:
                results.append(await self.upload_image_to_product_admin(product_id, path, variant_id=variant_id, alt_text=alt_text))
            return results
        else:
            # Use Platform API - requires variant lookup
            if to_master_variant:
                variant_id = await self.get_master_variant_id(product_id)
                if variant_id is None:
                    variants = await self.get_platform_variants_for_product(product_id)
                    if not variants:
                        raise SpreeAPIError("No variants found for product; cannot attach image")
                    first_variant_id = variants[0].get("id")
                    if first_variant_id is None:
                        raise SpreeAPIError("No variant ID found from API")
                    try:
                        variant_id = int(first_variant_id)
                    except (TypeError, ValueError):
                        raise SpreeAPIError("Invalid variant id format from API")
            else:
                variant_id = await self.get_master_variant_id(product_id)

            # variant_id is guaranteed to be int here after the checks above
            assert variant_id is not None
            results: list[dict[str, Any]] = []
            for path in image_paths:
                results.append(await self.upload_image_to_variant(variant_id, path))
            return results


# Convenience helpers
_global_spree_client: SpreeClient | None = None


async def get_spree_client() -> SpreeClient:
    global _global_spree_client
    if _global_spree_client is None:
        _global_spree_client = SpreeClient()
        await _global_spree_client.setup()
    return _global_spree_client


async def close_spree_client() -> None:
    global _global_spree_client
    if _global_spree_client:
        await _global_spree_client.close()
        _global_spree_client = None


# Database product functions
async def get_all_products(
    *,
    limit: int | None = None,
    offset: int = 0,
    status: str | None = None,
    include_deleted: bool = False,
    order_by: str = "created_at DESC",
) -> list[dict[str, Any]]:
    """
    Get all products from the database.

    Args:
        limit: Maximum number of products to return
        offset: Number of products to skip
        status: Filter by product status ('active', 'draft', 'archived', etc.)
        include_deleted: Whether to include deleted products
        order_by: SQL ORDER BY clause (default: 'created_at DESC')

    Returns:
        List of product dictionaries
    """
    # Build query conditions
    conditions = []
    params = []
    param_count = 0

    if not include_deleted:
        conditions.append("deleted_at IS NULL")

    if status:
        param_count += 1
        conditions.append(f"status = ${param_count}")
        params.append(status)

    # Build WHERE clause
    where_clause = ""
    if conditions:
        where_clause = f"WHERE {' AND '.join(conditions)}"

    # Build LIMIT clause
    limit_clause = ""
    if limit:
        param_count += 1
        limit_clause = f"LIMIT ${param_count}"
        params.append(limit)

    # Build OFFSET clause
    offset_clause = ""
    if offset > 0:
        param_count += 1
        offset_clause = f"OFFSET ${param_count}"
        params.append(offset)

    query = f"""
        SELECT id, name, description, available_on, deleted_at, slug,
               meta_description, meta_keywords, tax_category_id, shipping_category_id,
               created_at, updated_at, promotionable, meta_title, discontinue_on,
               public_metadata, private_metadata, status, make_active_at
        FROM spree_products
        {where_clause}
        ORDER BY {order_by}
        {limit_clause}
        {offset_clause}
    """

    try:
        records = await db_client.fetch(query, *params)
        return [dict(record) for record in records]
    except Exception as e:
        raise SpreeAPIError(f"Database error getting all products: {e}")


async def get_product_by_id(product_id: int) -> dict[str, Any] | None:
    """
    Get a single product by its ID from the database.

    Args:
        product_id: The product ID

    Returns:
        Product dictionary or None if not found
    """
    query = """
        SELECT id, name, description, available_on, deleted_at, slug,
               meta_description, meta_keywords, tax_category_id, shipping_category_id,
               created_at, updated_at, promotionable, meta_title, discontinue_on,
               public_metadata, private_metadata, status, make_active_at
        FROM spree_products
        WHERE id = $1 AND deleted_at IS NULL
    """

    try:
        record = await db_client.fetchrow(query, product_id)
        return dict(record) if record else None
    except Exception as e:
        raise SpreeAPIError(f"Database error getting product by ID {product_id}: {e}")


async def get_product_by_slug(slug: str) -> dict[str, Any] | None:
    """
    Get a single product by its slug from the database.

    Args:
        slug: The product slug

    Returns:
        Product dictionary or None if not found
    """
    query = """
        SELECT id, name, description, available_on, deleted_at, slug,
               meta_description, meta_keywords, tax_category_id, shipping_category_id,
               created_at, updated_at, promotionable, meta_title, discontinue_on,
               public_metadata, private_metadata, status, make_active_at
        FROM spree_products
        WHERE slug = $1 AND deleted_at IS NULL
    """

    try:
        record = await db_client.fetchrow(query, slug)
        return dict(record) if record else None
    except Exception as e:
        raise SpreeAPIError(f"Database error getting product by slug '{slug}': {e}")


async def get_product_slug_by_id(product_id: int) -> str | None:
    """
    Get a product's slug by its ID from the database.

    Args:
        product_id: The product ID

    Returns:
        Product slug or None if not found
    """
    query = """
        SELECT slug
        FROM spree_products
        WHERE id = $1 AND deleted_at IS NULL
    """

    try:
        record = await db_client.fetchrow(query, product_id)
        return record["slug"] if record else None
    except Exception as e:
        raise SpreeAPIError(f"Database error getting product slug for ID {product_id}: {e}")


async def get_products_with_variants(
    *,
    limit: int | None = None,
    offset: int = 0,
    status: str | None = None,
    include_deleted: bool = False,
) -> list[dict[str, Any]]:
    """
    Get products with their variants from the database.

    Args:
        limit: Maximum number of products to return
        offset: Number of products to skip
        status: Filter by product status
        include_deleted: Whether to include deleted products

    Returns:
        List of product dictionaries with variants included
    """
    # First get products
    products = await get_all_products(
        limit=limit,
        offset=offset,
        status=status,
        include_deleted=include_deleted,
    )

    if not products:
        return []

    # Get product IDs
    product_ids = [product["id"] for product in products]

    # Get variants for these products
    variants_query = """
        SELECT v.id, v.product_id, v.sku, v.price, v.weight, v.height, v.width, v.depth,
               v.deleted_at, v.is_master, v.position, v.cost_price, v.track_inventory,
               v.cost_currency, v.created_at, v.updated_at,
               p.amount as price_amount, p.currency
        FROM spree_variants v
        LEFT JOIN spree_prices p ON v.id = p.variant_id
        WHERE v.product_id = ANY($1::bigint[]) AND v.deleted_at IS NULL
        ORDER BY v.product_id, v.position
    """

    try:
        variant_records = await db_client.fetch(variants_query, product_ids)

        # Group variants by product_id
        variants_by_product = {}
        for variant in variant_records:
            product_id = variant["product_id"]
            if product_id not in variants_by_product:
                variants_by_product[product_id] = []
            variants_by_product[product_id].append(dict(variant))

        # Add variants to products
        for product in products:
            product["variants"] = variants_by_product.get(product["id"], [])

        return products

    except Exception as e:
        raise SpreeAPIError(f"Database error getting products with variants: {e}")
