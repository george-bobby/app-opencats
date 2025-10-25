import json
import random
from collections import OrderedDict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from faker import Faker

from apps.frappehrms.config.settings import settings
from apps.frappehrms.core import companies
from apps.frappehrms.utils import frappe_client
from common.logger import logger


fake = Faker()


# List of real US banks
US_BANKS = [
    "JPMorgan Chase Bank",
    "Bank of America",
    "Wells Fargo Bank",
    "Citibank",
    "U.S. Bank",
    "Truist Bank",
    "PNC Bank",
    "TD Bank",
    "Capital One",
    "Goldman Sachs Bank",
    "Fifth Third Bank",
    "Citizens Bank",
    "KeyBank",
    "Regions Bank",
    "BMO Harris Bank",
    "Huntington National Bank",
    "Ally Bank",
    "HSBC Bank USA",
    "Santander Bank",
    "M&T Bank",
]


def generate_employee_data(company: dict[str, str], department: list[str], designations: list[str]) -> dict[str, Any]:
    """Generate a single employee's data."""
    gender = random.choice(["Male", "Female"])
    first_name = fake.first_name_male() if gender == "Male" else fake.first_name_female()
    last_name = fake.last_name()
    inital_status = fake.random_element(
        OrderedDict(
            [
                ("Active", 0.7),
                ("Left", 0.1),
                ("Inactive", 0.1),
                ("Suspended", 0.1),
            ]
        ),
    )

    # Generate a realistic joining date within the last 5 years
    joining_date = fake.date_between(start_date="-5y", end_date="today")

    # Add relieving date if status is inactive
    relieving_date = fake.date_between(start_date=joining_date, end_date="today")

    # Generate a realistic date of birth (between 22 and 65 years old)
    dob = fake.date_between(
        start_date=datetime.now() - timedelta(days=65 * 365),
        end_date=datetime.now() - timedelta(days=22 * 365),
    )

    domain = "".join(c for c in company.get("name", "") if c.isalnum()).lower() + ".com"
    # Categorize designations into tiers
    c_suite_designations = [d for d in designations if d.startswith("Chief") or "Officer" in d]
    manager_designations = [d for d in designations if "Manager" in d or "Head" in d or "Head of" in d]
    regular_designations = [d for d in designations if d not in c_suite_designations and d not in manager_designations]

    # Use weighted probabilities to select designation tier
    designation_tier = random.choices(
        ["c_suite", "manager", "regular"],
        weights=[0.05, 0.15, 0.8],  # 5% C-suite, 15% managers, 80% regular employees
        k=1,
    )[0]

    # Select from the appropriate tier, falling back if necessary
    if designation_tier == "c_suite" and c_suite_designations:
        designation = random.choice(c_suite_designations)
    elif designation_tier == "manager" and manager_designations:
        designation = random.choice(manager_designations)
    elif regular_designations:
        designation = random.choice(regular_designations)
    else:
        # Fallback to any designation if categorization failed
        designation = random.choice(designations)

    # Find a suitable department based on designation
    matching_department = find_matching_department(designation, department)

    # Generate contact information
    personal_email = f"{first_name.lower()}.{last_name.lower()}@{fake.free_email_domain()}"
    company_email = f"{first_name.lower()}.{last_name.lower()}@{domain}"
    prefered_contact_email = "Company Email"  # Default as requested
    cell_number = fake.numerify(text="(###) ###-####")  # Exactly 10 digits
    current_address = fake.address()

    return {
        "doctype": "Employee",
        "first_name": first_name,
        "last_name": last_name,
        "gender": gender,
        "status": inital_status,
        "date_of_birth": dob.strftime("%Y-%m-%d"),
        "date_of_joining": joining_date.strftime("%Y-%m-%d"),
        "employment_type": random.choice(["Full-time", "Part-time", "Contract"]),
        "department": matching_department,
        "designation": designation,
        "email": company_email,
        "cell_number": cell_number,
        "personal_email": personal_email,
        "company_email": company_email,
        "prefered_contact_email": prefered_contact_email,
        "current_address": current_address,
        "emergency_contact_name": fake.name(),
        "emergency_contact": fake.numerify(text="(###) ###-####"),
        "bank_name": random.choice(US_BANKS),
        "bank_account_no": fake.credit_card_number(),
        "ifsc_code": fake.lexify(text="????0?????"),
        "company": company["name"],
        "relieving_date": relieving_date.strftime("%Y-%m-%d") if relieving_date else None,
        "marital_status": fake.random_element(
            OrderedDict(
                [
                    ("Single", 0.6),
                    ("Married", 0.4),
                    ("Divorced", 0.1),
                ]
            ),
        ),
    }


