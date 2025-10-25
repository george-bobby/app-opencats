from supabase import AsyncClient, create_async_client

from apps.supabase.config.settings import settings


async def get_supabase_client():
    client: AsyncClient = await create_async_client(settings.SUPABASE_PUBLIC_URL, settings.SERVICE_ROLE_KEY)
    return client
