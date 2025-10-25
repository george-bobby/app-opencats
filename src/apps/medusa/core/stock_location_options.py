import asyncio
from typing import Any

import aiohttp
from tenacity import retry, stop_after_attempt, wait_exponential

from apps.medusa.utils.api_utils import MedusaAPIUtils
from common.logger import logger


async def fetch_shipping_option_types(session: aiohttp.ClientSession, auth, base_url: str) -> str | None:
    """Fetch shipping option types."""
    try:
        url = f"{base_url}/admin/shipping-option-types"
        headers = auth.get_auth_headers()
        params = {"limit": 10, "offset": 0}

        async with session.get(url, headers=headers, params=params) as response:
            if response.status == 200:
                data = await response.json()
                types = data.get("shipping_option_types", [])
                if types:
                    return types[0].get("id")
            return None
    except Exception:
        return None


async def get_fulfillment_sets(location_id: str, location_name: str, session: aiohttp.ClientSession, auth, base_url: str) -> dict[str, str]:
    """Get existing fulfillment sets for a stock location."""
    try:
        url = f"{base_url}/admin/stock-locations/{location_id}"
        headers = auth.get_auth_headers()
        params = {"fields": "*fulfillment_sets"}

        async with session.get(url, headers=headers, params=params) as response:
            if response.status == 200:
                data = await response.json()
                stock_location = data.get("stock_location", {})
                fulfillment_sets = stock_location.get("fulfillment_sets", [])

                expected_pickup_name = f"{location_name} pick up"
                expected_shipping_name = f"{location_name} shipping"

                existing_sets = {}
                for fs in fulfillment_sets:
                    fs_name = fs.get("name", "")
                    fs_type = fs.get("type", "").lower()
                    fs_id = fs.get("id")

                    if fs_name == expected_pickup_name or (fs_type == "pickup" and location_name in fs_name):
                        existing_sets["pickup"] = fs_id
                    elif fs_name == expected_shipping_name or (fs_type == "shipping" and location_name in fs_name):
                        existing_sets["shipping"] = fs_id

                return existing_sets
            return {}
    except Exception:
        return {}


async def get_service_zones(fulfillment_set_id: str, session: aiohttp.ClientSession, auth, base_url: str) -> list[dict[str, Any]]:
    """Get service zones for a fulfillment set."""
    try:
        url = f"{base_url}/admin/fulfillment-sets/{fulfillment_set_id}"
        headers = auth.get_auth_headers()
        params = {"fields": "*service_zones"}

        async with session.get(url, headers=headers, params=params) as response:
            if response.status == 200:
                data = await response.json()
                fulfillment_set = data.get("fulfillment_set", {})
                return fulfillment_set.get("service_zones", [])
            return []
    except Exception:
        return []


async def connect_sales_channels(location_id: str, channel_ids: list[str], session: aiohttp.ClientSession, auth, base_url: str) -> bool:
    """Connect sales channels to stock location."""
    if not channel_ids:
        return True

    try:
        url = f"{base_url}/admin/stock-locations/{location_id}/sales-channels"
        headers = auth.get_auth_headers()
        payload = {"add": channel_ids, "remove": []}

        async with session.post(url, json=payload, headers=headers) as response:
            return response.status in [200, 201]
    except Exception:
        return False


async def connect_fulfillment_providers(location_id: str, session: aiohttp.ClientSession, auth, base_url: str) -> bool:
    """Connect fulfillment providers to stock location."""
    try:
        url = f"{base_url}/admin/stock-locations/{location_id}/fulfillment-providers"
        headers = auth.get_auth_headers()
        payload = {"add": ["manual_manual"], "remove": []}

        async with session.post(url, json=payload, headers=headers) as response:
            return response.status in [200, 201]
    except Exception:
        return False


