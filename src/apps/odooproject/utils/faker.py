import random

from faker import Faker
from faker.providers import BaseProvider


US_COLLEGES = [
    "Harvard University",
    "Stanford University",
    "Massachusetts Institute of Technology",
    "University of California, Berkeley",
    "California Institute of Technology",
    "Princeton University",
    "Yale University",
    "Columbia University",
    "University of Chicago",
    "University of Pennsylvania",
    "Duke University",
    "Johns Hopkins University",
    "Northwestern University",
    "University of Michigan, Ann Arbor",
    "Cornell University",
    "University of California, Los Angeles",
    "New York University",
    "University of California, San Diego",
    "University of Wisconsin-Madison",
    "University of Washington",
]

US_BANKS = [
    "JPMorgan Chase",
    "Bank of America",
    "Wells Fargo",
    "Citibank",
    "U.S. Bank",
    "PNC Bank",
    "Truist Bank",
    "Goldman Sachs Bank USA",
    "TD Bank",
    "Capital One",
    "HSBC Bank USA",
    "Fifth Third Bank",
    "Ally Bank",
    "KeyBank",
    "Regions Bank",
    "BMO Harris Bank",
    "Huntington National Bank",
    "Citizens Bank",
    "First Republic Bank",
    "M&T Bank",
]

CONSUMER_GOODS_FIELDS = [
    "Supply Chain Management",
    "Logistics and Transportation",
    "Industrial Engineering",
    "Manufacturing Engineering",
    "Food Science and Technology",
    "Packaging Science",
    "Quality Assurance/Quality Control",
    "Consumer Behavior",
    "Retail Management",
    "Marketing",
    "Product Design and Development",
    "Chemical Engineering",
    "Business Administration",
    "Operations Management",
    "Environmental Science",
    "Textile Engineering",
    "Sales and Merchandising",
    "International Business",
    "Human Resource Management",
    "Finance and Accounting",
]


class CustomContact(BaseProvider):
    def contact(self):
        first_name = faker.first_name()
        last_name = faker.last_name()
        full_name = f"{first_name} {last_name}"
        email = f"{first_name.lower()}_{last_name.lower()}@deeptune.ai"
        private_email = f"{first_name.lower()}_{faker.random_int(min=1000, max=9999)}@gmail.com"
        birthday = faker.date_of_birth(minimum_age=18, maximum_age=65)
        # Generate a phone number in the format '+1 212 555 4567'
        country_code = "+1"
        area_code = faker.random_int(min=200, max=999)
        exchange_code = faker.random_int(min=100, max=999)
        subscriber_number = faker.random_int(min=1000, max=9999)
        phone = f"{country_code} {area_code} {exchange_code} {subscriber_number}"
        address = {
            "street": faker.street_address(),
            "street2": faker.secondary_address(),
            "city": faker.city(),
            "state": faker.state_abbr(),
            "zip": faker.zipcode(),
            "country": "US",
        }
        visa_no = "".join(random.choices("ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789", k=8))
        work_permit_no = "".join(random.choices("ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789", k=9))
        visa_expiration_date = faker.date_between(start_date="+1y", end_date="+5y").strftime("%Y-%m-%d")
        work_permit_expiration_date = faker.date_between(start_date="+1y", end_date="+5y").strftime("%Y-%m-%d")
        return {
            "full_name": full_name,
            "email": email,
            "private_email": private_email,
            "birthday": birthday,
            "phone": phone,
            "address": address,
            "city": faker.city(),
            "school": random.choice(US_COLLEGES),
            "visa_no": visa_no,
            "work_permit_no": work_permit_no,
            "visa_expiration_date": visa_expiration_date,
            "work_permit_expiration_date": work_permit_expiration_date,
            "bank_name": random.choice(US_BANKS),
            "field_of_study": random.choice(CONSUMER_GOODS_FIELDS),
        }


faker = Faker()
faker.add_provider(CustomContact)
