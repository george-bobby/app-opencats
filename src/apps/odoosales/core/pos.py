from apps.odoosales.config.constants import POSModelName
from apps.odoosales.utils.odoo import OdooClient
from common.logger import logger


async def setup_pos_profile():
    logger.start("Setting up Point of Sale profile...")
    async with OdooClient() as client:
        try:
            pos_config_id = await client.create(POSModelName.POS_CONFIG.value, {"name": "Modern Market POS"})
            logger.succeed("Inserted POS profile successfully.")
            return pos_config_id
        except Exception as e:
            logger.fail(f"Error setting up POS profile: {e}")
            raise ValueError(f"Error setting up POS profile: {e}")
