"""
Backfill Odoo public holidays for the US in the current year.
"""

from datetime import date

from apps.odoohr.utils.odoo import OdooClient
from common.logger import logger


US_PUBLIC_HOLIDAYS = [
    ("New Year's Day", (1, 1)),
    ("Martin Luther King Jr. Day", (1, 20)),
    ("Presidents Day", (2, 17)),
    ("Memorial Day", (5, 26)),
    ("Independence Day", (7, 4)),
    ("Labor Day", (9, 1)),
    ("Columbus Day", (10, 13)),
    ("Veterans Day", (11, 11)),
    ("Thanksgiving Day", (11, 27)),
    ("Christmas Day", (12, 25)),
]


async def insert_public_holidays(year=None):
    """
    Insert 10 US Federal and common regional public holidays for the given year into Odoo.
    """
    if year is None:
        year = date.today().year

    logger.start(f"Inserting 10 public holidays for {year}")
    async with OdooClient() as client:
        public_holidays_to_create = []
        for name, (month, day) in US_PUBLIC_HOLIDAYS:
            public_holidays_to_create.append(
                {
                    "name": name,
                    "date_from": f"{year}-{month:02d}-{day:02d} 00:00:00",
                    "date_to": f"{year}-{month:02d}-{day:02d} 23:59:59",
                },
            )
        await client.create("resource.calendar.leaves", [public_holidays_to_create])
    logger.succeed(f"Inserted 10 public holidays for {year}")
