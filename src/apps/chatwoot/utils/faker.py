from faker import Faker
from faker.providers import BaseProvider

from apps.chatwoot.config.settings import settings


class CustomProvider(BaseProvider):
    def company_email(
        self,
        first_name: str,
        last_name: str,
        domain: str = "".join(c for c in settings.COMPANY_NAME if c.isalnum()).lower() + ".com",
    ) -> str:
        return f"{first_name.lower()}.{last_name.lower()}@{domain}"

    def normal_company_name(self) -> str:
        return faker.company().replace("-", " ").replace(",", "").replace("and", "&")

    def normal_random_date(self, start_date: str, end_date: str) -> str:
        while True:
            date = faker.date_time_between(start_date=start_date, end_date=end_date)
            # If it's a weekday (0 = Monday, 6 = Sunday)
            if date.weekday() < 5:
                # 100% chance to accept weekday
                return date
            else:
                # 30% chance to accept weekend
                if faker.random.random() < 0.3:
                    return date


faker = Faker(locale="en_US")
faker.add_provider(CustomProvider)
