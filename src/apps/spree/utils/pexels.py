import asyncio
import base64
import random
from typing import Any

import aiohttp

from apps.spree.config.settings import settings
from common.logger import logger


DEFAULT_MAX_RETRIES = 3
INITIAL_RETRY_DELAY = 5.0  # seconds
BACKOFF_MULTIPLIER = 3.0  # exponential factor


class PexelsAPI:
    """Async HTTP client for interacting with Pexels API"""

    def __init__(
        self,
        api_keys: str | None = settings.PEXELS_API_KEYS,
        base_url: str = "https://api.pexels.com/v1",
    ):
        # Parse API keys from comma-separated string
        if api_keys:
            self.api_keys = [key.strip() for key in api_keys.split(",") if key.strip()]
        else:
            self.api_keys = []

        self.base_url = base_url
        self.session: aiohttp.ClientSession | None = None

        if not self.api_keys:
            raise ValueError("At least one Pexels API key is required")

        # Default headers for Pexels API (will be updated with current key)
        self.default_headers = {
            "User-Agent": "Pexels-Python-Client/1.0",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

    def _get_current_api_key(self) -> str:
        """Get a random API key for better load distribution"""
        if not self.api_keys:
            raise ValueError("No API keys available")
        return random.choice(self.api_keys)

    def _rotate_api_key(self):
        """Rotate to a random API key for better distribution"""
        # No need to track current index since we use random selection
        pass

    def _get_headers_with_key(self, api_key: str | None = None) -> dict[str, str]:
        """Get headers with the specified API key or current rotated key"""
        if api_key is None:
            api_key = self._get_current_api_key()

        headers = self.default_headers.copy()
        headers["Authorization"] = api_key
        return headers

    async def __aenter__(self):
        """Async context manager entry"""
        await self.start_session()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        await self.close_session()

    async def start_session(self):
        """Initialize the aiohttp session"""
        if self.session is None:
            connector = aiohttp.TCPConnector(ssl=True)
            self.session = aiohttp.ClientSession(
                connector=connector,
                timeout=aiohttp.ClientTimeout(total=30),
            )

    async def close_session(self):
        """Close the aiohttp session"""
        if self.session:
            await self.session.close()
            self.session = None

    async def make_request(
        self,
        endpoint: str,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
        max_retries: int = DEFAULT_MAX_RETRIES,
    ) -> dict[str, Any]:
        """
        Make a GET request to the Pexels API with automatic key rotation and retry logic

        Args:
            endpoint: API endpoint (relative to base_url)
            params: URL parameters
            headers: Additional headers
            max_retries: Maximum number of retries with different API keys

        Returns:
            Dict containing response data
        """
        if not self.session:
            await self.start_session()

        url = f"{self.base_url}/{endpoint.lstrip('/')}"

        # Try with different API keys if request fails
        for attempt in range(max_retries):
            # Calculate exponential backoff delay
            if attempt > 0:
                delay = INITIAL_RETRY_DELAY * (BACKOFF_MULTIPLIER ** (attempt - 1))
                logger.debug(f"Retrying in {delay:.1f} seconds (attempt {attempt + 1}/{max_retries})")
                await asyncio.sleep(delay)

            # Get headers with current API key (rotate for each attempt)
            request_headers = self._get_headers_with_key()
            if headers:
                request_headers.update(headers)

            if self.session is None:
                raise RuntimeError("aiohttp session is not initialized.")

            # Convert all param values to str for query string
            params_str = {k: str(v) for k, v in params.items()} if params else None
            async with self.session.get(url, headers=request_headers, params=params_str) as response:
                # Parse response
                try:
                    response_data = await response.json()
                except aiohttp.ContentTypeError:
                    response_data = {
                        "text": await response.text(),
                        "status": response.status,
                    }

                response_data.update({"status_code": response.status, "headers": dict(response.headers)})

                if response.status == 200:
                    return response_data
                elif response.status == 429:  # Rate limit
                    logger.debug(f"Rate limit hit with key {self._get_current_api_key()[:4]}..., rotating to random key")
                    continue
                else:
                    logger.warning(f"Pexels API request failed with status {response.status}: {response_data}")
                    # For other errors, try with random key
                    continue

                self._rotate_api_key()

        # If we get here, all retries failed
        return {"error": f"All {max_retries} attempts failed", "status_code": None}

    async def search_photos(
        self,
        query: str,
        per_page: int = 15,
        page: int = 1,
        orientation: str | None = None,
        size: str | None = None,
        color: str | None = None,
        locale: str | None = None,
    ) -> dict[str, Any]:
        """
        Search for photos using the Pexels API

        Args:
            query: Search query (required)
            per_page: Number of results per page (default: 15, max: 80)
            page: Page number (default: 1, max: 1000)
            orientation: Photo orientation ("landscape", "portrait", "square")
            size: Photo size ("large", "medium", "small")
            color: Photo color ("red", "orange", "yellow", "green", "turquoise", "blue", "violet", "pink", "brown", "black", "gray", "white")
            locale: Locale for the search (e.g., "en-US", "pt-BR", "es-ES", "de-DE", "it-IT", "fr-FR", etc.)

        Returns:
            Dict containing search results with photos, pagination info, etc.
        """
        # logger.info(f"Searching for photos with query: {query} using API key: {self._get_current_api_key()}")

        params = {
            "query": query,
            "per_page": min(per_page, 80),  # Max 80 per page
            "page": min(page, 1000),  # Max 1000 pages
        }

        # Add optional parameters
        if orientation:
            params["orientation"] = orientation
        if size:
            params["size"] = size
        if color:
            params["color"] = color
        if locale:
            params["locale"] = locale

        return await self.make_request("search", params=params)

    async def get_photo(self, photo_id: int) -> dict[str, Any]:
        """
        Get details of a specific photo by ID

        Args:
            photo_id: Pexels photo ID

        Returns:
            Dict containing photo details
        """
        return await self.make_request(f"photos/{photo_id}")

    async def get_curated_photos(self, per_page: int = 80, page: int = 1) -> dict[str, Any]:
        """
        Get curated photos from Pexels

        Args:
            per_page: Number of results per page (default: 15, max: 80)
            page: Page number (default: 1, max: 1000)

        Returns:
            Dict containing curated photos
        """
        params = {
            "per_page": min(per_page, 80),  # Max 80 per page
            "page": min(page, 1000),  # Max 1000 pages
        }

        return await self.make_request("curated", params=params)

    async def search_videos(
        self,
        query: str,
        per_page: int = 15,
        page: int = 1,
        min_width: int | None = None,
        min_height: int | None = None,
        min_duration: int | None = None,
        max_duration: int | None = None,
        orientation: str | None = None,
        size: str | None = None,
        locale: str | None = None,
    ) -> dict[str, Any]:
        """
        Search for videos using the Pexels API

        Args:
            query: Search query (required)
            per_page: Number of results per page (default: 15, max: 80)
            page: Page number (default: 1, max: 1000)
            min_width: Minimum video width in pixels
            min_height: Minimum video height in pixels
            min_duration: Minimum video duration in seconds
            max_duration: Maximum video duration in seconds
            orientation: Video orientation ("landscape", "portrait", "square")
            size: Video size ("large", "medium", "small")
            locale: Locale for the search

        Returns:
            Dict containing search results with videos, pagination info, etc.
        """
        params = {
            "query": query,
            "per_page": min(per_page, 80),  # Max 80 per page
            "page": min(page, 1000),  # Max 1000 pages
        }

        # Add optional parameters
        if min_width:
            params["min_width"] = int(min_width)
        if min_height:
            params["min_height"] = int(min_height)
        if min_duration:
            params["min_duration"] = int(min_duration)
        if max_duration:
            params["max_duration"] = int(max_duration)
        if orientation:
            params["orientation"] = orientation
        if size:
            params["size"] = size
        if locale:
            params["locale"] = locale

        return await self.make_request("videos/search", params=params)

    async def get_video(self, video_id: int) -> dict[str, Any]:
        """
        Get details of a specific video by ID

        Args:
            video_id: Pexels video ID

        Returns:
            Dict containing video details
        """
        return await self.make_request(f"videos/videos/{video_id}")

    async def get_popular_videos(
        self,
        per_page: int = 15,
        page: int = 1,
        min_width: int | None = None,
        min_height: int | None = None,
        min_duration: int | None = None,
        max_duration: int | None = None,
        orientation: str | None = None,
    ) -> dict[str, Any]:
        """
        Get popular videos from Pexels

        Args:
            per_page: Number of results per page (default: 15, max: 80)
            page: Page number (default: 1, max: 1000)
            min_width: Minimum video width in pixels
            min_height: Minimum video height in pixels
            min_duration: Minimum video duration in seconds
            max_duration: Maximum video duration in seconds
            orientation: Video orientation ("landscape", "portrait", "square")

        Returns:
            Dict containing popular videos
        """
        params = {
            "per_page": str(min(per_page, 80)),  # Max 80 per page
            "page": str(min(page, 1000)),  # Max 1000 pages
        }

        # Add optional parameters
        if min_width is not None:
            params["min_width"] = str(min_width)
        if min_height is not None:
            params["min_height"] = str(min_height)
        if min_duration is not None:
            params["min_duration"] = str(min_duration)
        if max_duration is not None:
            params["max_duration"] = str(max_duration)
        if orientation is not None and isinstance(orientation, str):
            params["orientation"] = orientation

        return await self.make_request("videos/popular", params=params)

    async def get_collections(self, per_page: int = 15, page: int = 1) -> dict[str, Any]:
        """
        Get featured collections from Pexels

        Args:
            per_page: Number of results per page (default: 15, max: 80)
            page: Page number (default: 1, max: 1000)

        Returns:
            Dict containing collections
        """
        params = {
            "per_page": min(per_page, 80),  # Max 80 per page
            "page": min(page, 1000),  # Max 1000 pages
        }

        return await self.make_request("collections/featured", params=params)

    async def get_collection_media(
        self,
        collection_id: str,
        per_page: int = 15,
        page: int = 1,
        _type: str | None = None,
    ) -> dict[str, Any]:
        """
        Get media from a specific collection

        Args:
            collection_id: Collection ID
            per_page: Number of results per page (default: 15, max: 80)
            page: Page number (default: 1, max: 1000)
            type: Media type ("photos" or "videos")

        Returns:
            Dict containing collection media
        """
        params = {
            "per_page": str(min(per_page, 80)),  # Max 80 per page
            "page": str(min(page, 1000)),  # Max 1000 pages
        }

        if _type is not None and isinstance(_type, str):
            params["type"] = _type

        return await self.make_request(f"collections/{collection_id}", params=params)

    # Helper methods for common use cases
    async def get_random_photos(self, query: str, count: int = 80, orientation: str | None = None) -> list[dict[str, Any]]:
        """
        Get random photos for a query

        Args:
            query: Search query
            count: Number of photos to return

        Returns:
            List of photo dictionaries
        """
        result = await self.search_photos(query, per_page=min(count, 80), orientation=orientation)
        if result.get("status_code") == 200 and "photos" in result:
            return result["photos"][:count]
        return []

    async def download_photo_url(self, photo: dict[str, Any], size: str = "large") -> str | None:
        """
        Get download URL for a photo

        Args:
            photo: Photo dictionary from API response
            size: Size variant ("original", "large2x", "large", "medium", "small", "portrait", "landscape", "tiny")

        Returns:
            Download URL string or None
        """
        if "src" in photo and size in photo["src"]:
            return photo["src"][size]
        return None

    async def download_b64_photo(self, query: str) -> str | None:
        """
        Get base64 encoded image for a query

        Args:
            query: Search query
        Returns:
            Base64 encoded image string or None
        """
        photos = await self.get_random_photos(query, count=1)
        if photos and len(photos) > 0:
            photo_url = await self.download_photo_url(photos[0], size="medium")
            if photo_url:
                async with aiohttp.ClientSession() as session, session.get(photo_url) as resp:
                    if resp.status == 200:
                        img_data = await resp.read()
                        b64_data = base64.b64encode(img_data).decode("ascii")
                        return f"data:image/jpeg;base64,{b64_data}"
        return None