async def correct_employee_statuses():
    client = frappe_client.create_client()
    company = companies.get_default_company()
    employees = client.get_list(
        "Employee",
        limit_page_length=100000,
        fields=["name", "status", "designation"],
        filters=[["company", "=", company["name"]]],
    )
    logger.info(f"Found {len(employees)} employees")

    # Group employees by their exact designation title
    designation_groups = {}

    for employee in employees:
        designation = employee.get("designation", "")

        # Skip if no designation
        if not designation:
            continue

        # Check if this is a leadership position
        is_leadership = False
        designation_lower = designation.lower()

        if (
            "chief" in designation_lower
            or "officer" in designation_lower
            or "manager" in designation_lower
            or "director" in designation_lower
            or "head" in designation_lower
            or "head of" in designation_lower
        ):
            is_leadership = True

        # If this is a leadership position, add to the appropriate designation group
        if is_leadership:
            if designation not in designation_groups:
                designation_groups[designation] = []
            designation_groups[designation].append(employee)

    logger.info(f"Found {len(designation_groups)} distinct leadership titles")

    # For each leadership title, select one random employee to be active
    for title, title_employees in designation_groups.items():
        if len(title_employees) <= 0:
            continue

        # Select one random employee to be active
        active_employee = random.choice(title_employees)
        logger.info(f"Selected active '{title}' employee: {active_employee['name']}")

        # Update statuses for employees with this title
        for employee in title_employees:
            new_status = "Active" if employee["name"] == active_employee["name"] else "Inactive"

            # Only update if status needs to change
            if employee["status"] != new_status:
                try:
                    client.update(
                        {
                            "doctype": "Employee",
                            "name": employee["name"],
                            "status": new_status,
                        }
                    )
                    logger.info(f"Updated {employee['name']} status to {new_status}")
                except Exception as e:
                    logger.error(f"Failed to update status for {employee['name']}: {e!s}")

    logger.info("Employee status correction completed")


async def insert_employees(
    number_of_employees: int = 20,
) -> list[dict[str, Any]]:
    """
    Generate and insert employee data into Frappe HR.

    Args:
        number_of_employees (int): Number of employees to generate and insert

    Returns:
        List[Dict[str, Any]]: List of created employee documents
    """
    client = frappe_client.create_client()
    company = companies.get_default_company()
    company_name = company["name"]

    # Define the path to the employees JSON file
    employees_file_path = Path(__file__).parent.parent.joinpath("data", "generated", "employees.json")

    # Ensure the directory exists
    employees_file_path.parent.mkdir(parents=True, exist_ok=True)

    # Check if the file exists and has the required number of employees
    employee_data_list = []
    if employees_file_path.exists():
        logger.info("Found existing employees.json file, loading data from it")
        try:
            with employees_file_path.open(encoding="utf-8") as f:
                data = json.load(f)
                stored_employees = data.get("employees", [])
                stored_company = data.get("company_name", "")

                # Use stored data if it's for the same company and has enough employees
                if stored_company == company_name and len(stored_employees) >= number_of_employees:
                    employee_data_list = stored_employees[:number_of_employees]
                    logger.info(f"Using {len(employee_data_list)} employees from stored data")
                else:
                    logger.info("Stored data doesn't match current requirements, generating new data")
        except Exception as e:
            logger.error(f"Failed to read employees.json: {e!s}")
            logger.info("Falling back to new data generation")
    else:
        logger.info("employees.json file not found, generating new employee data")

    # If no suitable employee data loaded from file, generate new data
    if not employee_data_list:
        logger.info(f"Generating {number_of_employees} new employees")

        departments = [
            department["name"]
            for department in client.get_list(
                "Department",
                limit_page_length=settings.LIST_LIMIT,
                filters=[["company", "=", company_name]],
            )
        ]
        designations = [designation["name"] for designation in client.get_list("Designation")]

        # Generate the required number of employees
        for _ in range(number_of_employees):
            employee_data = generate_employee_data(company, departments, designations)
            employee_data_list.append(employee_data)

        # Save the generated employee data to the JSON file
        if employee_data_list:
            employees_cache_data = {
                "employees": employee_data_list,
                "company_name": company_name,
                "generated_count": number_of_employees,
                "theme_subject": settings.DATA_THEME_SUBJECT,
                "generated_at": datetime.now().isoformat(),
            }

            try:
                with employees_file_path.open("w", encoding="utf-8") as f:
                    json.dump(
                        employees_cache_data,
                        f,
                        indent=2,
                        ensure_ascii=False,
                        default=str,
                    )
                logger.info(f"Saved {len(employee_data_list)} employees to {employees_file_path}")
            except Exception as e:
                logger.error(f"Failed to save employees to file: {e!s}")

    # Insert the employee data (whether loaded from file or newly generated)
    for doc in employee_data_list:
        try:
            response = client.insert(doc)
            logger.info(f"Created employee: {response['name']}")
        except Exception as e:
            logger.error(f"Failed to create employee: {doc}")
            logger.error(f"Error message: {str(e).splitlines()[0]}")