async def setup_pickup(
    location_id: str,
    location_name: str,
    shipping_profile_id: str,
    shipping_option_type_id: str | None,
    existing_fulfillment_sets: dict[str, str],
    session: aiohttp.ClientSession,
    auth,
    base_url: str,
) -> bool:
    """Setup pickup fulfillment set and shipping options."""
    try:
        headers = auth.get_auth_headers()

        if "pickup" in existing_fulfillment_sets:
            pickup_fulfillment_set_id = existing_fulfillment_sets["pickup"]
        else:
            url = f"{base_url}/admin/stock-locations/{location_id}/fulfillment-sets"
            payload = {"name": f"{location_name} pick up", "type": "pickup"}

            async with session.post(url, json=payload, headers=headers) as response:
                if response.status not in [200, 201]:
                    return False

            fulfillment_sets = await get_fulfillment_sets(location_id, location_name, session, auth, base_url)
            pickup_fulfillment_set_id = fulfillment_sets.get("pickup")

            if not pickup_fulfillment_set_id:
                return False

        existing_zones = await get_service_zones(pickup_fulfillment_set_id, session, auth, base_url)

        pickup_service_zone_id = None
        for zone in existing_zones:
            if zone.get("name") == "Urban Express Pickup":
                pickup_service_zone_id = zone.get("id")
                break

        if not pickup_service_zone_id:
            url = f"{base_url}/admin/fulfillment-sets/{pickup_fulfillment_set_id}/service-zones"
            payload = {"name": "Urban Express Pickup", "geo_zones": [{"country_code": "us", "type": "country"}]}

            async with session.post(url, json=payload, headers=headers) as response:
                if response.status not in [200, 201]:
                    return False

                data = await response.json()
                if "fulfillment_set" in data:
                    fulfillment_set = data["fulfillment_set"]
                    service_zones = fulfillment_set.get("service_zones", [])
                    if service_zones:
                        pickup_service_zone_id = service_zones[0].get("id")

                if not pickup_service_zone_id:
                    return False

        url = f"{base_url}/admin/shipping-options"
        prices = [{"currency_code": "eur", "amount": 0}, {"currency_code": "usd", "amount": 0}]

        payload = {
            "name": "Storefront Pickup",
            "price_type": "flat",
            "service_zone_id": pickup_service_zone_id,
            "shipping_profile_id": shipping_profile_id,
            "provider_id": "manual_manual",
            "prices": prices,
            "data": {"id": "manual-fulfillment"},
            "rules": [
                {"value": "false", "attribute": "is_return", "operator": "eq"},
                {"value": "true", "attribute": "enabled_in_store", "operator": "eq"},
            ],
        }

        if shipping_option_type_id:
            payload["type_id"] = shipping_option_type_id

        await session.post(url, json=payload, headers=headers)

        payload = {
            "name": "In-Store Return",
            "price_type": "flat",
            "service_zone_id": pickup_service_zone_id,
            "shipping_profile_id": shipping_profile_id,
            "provider_id": "manual_manual",
            "prices": prices,
            "data": {"id": "manual-fulfillment-return", "is_return": True},
            "rules": [
                {"value": "true", "attribute": "is_return", "operator": "eq"},
                {"value": "true", "attribute": "enabled_in_store", "operator": "eq"},
            ],
        }

        if shipping_option_type_id:
            payload["type_id"] = shipping_option_type_id

        await session.post(url, json=payload, headers=headers)

        return True

    except Exception:
        return False


async def setup_shipping(
    location_id: str,
    location_name: str,
    shipping_profile_id: str,
    shipping_option_type_id: str | None,
    existing_fulfillment_sets: dict[str, str],
    session: aiohttp.ClientSession,
    auth,
    base_url: str,
) -> bool:
    """Setup shipping fulfillment set and shipping options."""
    try:
        headers = auth.get_auth_headers()

        if "shipping" in existing_fulfillment_sets:
            shipping_fulfillment_set_id = existing_fulfillment_sets["shipping"]
        else:
            url = f"{base_url}/admin/stock-locations/{location_id}/fulfillment-sets"
            payload = {"name": f"{location_name} shipping", "type": "shipping"}

            async with session.post(url, json=payload, headers=headers) as response:
                if response.status not in [200, 201]:
                    return False

            fulfillment_sets = await get_fulfillment_sets(location_id, location_name, session, auth, base_url)
            shipping_fulfillment_set_id = fulfillment_sets.get("shipping")

            if not shipping_fulfillment_set_id:
                return False

        existing_zones = await get_service_zones(shipping_fulfillment_set_id, session, auth, base_url)

        shipping_service_zone_id = None
        for zone in existing_zones:
            if zone.get("name") == "National Shipping":
                shipping_service_zone_id = zone.get("id")
                break

        if not shipping_service_zone_id:
            url = f"{base_url}/admin/fulfillment-sets/{shipping_fulfillment_set_id}/service-zones"
            payload = {"name": "National Shipping", "geo_zones": [{"country_code": "us", "type": "country"}]}

            async with session.post(url, json=payload, headers=headers) as response:
                if response.status not in [200, 201]:
                    return False

                data = await response.json()
                if "fulfillment_set" in data:
                    fulfillment_set = data["fulfillment_set"]
                    service_zones = fulfillment_set.get("service_zones", [])
                    if service_zones:
                        shipping_service_zone_id = service_zones[0].get("id")

                if not shipping_service_zone_id:
                    return False

        url = f"{base_url}/admin/shipping-options"

        payload = {
            "name": "Standard Shipping",
            "price_type": "flat",
            "service_zone_id": shipping_service_zone_id,
            "shipping_profile_id": shipping_profile_id,
            "provider_id": "manual_manual",
            "prices": [{"currency_code": "usd", "amount": 5}],
            "data": {"id": "manual-fulfillment"},
            "rules": [
                {"value": "false", "attribute": "is_return", "operator": "eq"},
                {"value": "true", "attribute": "enabled_in_store", "operator": "eq"},
            ],
        }

        if shipping_option_type_id:
            payload["type_id"] = shipping_option_type_id

        await session.post(url, json=payload, headers=headers)

        payload = {
            "name": "Scheduled Carrier Pickup",
            "price_type": "flat",
            "service_zone_id": shipping_service_zone_id,
            "shipping_profile_id": shipping_profile_id,
            "provider_id": "manual_manual",
            "prices": [{"currency_code": "usd", "amount": 5}],
            "data": {"id": "manual-fulfillment-return", "is_return": True},
            "rules": [
                {"value": "true", "attribute": "is_return", "operator": "eq"},
                {"value": "true", "attribute": "enabled_in_store", "operator": "eq"},
            ],
        }

        if shipping_option_type_id:
            payload["type_id"] = shipping_option_type_id

        await session.post(url, json=payload, headers=headers)

        return True

    except Exception:
        return False


