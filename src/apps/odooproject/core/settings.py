from apps.odooproject.config.constants import DEFAULT_COMPANY_ID, ResModelName
from apps.odooproject.config.settings import settings
from apps.odooproject.utils.odoo import OdooClient
from common.img_to_b64 import img_to_b64
from common.logger import logger


async def insert_settings():
    logger.start("Inserting settings into Odoo...")
    async with OdooClient() as client:
        setting_id = await client.create(
            ResModelName.RES_CONFIG_SETTINGS.value,
            {"group_project_task_dependencies": True, "group_project_stages": True},
        )

        await client.execute_kw(ResModelName.RES_CONFIG_SETTINGS.value, "execute", [setting_id])

        default_partner = await client.search_read(
            ResModelName.RES_PARTNER.value,
            [("email", "=", settings.ODOO_USERNAME)],
            ["id"],
            limit=1,
        )

        if default_partner:
            await client.write(ResModelName.RES_PARTNER.value, default_partner[0]["id"], {"name": settings.SYSTEM_USER})

        await client.write(
            ResModelName.RES_COMPANY.value,
            DEFAULT_COMPANY_ID,
            {
                "name": settings.COMPANY_NAME,
                "logo": img_to_b64(settings.COMPANY_LOGO),
            },
        )

    logger.succeed("Inserted settings successfully.")