async def update_employees_salary_data():
    """
    Update existing employees with salary data.
    """
    client = frappe_client.create_client()
    company = companies.get_default_company()
    employees = client.get_list(
        "Employee",
        limit_page_length=100000,
        fields=["name", "designation", "first_name", "last_name"],
        filters=[["company", "=", company["name"]]],
    )

    if not employees:
        logger.warning("No employees to update with salary data")
        return

    logger.info(f"Updating {len(employees)} employees with salary data")

    # Get all departments for the company
    departments = [
        department["name"]
        for department in client.get_list(
            "Department",
            limit_page_length=settings.LIST_LIMIT,
            filters=[["company", "=", company["name"]]],
        )
    ]

    for employee in employees:
        designation = employee.get("designation", "").lower()

        # Determine salary tier based on designation
        if "chief" in designation or "officer" in designation or "director" in designation:
            ctc = random.randint(150000, 300000)
        elif "manager" in designation or "head" in designation:
            ctc = random.randint(85000, 150000)
        else:
            ctc = random.randint(40000, 85000)

        # Generate bank details
        bank_name = random.choice(US_BANKS)
        bank_account = fake.numerify(text="#" * random.randint(8, 12))
        iban = f"US{fake.numerify(text='##')}BANK{fake.numerify(text='#' * 14)}"

        # Get employee first and last name
        first_name = employee.get("first_name", "")
        last_name = employee.get("last_name", "")

        # Extract domain from company email or generate one
        company_email = company.get("email", "")
        domain = "".join(c for c in company.get("name", "") if c.isalnum()).lower() + ".com"

        # Generate contact information if not already set
        personal_email = f"{first_name.lower()}.{last_name.lower()}@{fake.free_email_domain()}"
        company_email = f"{first_name.lower()}.{last_name.lower()}@{domain}"
        cell_number = fake.numerify(text="(###) ###-####")  # Exactly 10 digits
        current_address = fake.address()

        # Find appropriate department based on designation
        matching_department = find_matching_department(employee.get("designation", ""), departments)

        salary_update = {
            "doctype": "Employee",
            "name": employee["name"],
            "ctc": ctc,
            "salary_currency": "USD",
            "salary_mode": fake.random_element(["Cash", "Bank", "Cheque"]),
            "payroll_cost_center": f"Main - {company['abbr']}",
            "bank_name": bank_name,
            "bank_ac_no": bank_account,
            "iban": iban,
            "cell_number": cell_number,
            "personal_email": personal_email,
            "company_email": company_email,
            "prefered_contact_email": "Company Email",
            "current_address": current_address,
            "department": matching_department,
        }

        try:
            client.update(salary_update)
            logger.info(f"Updated salary and contact data for employee: {employee['name']}")
        except Exception as e:
            logger.error(f"Failed to update salary and contact data for employee: {employee['name']}")
            logger.error(f"Error message: {str(e).splitlines()[0]}")

    logger.info("Employee salary and contact data update completed")


async def delete_all_employees():
    client = frappe_client.create_client()
    employees = client.get_list("Employee", limit_page_length=100000, fields=["name"])

    if not employees:
        logger.warning("No employees to delete")
        return

    for employee in employees:
        logger.info(f"Deleting employee: {employee['name']}")
        try:
            client.delete("Employee", employee["name"])
        except Exception as e:
            logger.error(f"Failed to delete employee: {employee['name']}")
            logger.error(f"Error message: {str(e).splitlines()[0]}")


