import json
import logging
import random
from collections import OrderedDict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from faker import Faker

from apps.frappehrms.config.settings import settings
from apps.frappehrms.core import companies
from apps.frappehrms.utils import frappe_client
from apps.frappehrms.utils.timeout import TimeoutExceptionError, time_limit
from common.logger import logger


fake = Faker()


# Load leave types and reasons data
def _get_leave_reason(leave_type_name):
    """Get a random reason for the given leave type from the JSON data."""
    leave_data = load_leaves_data()
    leave_types = leave_data.get("leave_types", [])

    # Find the matching leave type
    for leave_type in leave_types:
        if leave_type["name"] == leave_type_name:
            # Return a random reason if available, otherwise fallback to fake sentence
            reasons = leave_type.get("reasons", [])
            if reasons:
                return random.choice(reasons)

    # Fallback to fake sentence if leave type not found or no reasons available
    return fake.sentence(nb_words=10)


# Load data from JSON file
def load_leaves_data():
    """Load leave types and holiday data from JSON file."""
    try:
        json_path = Path(__file__).parent.parent.joinpath("data", "leaves.json")
        data = json.loads(json_path.read_text(encoding="utf-8"))
        return data
    except Exception as e:
        logger.error(f"Error loading leave data from JSON: {e!s}")
        return {}


# Load leave types from JSON file
def load_leave_types():
    """Load leave types from JSON file."""
    data = load_leaves_data()
    leave_types = data.get("leave_types", [])
    logger.info(f"Loaded {len(leave_types)} leave types from JSON file")
    return leave_types


# Load holiday lists from JSON file
def load_holiday_lists():
    """Load holiday lists from JSON file."""
    data = load_leaves_data()
    holiday_lists = data.get("holiday_lists", [])
    logger.info(f"Loaded {len(holiday_lists)} holiday lists from JSON file")
    return holiday_lists


