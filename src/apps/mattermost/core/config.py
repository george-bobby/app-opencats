import contextlib

import aiohttp

from apps.mattermost.config.settings import settings
from apps.mattermost.utils.mattermost import MattermostClient
from common.load_json import load_json
from common.logger import logger


async def initialize():
    async with aiohttp.ClientSession() as session:
        # Create first user
        user_data = {
            "email": settings.MATTERMOST_EMAIL,
            "username": settings.MATTERMOST_OWNER_USERNAME,
            "password": settings.MATTERMOST_PASSWORD,
            "first_name": settings.MATTERMOST_OWNER_FIRST_NAME,
            "last_name": settings.MATTERMOST_OWNER_LAST_NAME,
            "nickname": settings.MATTERMOST_OWNER_NICKNAME,
            "position": settings.MATTERMOST_OWNER_POSITION,
        }

        url = f"{settings.MATTERMOST_URL}/api/v4/users"
        headers = {
            "Content-Type": "application/json",
        }

        try:
            async with session.post(url, json=user_data, headers=headers) as response:
                if response.status == 201:
                    user_info = await response.json()
                    return user_info
                else:
                    error_text = await response.text()
                    logger.fail(f"✖ Failed to create first user: {response.status} - {error_text}")
                    return None
        except Exception as e:
            logger.fail(f"✖ Error creating first user: {e}")
            return None


async def setup_configuration():
    """
    Setup Mattermost configuration for Vertexon Solutions.

    This function configures:
    - Site Configuration: URL, name, company details
    - Email Settings: SMTP configuration for vertexon.io domain
    - Integration Settings: Webhooks, bots, security settings
    - Licensing: Free plan simulation for SMB setup

    """
    config = load_json(settings.DATA_PATH.joinpath("config.json"))
    logger.start("Setting up Mattermost configuration for Vertexon Solutions...")

    async with MattermostClient() as client:
        try:
            config_data = {
                "site_configuration": {
                    "site_url": config["site_configuration"]["site_url"],
                    "site_name": config["site_configuration"]["site_name"],
                    "company_name": config["site_configuration"]["company_name"],
                    "enable_signup": False,
                    "enable_open_server": False,
                },
                "email_settings": {
                    "smtp_server": config["email_settings"]["smtp_server"],
                    "smtp_port": config["email_settings"]["smtp_port"],
                    "smtp_username": config["email_settings"]["smtp_username"],
                    "smtp_password": config["email_settings"]["smtp_password"],
                    "smtp_security": config["email_settings"]["smtp_security"],
                    "feedback_email": config["email_settings"]["feedback_email"],
                    "feedback_name": config["email_settings"]["feedback_name"],
                },
                "integration_settings": {
                    "incoming_webhooks": config["integrations"]["incoming_webhooks"]["enabled"],
                    "outgoing_webhooks": config["integrations"]["outgoing_webhooks"]["enabled"],
                    "bot_accounts": config["integrations"]["bot_accounts"]["enabled"],
                    "slash_commands": config["integrations"]["slash_commands"]["enabled"],
                    "oauth_applications": config["integrations"]["oauth_applications"]["enabled"],
                },
            }

            result = await client.update_complete_configuration(config_data)
            if not result:
                raise Exception("Failed to update configuration")

            # update profile picture for the administrator
            sys_admin = await client.get_user_by_username(settings.MATTERMOST_OWNER_USERNAME)
            if sys_admin:
                avatar_path = settings.DATA_PATH.joinpath("admin-avatar.jpg")
                with contextlib.suppress(Exception):
                    if avatar_path.exists():
                        await client.upload_user_avatar(sys_admin["id"], avatar_path)

            logger.succeed("Mattermost configuration setup completed for Vertexon Solutions")
        except Exception as e:
            logger.error(f"Failed to setup configuration: {e}")
            raise