async def insert_promomotions(number_of_promotions: int = 10):
    client = frappe_client.create_client()
    employees = client.get_list(
        "Employee",
        limit_page_length=settings.LIST_LIMIT,
        fields=["name", "date_of_joining"],
        filters=[["status", "=", "Active"]],
    )
    promoted_employees = random.sample(employees, number_of_promotions)

    for employee in promoted_employees:
        # Convert the date string to datetime object
        joining_date = datetime.strptime(employee["date_of_joining"], "%Y-%m-%d")
        promotion_date = fake.date_between(start_date=joining_date, end_date="today")
        promotion_doc = {
            "doctype": "Employee Promotion",
            "employee": employee["name"],
            "promotion_date": promotion_date.strftime("%Y-%m-%d"),
            "docstatus": fake.random_element(
                OrderedDict(
                    [
                        (0, 0.3),
                        (1, 0.7),
                    ]
                ),
            ),
        }

        try:
            response = client.insert(promotion_doc)
            logger.info(f"Created promotion {response['name']}")
        except Exception as e:
            logger.error(f"Failed to create promotion: {promotion_doc}")
            logger.error(f"Error message: {str(e).splitlines()[0]}")

    # 10% of the employee promotions should be cancelled, use faker
    # Randomly select 10% of the promotions to be cancelled
    all_promotions = client.get_list(
        "Employee Promotion",
        limit_page_length=100000,
        fields=["name"],
        filters=[["docstatus", "=", 1]],  # Only consider submitted promotions
    )

    if all_promotions:
        # Calculate 10% of promotions to cancel
        num_to_cancel = max(1, int(len(all_promotions) * 0.1))
        promotions_to_cancel = random.sample(all_promotions, num_to_cancel)

        for promotion in promotions_to_cancel:
            try:
                client.update(
                    {
                        "doctype": "Employee Promotion",
                        "name": promotion["name"],
                        "docstatus": 2,  # 2 = Cancelled
                    }
                )
                logger.info(f"Cancelled promotion: {promotion['name']}")
            except Exception as e:
                logger.error(f"Failed to cancel promotion: {promotion['name']}")
                logger.error(f"Error message: {str(e).splitlines()[0]}")


async def delete_all_promotions():
    client = frappe_client.create_client()
    promotions = client.get_list(
        "Employee Promotion",
        limit_page_length=100000,
    )
    if not promotions:
        logger.info("No promotions to delete")
        return

    updated_promotions = [
        {
            "docname": promotion["name"],
            "docstatus": 2,  # Cancelled
            "doctype": "Employee Promotion",
        }
        for promotion in promotions
    ]
    logger.info(f"Cancelling {len(updated_promotions)} promotions before deletion")
    try:
        client.bulk_update(updated_promotions)
    except Exception as e:
        logger.error(f"Failed to cancel promotions: {str(e).splitlines()[0]}")

    for promotion in promotions:
        try:
            client.delete("Employee Promotion", promotion["name"])
            logger.info(f"Deleted promotion {promotion['name']}")
        except Exception as e:
            logger.error(f"Failed to delete promotion: {promotion['name']}")
            logger.error(f"Error message: {str(e).splitlines()[0]}")


