from apps.odoosales.utils.odoo import OdooClient
from common.logger import logger


async def setup_company_profile():
    async with OdooClient() as client:
        try:
            company_id = await client.write(
                "res.company",
                1,
                {
                    "name": "Modern Market Co.",
                    "street": "782 Elm Street",
                    "city": "Austin",
                    "state_id": 52,
                    "country_id": 233,  # United States
                    "zip": 73301,
                    "email": "hello@modernmarket.com",
                    "vat": "12-3456789",
                },
            )
            logger.succeed("Company updated successfully")
            return company_id
        except Exception as e:
            raise ValueError(f"Error updating company: {e}")
