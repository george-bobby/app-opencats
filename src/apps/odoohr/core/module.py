"""Activates required Odoo HR modules."""

from apps.odoohr.utils.odoo import OdooClient
from common.logger import logger


ODOO_APPS = ["hr", "hr_holidays", "hr_recruitment", "hr_skills"]


async def activate_modules():
    logger.start(f"Activating modules: {', '.join(ODOO_APPS)}")
    async with OdooClient() as client:
        try:
            modules = await client.search_read(
                "ir.module.module",
                [("name", "in", ODOO_APPS)],
                ["id"],
            )

            for module in modules:
                await client.execute_kw(
                    "ir.module.module",
                    "button_immediate_install",
                    [module["id"]],
                )
            logger.succeed(f"Activated modules: {', '.join(ODOO_APPS)}")
        except Exception as e:
            raise ValueError(f"Error activating modules: {e}")