async def insert_transfers(number_of_transfers: int = 10):
    client = frappe_client.create_client()
    employees = client.get_list(
        "Employee",
        limit_page_length=settings.LIST_LIMIT,
        filters=[["status", "=", "Active"]],
        fields=["name", "designation"],
    )

    # Get the default company
    company = companies.get_default_company()
    company_name = company["name"]

    # Filter out leadership employees (c-suite, managers, directors, heads)
    filtered_employees = []
    for employee in employees:
        designation = employee.get("designation", "").lower()
        if (
            "chief" not in designation
            and "officer" not in designation
            and "manager" not in designation
            and "director" not in designation
            and "head" not in designation
            and "head of" not in designation
        ):
            filtered_employees.append(employee)

    logger.info(f"Found {len(filtered_employees)} non-leadership employees eligible for transfer")

    if not filtered_employees:
        logger.warning("No eligible employees for transfer")
        return

    # Get all departments and designations for transfers
    departments = [
        department["name"]
        for department in client.get_list(
            "Department",
            limit_page_length=settings.LIST_LIMIT,
            filters=[["company", "=", company_name]],
        )
    ]

    designations = [designation["name"] for designation in client.get_list("Designation")]

    # Filter out leadership positions from available designations
    filtered_designations = []
    for designation in designations:
        designation_lower = designation.lower()
        if (
            "chief" not in designation_lower
            and "officer" not in designation_lower
            and "manager" not in designation_lower
            and "director" not in designation_lower
            and "head" not in designation_lower
            and "head of" not in designation_lower
        ):
            filtered_designations.append(designation)

    employees_to_transfer = random.sample(filtered_employees, min(number_of_transfers, len(filtered_employees)))

    logger.info(f"Creating {len(employees_to_transfer)} employee transfers")

    for employee in employees_to_transfer:
        # Get employee details including current department and designation
        emp_doc = client.get_doc("Employee", employee["name"])

        # Select new department different from current one (if departments exist)
        current_dept = emp_doc.get("department")
        available_depts = [d for d in departments if d != current_dept]
        new_dept = random.choice(available_depts) if available_depts else None

        # Select new designation different from current one (if designations exist)
        current_designation = emp_doc.get("designation")
        available_designations = [d for d in filtered_designations if d != current_designation]
        new_designation = random.choice(available_designations) if available_designations else None

        # Generate a random transfer date in the past year
        transfer_date = fake.date_between(start_date="-1y", end_date="today")

        # Create the transfer document
        transfer_doc = {
            "doctype": "Employee Transfer",
            "employee": employee["name"],
            "employee_name": f"{emp_doc.get('first_name', '')} {emp_doc.get('last_name', '')}",
            "transfer_date": transfer_date.strftime("%Y-%m-%d"),
            "company": company_name,
            "new_company": company_name,  # No change in company
            "transfer_details": [],
        }

        # Add department transfer details if applicable
        if current_dept and new_dept:
            transfer_doc["transfer_details"].append(
                {
                    "property": "Department",
                    "current": current_dept,
                    "new": new_dept,
                    "fieldname": "department",
                }
            )

        # Add designation transfer details if applicable
        if current_designation and new_designation:
            transfer_doc["transfer_details"].append(
                {
                    "property": "Designation",
                    "current": current_designation,
                    "new": new_designation,
                    "fieldname": "designation",
                }
            )

        # Only create transfers with at least one change
        if transfer_doc["transfer_details"]:
            try:
                # Set a random docstatus (0=Draft, 1=Submitted)
                transfer_doc["docstatus"] = random.choice([0, 1])

                # Insert the transfer document
                response = client.insert(transfer_doc)
                logger.info(f"Created employee transfer: {response['name']}")

                # If docstatus is submitted, also update the employee record
                if transfer_doc["docstatus"] == 1:
                    employee_update = {"doctype": "Employee", "name": employee["name"]}

                    # Update department and designation in employee record
                    for detail in transfer_doc["transfer_details"]:
                        fieldname = detail["fieldname"]
                        new_value = detail["new"]
                        employee_update[fieldname] = new_value

                    client.update(employee_update)
                    logger.info(f"Updated employee {employee['name']} with new {', '.join([d['property'] for d in transfer_doc['transfer_details']])}")

            except Exception as e:
                logger.error(f"Failed to create transfer for employee: {employee['name']}")
                logger.error(f"Error message: {str(e).splitlines()[0]}")


async def delete_all_transfers():
    """Delete all existing employee transfers."""
    client = frappe_client.create_client()
    transfers = client.get_list("Employee Transfer", limit_page_length=settings.LIST_LIMIT, fields=["name"])

    if not transfers:
        logger.info("No transfers to delete")
        return

    for transfer in transfers:
        try:
            client.update(
                {
                    "doctype": "Employee Transfer",
                    "name": transfer["name"],
                    "docstatus": 2,  # Cancelled
                }
            )
            logger.info(f"Cancelled transfer: {transfer['name']}")
        except Exception as e:
            logger.error(f"Failed to cancel transfer: {transfer['name']}")
            logger.error(e)

    for transfer in transfers:
        logger.info(f"Deleting transfer: {transfer['name']}")
        try:
            client.delete("Employee Transfer", transfer["name"])
        except Exception as e:
            logger.error(f"Failed to delete transfer: {transfer['name']} {e}")


