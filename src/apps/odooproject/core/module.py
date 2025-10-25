from apps.odooproject.utils.odoo import OdooClient
from common.logger import logger


ODOO_APPS = ["project"]


async def activate_modules():
    logger.start("Activating Odoo modules...")
    async with OdooClient() as client:
        try:
            modules = await client.search_read("ir.module.module", [("name", "in", ODOO_APPS)], ["id"])

            await client.execute_kw(
                "ir.module.module",
                "button_immediate_install",
                [module["id"] for module in modules],
            )

            logger.succeed(f"Activated modules: {', '.join(ODOO_APPS)}")
        except Exception as e:
            logger.fail(f"Error activating modules: {e}")
            raise