async def seed_stock_location_options_internal(
    location_id: str,
    location_name: str,
    shipping_profile_id: str,
    channel_ids: list[str],
    session: aiohttp.ClientSession,
    auth,
    base_url: str,
) -> dict[str, int]:
    """Internal function to setup stock location options."""
    logger.info(f"Setting up stock location options: {location_name}")

    successful = 0
    failed = 0
    total = 4

    shipping_option_type_id = await fetch_shipping_option_types(session, auth, base_url)
    existing_fulfillment_sets = await get_fulfillment_sets(location_id, location_name, session, auth, base_url)

    if await connect_sales_channels(location_id, channel_ids, session, auth, base_url):
        successful += 1
    else:
        failed += 1

    if await connect_fulfillment_providers(location_id, session, auth, base_url):
        successful += 1
    else:
        failed += 1

    if await setup_pickup(location_id, location_name, shipping_profile_id, shipping_option_type_id, existing_fulfillment_sets, session, auth, base_url):
        successful += 1
    else:
        failed += 1

    if await setup_shipping(location_id, location_name, shipping_profile_id, shipping_option_type_id, existing_fulfillment_sets, session, auth, base_url):
        successful += 1
    else:
        failed += 1

    logger.info(f"Stock location options setup: {successful} successful, {failed} failed")

    return {"total": total, "successful": successful, "failed": failed}


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=10))
async def seed_stock_location_options() -> dict[str, int]:
    """Setup stock location options including fulfillment sets and shipping options."""
    async with MedusaAPIUtils() as api_utils:
        stock_locations = await api_utils.fetch_stock_locations()

        if not stock_locations:
            logger.warning("No stock locations found")
            return {"total": 0, "successful": 0, "failed": 0}

        location = stock_locations[0]
        location_id = location.get("id")
        location_name = location.get("name", "Unknown")

        if not location_id:
            return {"total": 0, "successful": 0, "failed": 0}

        sales_channels = await api_utils.fetch_sales_channels()
        channel_ids = [ch["id"] for ch in sales_channels if "id" in ch]

        shipping_profiles = await api_utils.fetch_shipping_profiles()
        shipping_profile_map = {profile.get("name", ""): profile.get("id") for profile in shipping_profiles if profile.get("id")}

        shipping_profile_id = shipping_profile_map.get("Standard Shipping") or (next(iter(shipping_profile_map.values())) if shipping_profile_map else None)

        if not shipping_profile_id:
            logger.warning("No shipping profile found")
            return {"total": 0, "successful": 0, "failed": 0}

        async with aiohttp.ClientSession() as session:
            return await seed_stock_location_options_internal(
                location_id,
                location_name,
                shipping_profile_id,
                channel_ids,
                session,
                api_utils.auth,
                api_utils.base_url,
            )


if __name__ == "__main__":
    asyncio.run(seed_stock_location_options())