async def insert_separations(number_of_separations: int = 10):
    """
    Create employee separation records for a random selection of employees.

    Args:
        number_of_separations (int): Number of separation records to create
    """
    # Get active employees
    client = frappe_client.create_client()
    employees = client.get_list(
        "Employee",
        limit_page_length=settings.LIST_LIMIT,
        fields=["name", "employee_name", "department", "designation", "company"],
        filters=[["status", "=", "Active"]],
    )

    if not employees:
        logger.warning("No active employees found for creating separation records")
        return

    # Select random employees for separation
    employees_to_separate = random.sample(employees, min(number_of_separations, len(employees)))

    logger.info(f"Creating {len(employees_to_separate)} employee separation records")

    for employee in employees_to_separate:
        # Generate a separation date in the near future
        separation_date = fake.date_between(start_date="today", end_date="+6m")

        # Create the separation document
        separation_doc = {
            "doctype": "Employee Separation",
            "employee": employee["name"],
            "employee_name": employee.get("employee_name", ""),
            "department": employee.get("department"),
            "designation": employee.get("designation"),
            "company": employee.get("company"),
            "boarding_status": fake.random_element(
                OrderedDict(
                    [
                        ("Pending", 0.7),
                        ("In Process", 0.2),
                        ("Completed", 0.1),
                    ]
                )
            ),
            "boarding_begins_on": fake.date_between(start_date="today", end_date=separation_date).strftime("%Y-%m-%d"),
            "docstatus": fake.random_element(
                OrderedDict(
                    [
                        (0, 1),  # Draft
                        # (1, 0.4),  # Submitted
                    ]
                )
            ),
            "notify_users_by_email": 0,
        }

        # Optionally add resignation letter date (70% chance)
        if random.random() < 0.7:
            resignation_date = fake.date_between(start_date="-1m", end_date="today")
            separation_doc["resignation_letter_date"] = resignation_date.strftime("%Y-%m-%d")

        try:
            response = client.insert(separation_doc)
            logger.info(f"Created employee separation: {response['name']}")

            # If the separation is submitted, update the employee status
            if separation_doc["docstatus"] == 1:
                try:
                    client.update(
                        {
                            "doctype": "Employee",
                            "name": employee["name"],
                            "status": "Left",
                        }
                    )
                    logger.info(f"Updated employee {employee['name']} status to Left")
                except Exception as e:
                    logger.error(f"Failed to update employee status: {employee['name']}")
                    logger.error(f"Error message: {str(e).splitlines()[0]}")

        except Exception as e:
            logger.error(f"Failed to create separation for employee: {employee['name']}")
            logger.error(f"Error message: {str(e).splitlines()[0]}")


async def delete_all_separations():
    """
    Delete all existing employee separation records.
    """
    # Get all separation records
    client = frappe_client.create_client()
    separations = client.get_list(
        "Employee Separation",
        limit_page_length=settings.LIST_LIMIT,
        fields=["name", "docstatus"],
    )

    if not separations:
        logger.info("No separation records to delete")
        return

    # First cancel all submitted separations
    submitted_separations = [
        {
            "docname": sep["name"],
            "docstatus": 2,  # Cancelled
            "doctype": "Employee Separation",
        }
        for sep in separations
        if sep.get("docstatus") == 1
    ]

    if submitted_separations:
        logger.info(f"Cancelling {len(submitted_separations)} submitted separation records")
        try:
            client.bulk_update(submitted_separations)
        except Exception as e:
            logger.error(f"Failed to cancel separation records: {str(e).splitlines()[0]}")

    # Now delete all separation records
    for separation in separations:
        try:
            client.delete("Employee Separation", separation["name"])
            logger.info(f"Deleted separation record: {separation['name']}")
        except Exception as e:
            logger.error(f"Failed to delete separation record: {separation['name']}")
            logger.error(f"Error message: {str(e).splitlines()[0]}")


def find_matching_department(designation: str, departments: list[str]) -> str:
    """Find a department that matches the designation based on keywords."""
    matching_department = None

    if not designation or not departments:
        return None

    designation_words = designation.lower().split()

    # First try to find a direct match between words in designation and department names
    for dept in departments:
        dept_lower = dept.lower()
        # Check if any word in designation appears in department name
        for word in designation_words:
            if word in dept_lower and len(word) > 3:  # Avoid matching short words
                matching_department = dept
                break
        if matching_department:
            break

    # If no match found, use some common mappings
    if not matching_department:
        designation_lower = designation.lower()
        if "sales" in designation_lower or "business" in designation_lower:
            matching_departments = [d for d in departments if "sales" in d.lower()]
            matching_department = random.choice(matching_departments) if matching_departments else None
        elif "finance" in designation_lower or "account" in designation_lower:
            matching_departments = [d for d in departments if "finance" in d.lower() or "account" in d.lower()]
            matching_department = random.choice(matching_departments) if matching_departments else None
        elif "engineer" in designation_lower or "developer" in designation_lower or "tech" in designation_lower:
            matching_departments = [d for d in departments if "tech" in d.lower() or "engineering" in d.lower() or "development" in d.lower()]
            matching_department = random.choice(matching_departments) if matching_departments else None
        elif "hr" in designation_lower or "human resource" in designation_lower:
            matching_departments = [d for d in departments if "hr" in d.lower() or "human" in d.lower()]
            matching_department = random.choice(matching_departments) if matching_departments else None
        elif "market" in designation_lower:
            matching_departments = [d for d in departments if "market" in d.lower()]
            matching_department = random.choice(matching_departments) if matching_departments else None

    # Fallback to random department if no match found
    if not matching_department and departments:
        matching_department = random.choice(departments)

    return matching_department