def generate_leave_allocation(employee_id: str, leave_type: dict[str, Any], company_name: str) -> dict[str, Any]:
    """Generate a leave allocation for an employee."""
    today = datetime.now()
    # Allocate from start of year to end of year
    from_date = datetime(today.year, 1, 1)
    to_date = datetime(today.year, 12, 31)

    # Allocate a random number of days up to the maximum
    max_days = leave_type.get(
        "max_leaves_allowed",
        leave_type.get("max_days_per_year", leave_type.get("max_days", 0)),
    )

    if max_days > 0:  # noqa: SIM108
        allocated_days = random.randint(max(1, int(max_days // 2)), int(max_days))
    else:
        # Assign a default allocation between 5-10 if no maximum is specified
        allocated_days = random.randint(5, 10)

    return {
        "doctype": "Leave Allocation",
        "employee": employee_id,
        "leave_type": leave_type["name"],
        "from_date": from_date.strftime("%Y-%m-%d"),
        "to_date": to_date.strftime("%Y-%m-%d"),
        "new_leaves_allocated": allocated_days,
        "company": company_name,
        "total_leaves_allocated": allocated_days,
        "docstatus": fake.random_element(OrderedDict([(0, 0.2), (1, 0.7)])),
    }


def generate_leave_application(employee_id: str, leave_type: dict[str, Any], company_name: str) -> dict[str, Any]:
    """Generate a leave application for an employee."""
    # Ensure leave application is within the current year's allocation
    today = datetime.now()
    year_start = datetime(today.year, 1, 1)
    year_end = datetime(today.year, 12, 31)

    # Generate a date within the current year's allocation period
    # Use min(today, year_end) to avoid generating future dates
    from_date = fake.date_between(start_date=year_start, end_date=min(today - timedelta(days=1), year_end))

    # Convert from_date to datetime to match year_end type
    from_date = datetime.combine(from_date, datetime.min.time())

    # Leave duration between 1 and 5 days
    max_days = leave_type.get("max_days_per_year", leave_type.get("max_days", 0))
    max_duration = min(5, max_days) if max_days > 0 else 5

    duration = random.randint(1, max_duration)
    to_date = from_date + timedelta(days=duration - 1)  # inclusive end date

    # Ensure to_date doesn't exceed year_end
    if to_date > year_end:
        to_date = year_end
        # Recalculate duration
        duration = (to_date - from_date).days + 1

    return {
        "doctype": "Leave Application",
        "employee": employee_id,
        "leave_type": leave_type["name"],
        "from_date": from_date.strftime("%Y-%m-%d"),
        "to_date": to_date.strftime("%Y-%m-%d"),
        "total_leave_days": duration,
        "status": random.choices(["Approved", "Rejected", "Open"], weights=[0.7, 0.1, 0.2])[0],
        "description": _get_leave_reason(leave_type["name"]),
        "company": company_name,
    }


async def insert_leave_types():
    client = frappe_client.create_client()
    company = companies.get_default_company()
    company_name = company["name"]

    # Load leave types from JSON file
    leave_types_to_use = load_leave_types()

    if not leave_types_to_use:
        logger.error("No leave types found in leaves.json file. Cannot proceed.")
        return

    # 1. Create leave types if they don't exist
    for leave_type in leave_types_to_use:
        # Handle both old and new format
        name = leave_type["name"]
        description = leave_type.get("description", "")
        max_days = leave_type.get("max_days_per_year", leave_type.get("max_days", 0))

        leave_type_doc = {
            "doctype": "Leave Type",
            "name": name,
            "leave_type_name": name,
            "max_continuous_days_allowed": max_days if max_days > 0 else 30,
            "description": description,
            "company": company_name,
            "is_carry_forward": leave_type.get("carry_forward", False),
            "is_encash": leave_type.get("encashment_allowed", False),
            "include_holiday": leave_type.get("include_holidays", False),
            "total_leaves_allocated": max_days if max_days > 0 else 0,
        }

        # Add policy if available
        if "policy" in leave_type:
            policy = leave_type["policy"]
            leave_type_doc["policy_name"] = policy.get("name", f"{name} Policy")
            leave_type_doc["policy_description"] = policy.get("description", "")

        try:
            client.insert(leave_type_doc)
            logger.info(f"Created leave type: {name}")
        except Exception as e:
            logger.warning(f"Failed to insert leave type {leave_type_doc}: {(e)}")


async def insert_leave_allocations(number_of_allocations: int = 200):
    """
    Generate and insert leave allocations and applications for employees.
    This function creates leave types, allocates leaves to employees, and
    generates sample leave applications.

    Args:
        number_of_allocations (int): Maximum number of leave allocations to generate. Default is 200.
    """
    client = frappe_client.create_client()
    company = companies.get_default_company()
    company_name = company["name"]

    leave_types_to_use = client.get_list("Leave Type", fields=["*"], limit_page_length=settings.LIST_LIMIT)

    # 2. Get all employees
    employees = client.get_list(
        "Employee",
        fields=["name", "employee_name"],
        limit_page_length=settings.LIST_LIMIT,
    )

    if not employees:
        logger.warning("No employees found. Skipping leave generation.")
        return

    allocations = []

    for employee in employees:
        # Break if we've reached the limit of allocations
        if len(allocations) >= number_of_allocations:
            logger.info(f"Reached limit of {number_of_allocations} allocations")
            break

        # Allocate 3 random leave types to each employee
        selected_leave_types = random.sample(leave_types_to_use, min(3, len(leave_types_to_use)))

        for leave_type in selected_leave_types:
            # Break if we've reached the limit of allocations
            if len(allocations) >= number_of_allocations:
                break

            # Skip allocations for no-quota leave types
            if leave_type.get("max_days_per_year", leave_type.get("max_days", 0)) == 0 and "rules" in leave_type and leave_type["rules"].get("no_fixed_quota", False):
                continue

            # Create allocation
            allocation = generate_leave_allocation(employee["name"], leave_type, company_name)
            allocations.append(allocation)

    if not allocations:
        logger.warning("No leave allocations found. Skipping leave generation.")
        return

    logger.info(f"Generated {len(allocations)} leave allocations")

    for allocation in allocations:
        try:
            response = client.insert(allocation)
            logger.info(f"Created leave allocation: {allocation['employee']}")

            if allocation["docstatus"] == 1 and random.random() < 0.2:  # 20% chance
                client.update(
                    {
                        "doctype": "Leave Allocation",
                        "name": response.get("name"),
                        "docstatus": 2,
                    }
                )

            logger.info(f"Created leave allocation: {allocation['employee']}")
        except Exception as e:
            logger.warning(f"Failed to insert leave allocation {json.dumps(allocation)}: {e!s}")


async def delete_leave_applications():
    """
    Delete all leave-related records from the system.
    This removes leave applications, allocations, and optionally leave types.
    """
    client = frappe_client.create_client()

    # 1. Delete all leave applications
    applications = client.get_list("Leave Application", limit_page_length=999)

    if not applications:
        logger.info("No applications found to delete")

    for app in applications:
        try:
            if app["docstatus"] not in [0, 2]:
                client.update(
                    {
                        "doctype": "Leave Application",
                        "name": app["name"],
                        "docstatus": 2,
                    }
                )
            client.delete("Leave Application", app["name"])
            logger.info(f"Deleted leave application: {app['name']}")
        except Exception as e:
            logger.warning(f"Failed to delete leave application {app['name']}: {e!s}")


async def delete_leave_allocations():
    client = frappe_client.create_client()

    allocations = client.get_list("Leave Allocation", limit_page_length=999)
    for alloc in allocations:
        try:
            if alloc["docstatus"] == 1:
                client.update(
                    {
                        "doctype": "Leave Allocation",
                        "name": alloc["name"],
                        "docstatus": 2,
                    }
                )
            client.delete("Leave Allocation", alloc["name"])
            logger.info(f"Deleted leave allocation: {alloc['name']}")
        except Exception as e:
            logger.warning(f"Failed to delete leave allocation {alloc['name']}: {e!s}")


async def delete_leave_types():
    client = frappe_client.create_client()

    leave_types = client.get_list("Leave Type", limit_page_length=settings.LIST_LIMIT)
    for lt in leave_types:
        try:
            client.delete("Leave Type", lt["name"])
            logger.info(f"Deleted leave type: {lt['name']}")
        except Exception as e:
            logger.warning(f"Failed to delete leave type {lt['name']}: {e!s}")


async def assign_leave_types():
    client = frappe_client.create_client()

    users = client.get_list(
        "User",
        fields=["name", "email"],
        limit_page_length=settings.LIST_LIMIT,
        filters=[["name", "not in", ["Administrator", "Guest"]]],
    )
    leave_types = client.get_list(
        "Leave Type",
        fields=["name", "leave_type_name"],
        limit_page_length=settings.LIST_LIMIT,
    )

    try:
        with time_limit(60):  # 60 second timeout
            client.assign(
                "Leave Type",
                [lt["name"] for lt in leave_types],
                [user["email"] for user in users],
            )
    except TimeoutExceptionError:
        logging.warning("Assignment of leave types timed out after 60 seconds")


async def insert_leave_holidays():
    """
    Create holiday lists based on the data in the JSON file.
    The lists are assigned to the default company and linked to employees.
    """
    client = frappe_client.create_client()

    # Get holiday lists from JSON
    holiday_lists_data = load_holiday_lists()

    if not holiday_lists_data:
        logger.error("No holiday lists found in leaves.json file. Cannot create holidays.")
        return

    # Get default company
    company = companies.get_default_company()
    company_name = company["name"]

    for holiday_list_data in holiday_lists_data:
        # Get current year if not specified
        current_year = datetime.now().year

        from_date_str = holiday_list_data.get("from_date", f"{current_year}-01-01")
        to_date_str = holiday_list_data.get("to_date", f"{current_year}-12-31")

        from_date = datetime.strptime(from_date_str, "%Y-%m-%d")
        to_date = datetime.strptime(to_date_str, "%Y-%m-%d")

        # Create holiday list document
        holiday_list = {
            "doctype": "Holiday List",
            "holiday_list_name": holiday_list_data.get("name", f"Holidays {current_year}"),
            "from_date": from_date_str,
            "to_date": to_date_str,
            "company": company_name,
            "color": holiday_list_data.get("color", "#ECAD4B"),  # Default gold color
            "holidays": [],
        }

        # Add holidays from the JSON data
        idx = 1
        for holiday in holiday_list_data.get("holidays", []):
            holiday_list["holidays"].append(
                {
                    "doctype": "Holiday",
                    "holiday_date": holiday["holiday_date"],
                    "description": holiday["description"],
                    "weekly_off": 0,
                    "idx": idx,
                }
            )
            idx += 1

        # Add all Saturdays and Sundays in the date range
        current_date = from_date
        while current_date <= to_date:
            # 5 = Saturday, 6 = Sunday
            if current_date.weekday() in [5, 6]:
                day_name = "Saturday" if current_date.weekday() == 5 else "Sunday"
                holiday_list["holidays"].append(
                    {
                        "doctype": "Holiday",
                        "holiday_date": current_date.strftime("%Y-%m-%d"),
                        "description": f"Weekly Off - {day_name}",
                        "weekly_off": 1,
                        "idx": idx,
                    }
                )
                idx += 1
            current_date += timedelta(days=1)

        # Update total holidays count
        holiday_list["total_holidays"] = len(holiday_list["holidays"])

        # Insert holiday list
        try:
            client.insert(holiday_list)
            logger.info(f"Created holiday list: {holiday_list['holiday_list_name']} with {holiday_list['total_holidays']} holidays including weekends")
        except Exception as e:
            logger.error(f"Error creating holiday list: {e!s}")


async def assign_leave_holidays():
    client = frappe_client.create_client()

    company = companies.get_default_company()
    try:
        client.update(
            {
                "doctype": "Company",
                "name": company["name"],
                "default_holiday_list": f"US Holidays {datetime.now().year}",
            }
        )
        logger.info(f"Assigned holiday list to company: {company['name']}")
    except Exception as e:
        logger.error(f"Error assigning leave policy to company: {e!s}")

    users = client.get_list(
        "User",
        fields=["name", "email"],
        limit_page_length=settings.LIST_LIMIT,
        filters=[["name", "not in", ["Administrator", "Guest"]]],
    )
    holiday_lists = client.get_list("Holiday List", fields=["name", "holiday_list_name"])

    try:
        with time_limit(60):  # 60 second timeout
            client.assign(
                "Holiday List",
                [hl["name"] for hl in holiday_lists],
                [user["email"] for user in users],
            )
    except TimeoutExceptionError:
        logging.warning("Assignment of holiday lists timed out after 60 seconds")


async def update_leave_approvers():
    client = frappe_client.create_client()

    all_employees = client.get_list(
        "Employee",
        fields=["name", "company_email", "designation", "department", "status"],
        limit_page_length=settings.LIST_LIMIT,
    )

    active_employees = [employee for employee in all_employees if employee.get("status") == "Active"]

    if not active_employees:
        logger.warning("No active employees found for expense approver assignment")
        return

    # Track expense approvers
    leave_approvers = []

    for employee in active_employees:
        designation = employee.get("designation", "").lower()
        department = employee.get("department", "").lower()

        # Check if employee is in finance or HR department
        is_finance_hr = "finance" in department or "account" in department or "hr" in department or "human" in department

        # Check if employee has a leadership designation
        is_leader = "chief" in designation or "head" in designation or "manager" in designation or "director" in designation

        # If employee is a leader in finance or HR, add them as an expense approver
        if is_finance_hr and is_leader:
            leave_approvers.append(employee)
            logger.info(f"Identified {employee['company_email']} as expense approver based on designation: {employee['designation']}")

    if not leave_approvers:
        logger.warning("No suitable expense approvers found")
        return

    # Get all expense claim types
    expense_claim_types = client.get_list("Expense Claim Type", fields=["name"], limit_page_length=settings.LIST_LIMIT)

    if not expense_claim_types:
        logger.warning("No expense claim types found")
        return

    for employee in all_employees:
        approver = fake.random_element(elements=leave_approvers)
        try:
            client.update(
                {
                    "doctype": "Employee",
                    "name": employee["name"],
                    "leave_approver": approver["company_email"],
                }
            )
            logger.info(f"Assigned expense approver {approver['company_email']} to {employee['name']}")
        except Exception as e:
            logger.error(f"Error assigning expense approver to {employee['name']}: {e!s}")


async def insert_leave_applications(number_of_applications: int = 10):
    """
    Generate and insert leave applications for employees with existing allocations.

    Args:
        number_of_applications (int): Maximum number of leave applications to generate. Default is 10.
    """
    client = frappe_client.create_client()

    current_year = datetime.now().year
    allocations = client.get_list(
        "Leave Allocation",
        filters=[
            ["from_date", ">=", f"{current_year}-01-01"],
            ["to_date", ">=", f"{current_year}-12-31"],
        ],
        limit_page_length=settings.LIST_LIMIT,
    )

    if not allocations:
        logger.warning("No leave allocations found. Skipping leave application generation.")
        return

    # Get employee details for all employees with allocations, ensuring they are active
    employee_ids = list({alloc["employee"] for alloc in allocations})
    employees = {}
    active_employees = []

    for emp_id in employee_ids:
        try:
            emp_details = client.get_doc("Employee", emp_id)
            employees[emp_id] = emp_details
            # Only add to active employees if status is Active
            if emp_details.get("status") == "Active":
                active_employees.append(emp_id)
        except Exception as e:
            logger.warning(f"Failed to get employee details for {emp_id}: {e!s}")

    if not active_employees:
        logger.warning("No active employees found. Skipping leave application generation.")
        return

    # Get leave approvers
    leave_approvers = []
    all_employees = client.get_list(
        "Employee",
        fields=["name", "company_email", "designation", "department", "status"],
        limit_page_length=settings.LIST_LIMIT,
    )

    # Find potential leave approvers (managers, HR staff, etc.)
    for employee in all_employees:
        if employee.get("status") == "Active":
            designation = employee.get("designation", "").lower()
            department = employee.get("department", "").lower()

            is_leader = "chief" in designation or "head" in designation or "manager" in designation or "director" in designation

            is_hr = "hr" in department or "human" in department

            if (is_leader or is_hr) and employee.get("company_email"):
                leave_approvers.append(employee["company_email"])

    if not leave_approvers:
        # If no approvers found, use admin
        leave_approvers = ["admin@example.com"]

    # Generate applications
    applications_created = 0
    random.shuffle(allocations)

    for allocation in allocations:
        if applications_created >= number_of_applications:
            break

        # Skip allocations with docstatus != 1 (not submitted)
        if allocation.get("docstatus") != 1:
            continue

        # Get employee ID
        employee_id = allocation.get("employee")

        # Skip if employee is not active
        if employee_id not in active_employees:
            continue

        # 50% chance to create a leave application for an allocation
        if random.random() < 0.5:
            continue

        # Get allocation details
        allocation_doc = client.get_doc("Leave Allocation", allocation["name"])
        leave_type = allocation_doc.get("leave_type")
        company = allocation_doc.get("company")
        total_leaves = float(allocation_doc.get("total_leaves_allocated", 0))

        # Skip if no leaves allocated
        if total_leaves <= 0:
            continue

        employee_info = employees.get(employee_id, {})
        employee_name = employee_info.get("employee_name", "")
        department = employee_info.get("department", "")

        # Calculate leave duration (1 to 3 days, but not more than what's allocated)
        max_days = min(3, int(total_leaves))
        if max_days < 1:
            max_days = 1
        duration = random.randint(1, max_days)

        # Generate leave dates (sometime in the past 6 months)
        today = datetime.now()
        earliest_date = max(
            datetime(today.year, 1, 1),  # Start of year
            today - timedelta(days=180),  # Or 6 months ago
        )

        # Random start date
        from_date = fake.date_between(
            start_date=earliest_date.date(),
            end_date=min(today.date(), datetime(today.year, 12, 31).date()),
        )

        from_date_dt = datetime.combine(from_date, datetime.min.time())
        to_date_dt = from_date_dt + timedelta(days=duration - 1)

        # Convert to string format
        from_date_str = from_date_dt.strftime("%Y-%m-%d")
        to_date_str = to_date_dt.strftime("%Y-%m-%d")

        # Select a random leave approver
        leave_approver = random.choice(leave_approvers)

        # Generate application
        application = {
            "doctype": "Leave Application",
            "employee": employee_id,
            "employee_name": employee_name,
            "leave_type": leave_type,
            "company": company,
            "department": department,
            "from_date": from_date_str,
            "to_date": to_date_str,
            "half_day": 0,
            "total_leave_days": duration,
            "description": _get_leave_reason(leave_type),
            "leave_approver": leave_approver,
            "posting_date": (from_date_dt - timedelta(days=random.randint(0, 7))).strftime("%Y-%m-%d"),
            "follow_via_email": 1,
            "status": random.choices(["Approved", "Rejected", "Open"], weights=[0.7, 0.1, 0.2])[0],
        }

        # Insert the application
        try:
            response = client.insert(application)
            logger.info(f"Created leave application for {employee_id}: {response.get('name')}")

            # Update status if needed
            if application["status"] in ["Approved", "Rejected"]:
                try:
                    client.update(
                        {
                            "doctype": "Leave Application",
                            "name": response.get("name"),
                            "status": application["status"],
                            "docstatus": 1,
                        }
                    )
                except Exception as e:
                    logger.warning(f"Failed to update status for leave application {response.get('name')}: {e!s}")

            applications_created += 1
            logger.info(f"Created leave application for {employee_id}: {response.get('name')}")
        except Exception as e:
            logger.warning(f"Failed to create leave application: {e!s}")

    applications_to_cancel = client.get_list(
        "Leave Application",
        limit_page_length=settings.LIST_LIMIT,
        filters=[["docstatus", "!=", 2]],
    )
    applications_to_cancel = random.sample(applications_to_cancel, int(len(applications_to_cancel) * 0.1))
    for app in applications_to_cancel:
        try:
            client.update(
                {
                    "doctype": "Leave Application",
                    "name": app["name"],
                    "docstatus": 2,
                }
            )
            logger.info(f"Updated leave application: {app['name']}")
        except Exception as e:
            logger.warning(f"Failed to update leave application {app['name']}: {e!s}")
