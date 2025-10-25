from apps.odoosales.config.constants import ResModelName
from apps.odoosales.config.settings import settings
from apps.odoosales.utils.odoo import OdooClient
from common.img_to_b64 import img_to_b64
from common.logger import logger


async def setup_config():
    logger.start("Setting up configuration...")
    async with OdooClient() as client:
        try:
            settings_id = await client.create(
                ResModelName.RES_CONFIG_SETTINGS.value,
                {
                    "group_product_variant": True,
                    "group_product_pricelist": True,
                    "group_use_lead": True,
                },
            )

            await client.execute_kw(ResModelName.RES_CONFIG_SETTINGS.value, "execute", [settings_id])

            default_partner = await client.search_read(
                ResModelName.RES_PARTNER.value,
                [("email", "=", settings.ODOO_USERNAME)],
                ["id"],
                limit=1,
            )

            if default_partner:
                await client.write(ResModelName.RES_PARTNER.value, default_partner[0]["id"], {"name": settings.SYSTEM_USER})

            await client.write(ResModelName.RES_COMPANY.value, 1, {"name": settings.COMPANY_NAME, "logo": img_to_b64(settings.COMPANY_LOGO)})
            logger.succeed("Configuration setup completed successfully.")
        except Exception as e:
            raise ValueError(f"Error setting up configuration: {e}")
