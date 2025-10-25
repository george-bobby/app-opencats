from faker import Faker
from faker.providers import BaseProvider


class CustomProvider(BaseProvider):
    def phone_number_e164(self):
        return "+1" + self.numerify("##########")


faker = Faker()
faker.add_provider(CustomProvider)
