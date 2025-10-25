from collections import OrderedDict

from faker import Faker
from faker.providers import BaseProvider


class FakerProvider(BaseProvider):
    def first_world_country(self):
        european_countries = [
            "France",
            "Germany",
            "Italy",
            "Spain",
            "Netherlands",
            "Belgium",
            "Sweden",
            "Poland",
            "Austria",
            "Denmark",
            "Finland",
            "Ireland",
            "Portugal",
            "Greece",
        ]

        choices = OrderedDict(
            [
                ("United States", 0.8),
                (self.generator.random_element(european_countries), 0.2),
            ]
        )

        return self.generator.random_element(choices)


faker = Faker(locale="en_US")
faker.add_provider(FakerProvider)