async def update_employee_reports_to():
    """
    Update the 'reports_to' field for employees by first appointing department heads
    and then setting other employees to report to their department head.
    """
    client = frappe_client.create_client()
    company = companies.get_default_company()
    company_name = company["name"]

    # Get all departments
    departments = client.get_list(
        "Department",
        limit_page_length=settings.LIST_LIMIT,
        fields=["name"],
        filters=[["company", "=", company_name]],
    )

    if not departments:
        logger.warning("No departments found for setting up reporting structure")
        return

    logger.info(f"Updating reporting structure for {len(departments)} departments")

    department_heads = {}

    # First pass: For each department, find a suitable leader (manager, head, or C-suite)
    for department in departments:
        dept_name = department["name"]
        logger.info(f"Finding leader for department: {dept_name}")

        # First look for employees in this department that have leadership titles
        employees_in_dept = client.get_list(
            "Employee",
            limit_page_length=settings.LIST_LIMIT,
            fields=["name", "designation", "employee_name"],
            filters=[
                ["department", "=", dept_name],
                ["status", "=", "Active"],
            ],
        )

        if not employees_in_dept:
            logger.warning(f"No employees found in department: {dept_name}")
            continue

        # Define leadership tiers with descending priority
        c_suite_employees = []
        head_employees = []
        manager_employees = []
        senior_employees = []
        regular_employees = []

        # Categorize employees by seniority based on their designation
        for employee in employees_in_dept:
            designation = employee.get("designation", "").lower()

            if "chief" in designation or "officer" in designation or "director" in designation:
                c_suite_employees.append(employee)
            elif "head" in designation or "head of" in designation:
                head_employees.append(employee)
            elif "manager" in designation or "lead" in designation:
                manager_employees.append(employee)
            elif "senior" in designation or "principal" in designation:
                senior_employees.append(employee)
            else:
                regular_employees.append(employee)

        # Choose department head by priority
        department_head = None
        if c_suite_employees:
            department_head = random.choice(c_suite_employees)
        elif head_employees:
            department_head = random.choice(head_employees)
        elif manager_employees:
            department_head = random.choice(manager_employees)
        elif senior_employees:
            department_head = random.choice(senior_employees)
        elif regular_employees:
            # If no leadership positions, promote someone to be department head
            department_head = random.choice(regular_employees)

        if department_head:
            department_heads[dept_name] = department_head
            logger.info(f"Appointed {department_head['employee_name']} as head of {dept_name}")

    # Second pass: Set up C-suite reporting structure
    ceo = None
    c_suite_members = []

    # Get all C-suite employees
    c_suite = client.get_list(
        "Employee",
        limit_page_length=settings.LIST_LIMIT,
        fields=["name", "designation", "employee_name", "department"],
        filters=[
            ["company", "=", company_name],
            ["status", "=", "Active"],
        ],
    )

    # Filter to find CEO and other C-suite
    for employee in c_suite:
        designation = employee.get("designation", "").lower()
        if "chief executive" in designation or "ceo" in designation:
            ceo = employee
        elif "chief" in designation or "officer" in designation:
            c_suite_members.append(employee)

    # If no CEO found, appoint one
    if not ceo and c_suite_members:
        ceo = random.choice(c_suite_members)
        c_suite_members.remove(ceo)
    elif not ceo:
        # Get any employee to be CEO if no C-suite found
        all_employees = client.get_list(
            "Employee",
            limit_page_length=settings.LIST_LIMIT,
            fields=["name", "designation", "employee_name"],
            filters=[
                ["company", "=", company_name],
                ["status", "=", "Active"],
            ],
        )
        if all_employees:
            ceo = random.choice(all_employees)

    # Update C-suite to report to CEO
    if ceo:
        logger.info(f"Appointed {ceo['employee_name']} as CEO")

        # Make C-suite report to CEO
        for executive in c_suite_members:
            try:
                client.update(
                    {
                        "doctype": "Employee",
                        "name": executive["name"],
                        "reports_to": ceo["name"],
                    }
                )
                logger.info(f"Updated {executive['employee_name']} to report to CEO")
            except Exception as e:
                logger.error(f"Failed to update reports_to for {executive['name']}")
                logger.error(f"Error message: {str(e).splitlines()[0]}")

    # Third pass: Make department heads report to appropriate C-suite or CEO
    for dept_name, dept_head in department_heads.items():
        # Find appropriate C-suite member to report to based on department
        reporting_executive = ceo  # Default to CEO

        if c_suite_members:
            dept_lower = dept_name.lower()
            for executive in c_suite_members:
                exec_designation = executive.get("designation", "").lower()
                exec_dept = executive.get("department", "").lower()

                # Match department with related executive
                if (
                    (("finance" in dept_lower or "account" in dept_lower) and ("finance" in exec_designation or "cfo" in exec_designation))
                    or (("tech" in dept_lower or "engineering" in dept_lower or "it" in dept_lower) and ("technology" in exec_designation or "cto" in exec_designation))
                    or (("hr" in dept_lower or "human" in dept_lower) and ("human" in exec_designation or "people" in exec_designation))
                    or (("operation" in dept_lower or "product" in dept_lower) and ("operation" in exec_designation or "coo" in exec_designation))
                    or (("sales" in dept_lower or "market" in dept_lower) and ("marketing" in exec_designation or "revenue" in exec_designation or "commercial" in exec_designation))
                    or (exec_dept and dept_lower in exec_dept)
                ):
                    reporting_executive = executive
                    break

        # Skip if department head is the CEO
        if ceo and dept_head["name"] == ceo["name"]:
            continue

        # Skip if department head is already a C-suite member
        if any(c_exec["name"] == dept_head["name"] for c_exec in c_suite_members):
            continue

        # Update department head to report to appropriate executive
        if reporting_executive:
            try:
                client.update(
                    {
                        "doctype": "Employee",
                        "name": dept_head["name"],
                        "reports_to": reporting_executive["name"],
                    }
                )
                logger.info(f"Updated {dept_head['employee_name']} to report to {reporting_executive['employee_name']}")
            except Exception as e:
                logger.error(f"Failed to update reports_to for {dept_head['name']}")
                logger.error(f"Error message: {str(e).splitlines()[0]}")

    # Fourth pass: For each department, make remaining employees report to department head
    for dept_name, dept_head in department_heads.items():
        # Get all employees in this department
        employees_in_dept = client.get_list(
            "Employee",
            limit_page_length=settings.LIST_LIMIT,
            fields=["name", "employee_name"],
            filters=[
                ["department", "=", dept_name],
                ["status", "=", "Active"],
                ["name", "!=", dept_head["name"]],  # Exclude department head
            ],
        )

        # Update each employee to report to department head
        for employee in employees_in_dept:
            try:
                client.update(
                    {
                        "doctype": "Employee",
                        "name": employee["name"],
                        "reports_to": dept_head["name"],
                    }
                )
                logger.info(f"Updated {employee['employee_name']} to report to department head {dept_head['employee_name']}")
            except Exception as e:
                logger.error(f"Failed to update reports_to for {employee['name']}")
                logger.error(f"Error message: {str(e).splitlines()[0]}")

    logger.info("Employee reporting structure update completed")


async def correct_employee_relieving_dates():
    """
    Correct the relieving dates for employees who have been terminated.
    """
    client = frappe_client.create_client()
    employees = client.get_list(
        "Employee",
        fields=[
            "name",
            "employee_name",
            "designation",
            "department",
            "date_of_joining",
            "relieving_date",
            "status",
        ],
        filters=[["status", "=", "Active"]],  # must be active employees
        limit_page_length=settings.LIST_LIMIT,
    )

    for employee in employees:
        try:
            client.update(
                {
                    "doctype": "Employee",
                    "name": employee["name"],
                    "relieving_date": None,
                }
            )
            logger.info(f"Updated relieving date for {employee['employee_name']}")
        except Exception as e:
            logger.error(f"Failed to update relieving date for {employee['name']}")
            logger.error(f"Error message: {str(e).splitlines()[0]}")
