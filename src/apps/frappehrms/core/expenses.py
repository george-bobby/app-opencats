import json
import random
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


async def insert_expense_accounts():
    """
    Create expense accounts in Frappe HR.
    This function creates standard expense accounts needed for expense management.
    """
    client = frappe_client.create_client()
    company = companies.get_default_company()
    company_name = company["name"]
    company_abbr = company["abbr"]

    logger.info("Starting expense account creation")

    # Load expense accounts from JSON file
    try:
        # Get the path to the expenses.json file
        json_path = Path(__file__).parent.parent.joinpath("data", "expenses.json")

        # Load data from file
        data = json.loads(json_path.read_text(encoding="utf-8"))
        claim_types = data.get("claim_types", [])
    except Exception as e:
        logger.error(f"Error loading expense accounts: {e!s}")
        return 0

    if not claim_types:
        logger.error("No expense claim types found in expenses.json")
        return 0

    # Track unique accounts to avoid duplicates
    unique_accounts = set()

    for claim_type in claim_types:
        for account in claim_type.get("accounts", []):
            account_name = account.get("account")
            if not account_name or account_name in unique_accounts:
                continue

            # Prepare account document
            account_doc = {
                "doctype": "Account",
                "account_name": account_name,
                "parent_account": f"Expenses - {company_abbr}",
                "company": company_name,
                "account_type": "Expense Account",
                "is_group": 0,
            }

            try:
                client.insert(account_doc)
                logger.info(f"Created expense account: {account_name}")
            except Exception:
                try:
                    account_doc = {
                        "doctype": "Account",
                        "name": f"{account_name} - {company_abbr}",
                        "parent_account": f"Expenses - {company_abbr}",
                        "company": company_name,
                        "account_type": "Expense Account",
                        "is_group": 0,
                    }
                    client.update(account_doc)
                    logger.info(f"Updated expense account: {account_name}")
                except Exception as e:
                    logger.error(f"Error creating expense account {account_name}: {e}")
            unique_accounts.add(account_name)


def load_expense_claim_types() -> list[dict[str, Any]]:
    """
    Load expense claim types from the expenses.json file.
    """
    try:
        # Get the path to the expenses.json file
        json_path = Path(__file__).parent.parent.joinpath("data", "expenses.json")

        # Load data from file
        data = json.loads(json_path.read_text(encoding="utf-8"))
        return data.get("claim_types", [])
    except Exception as e:
        logger.error(f"Error loading expense claim types: {e!s}")
        return []


async def insert_expense_claim_types():
    """
    Create expense claim types in Frappe HR.
    This function creates standard expense claim types needed for expense management.
    """
    client = frappe_client.create_client()
    company = companies.get_default_company()
    company_name = company["name"]
    company_abbr = company["abbr"]
    # Create Frappe client

    # Load expense claim types from JSON file
    expense_types = load_expense_claim_types()

    if not expense_types:
        logger.error("No expense claim types found in expenses.json")
        return 0

    inserted_count = 0
    for expense_type in expense_types:
        # Prepare expense claim type document
        expense_doc = {
            "doctype": "Expense Claim Type",
            "name": expense_type["name"],
            "expense_type": expense_type["name"],
            "description": expense_type.get("description", ""),
            "report_type": "Balance Sheet",
            "accounts": [],
        }

        # Add accounts if available
        for account in expense_type.get("accounts", []):
            expense_doc["accounts"].append(
                {
                    "company": company_name,
                    "default_account": f"{account.get('account', 'Bank Accounts')} - {company_abbr}",
                }
            )

        # Insert expense claim type
        try:
            client.insert(expense_doc)
            inserted_count += 1
            logger.info(f"Created expense claim type: {expense_type['name']}")
        except Exception:
            try:
                client.update(expense_doc)
                logger.info(f"Updated expense claim type: {expense_type['name']}")
            except Exception as e:
                logger.error(f"Error creating expense claim type {expense_type['name']}: {e!s}")
            # Continue with the next type

    return inserted_count


async def assign_expense_claim_types():
    logger.info("Assigning expense claim types to users")

    client = frappe_client.create_client()

    users = client.get_list(
        "User",
        fields=["name", "email"],
        limit_page_length=settings.LIST_LIMIT,
        filters=[["name", "not in", ["Administrator", "Guest"]]],
    )
    expense_claim_types = client.get_list("Expense Claim Type", fields=["name", "expense_type"])

    try:
        with time_limit(60):  # 60 second timeout
            try:
                client.assign(
                    "Expense Claim Type",
                    [et["name"] for et in expense_claim_types],
                    [user["email"] for user in users],
                )
            except Exception as e:
                logger.error(f"Error assigning expense claim types to users: {e!s}")
    except TimeoutExceptionError:
        logger.warning("Assignment of expense claim types timed out after 10 seconds")


async def assign_expense_approvers():
    """
    Assign expense approvers based on their designations.
    This function identifies employees with leadership positions (chief, head, manager)
    in finance or HR departments as expense approvers.
    """
    # Get all active employees with their designations and departments
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
    expense_approvers = []

    for employee in active_employees:
        designation = employee.get("designation", "").lower()
        department = employee.get("department", "").lower()

        # Check if employee is in finance or HR department
        is_finance_hr = "finance" in department or "account" in department or "hr" in department or "human" in department

        # Check if employee has a leadership designation
        is_leader = "chief" in designation or "head" in designation or "manager" in designation or "director" in designation

        # If employee is a leader in finance or HR, add them as an expense approver
        if is_finance_hr and is_leader:
            expense_approvers.append(employee)
            logger.info(f"Identified {employee['company_email']} as expense approver based on designation: {employee['designation']}")

    if not expense_approvers:
        logger.warning("No suitable expense approvers found")
        return

    # Get all expense claim types
    expense_claim_types = client.get_list("Expense Claim Type", fields=["name"], limit_page_length=settings.LIST_LIMIT)

    if not expense_claim_types:
        logger.warning("No expense claim types found")
        return

    for employee in all_employees:
        approver = fake.random_element(elements=expense_approvers)
        try:
            client.update(
                {
                    "doctype": "Employee",
                    "name": employee["name"],
                    "expense_approver": approver["company_email"],
                }
            )
            logger.info(f"Assigned expense approver {approver['company_email']} to {employee['name']}")
        except Exception as e:
            logger.error(f"Error assigning expense approver to {employee['name']}: {e!s}")


async def insert_suppliers():
    """
    Insert suppliers into the system.
    """
    client = frappe_client.create_client()
    payable_accounts = client.get_list(
        "Account",
        fields=["name", "account_name", "company"],
        filters=[["account_type", "=", "Payable"]],
        limit_page_length=settings.LIST_LIMIT,
    )

    for account in payable_accounts:
        supplier_name = fake.company()
        supplier = {
            "doctype": "Supplier",
            "supplier_name": fake.company(),
            "company": account["company"],
            "supplier_type": fake.random_element(elements=["Company", "Individual", "Partnership"]),
            "accounts": [
                {
                    "company": account["company"],
                    "account": account["name"],
                    "advance_account": None,
                    "parent": supplier_name,
                    "parentfield": "accounts",
                    "parenttype": "Supplier",
                    "doctype": "Party Account",
                }
            ],
        }
        try:
            client.insert(supplier)
            logger.info(f"Inserted supplier {supplier['supplier_name']}")
        except Exception as e:
            logger.error(f"Failed to insert supplier {supplier['supplier_name']}: {e!s}")


async def insert_expense_claims(number_of_claims: int = 10):
    """
    Generate and insert expense claims for employees.

    Args:
        number_of_claims (int): Number of expense claims to generate and insert
    """
    logger.info(f"Starting expense claim generation for {number_of_claims} claims")

    client = frappe_client.create_client()

    # Get company information
    company = companies.get_default_company()
    company_name = company["name"]
    company_abbr = company["abbr"]

    # Get expense claim types
    expense_types = load_expense_claim_types()
    if not expense_types:
        logger.error("No expense claim types found")
        return 0

    # Get active employees with their expense approvers
    employees = client.get_list(
        "Employee",
        fields=[
            "name",
            "employee_name",
            "department",
            "expense_approver",
            "company_email",
        ],
        filters=[["status", "=", "Active"]],
        limit_page_length=settings.LIST_LIMIT,
    )

    if not employees:
        logger.error("No active employees found")
        return 0

    # Get cost centers
    cost_centers = client.get_list(
        "Cost Center",
        fields=["name"],
        filters=[["company", "=", company_name]],
        limit_page_length=settings.LIST_LIMIT,
    )

    if not cost_centers:
        logger.error("No cost centers found")
        return 0

    inserted_count = 0
    for _ in range(number_of_claims):
        # Select random employee
        employee = random.choice(employees)

        # Generate random number of expense items (1-5)
        num_items = random.randint(1, 5)
        expense_items = []
        total_amount = 0

        for idx in range(num_items):
            # Select random expense type
            expense_type = random.choice(expense_types)

            # Generate random amount between 50 and 1000
            amount = round(random.uniform(50, 1000), 2)
            total_amount += amount

            # Get default account for expense type
            default_account = None
            if expense_type.get("accounts"):
                account = expense_type["accounts"][0].get("account")
                if account:
                    default_account = f"{account} - {company_abbr}"

            # Create expense item
            expense_item = {
                "docstatus": 0,
                "doctype": "Expense Claim Detail",
                "owner": employee["company_email"],
                "expense_date": (datetime.now() - timedelta(days=random.randint(0, 30))).strftime("%Y-%m-%d"),
                "parentfield": "expenses",
                "parenttype": "Expense Claim",
                "idx": idx + 1,
                "cost_center": "Main - " + company_abbr,
                "description": expense_type["description"],
                "expense_type": expense_type["name"],
                "default_account": default_account,
                "amount": amount,
                "sanctioned_amount": amount,
            }
            expense_items.append(expense_item)

        # Create expense claim document
        # Determine approval status with specified distribution
        approval_roll = random.random()
        if approval_roll < 0.6:  # 60% chance
            approval_status = "Approved"
        elif approval_roll < 0.7:  # 10% chance
            approval_status = "Draft"
        else:  # 30% chance
            approval_status = "Rejected"

        # If not Draft, determine status (Submitted or Cancelled)
        if approval_status != "Draft":  # noqa: SIM108
            status = random.choice(["Submitted", "Cancelled"])
        else:
            status = "Draft"

        expense_claim = {
            "doctype": "Expense Claim",
            "owner": employee["company_email"],
            "company": company_name,
            "approval_status": approval_status,
            "expenses": expense_items,
            "taxes": [],
            "advances": [],
            "posting_date": datetime.now().strftime("%Y-%m-%d"),
            "is_paid": 0,
            "status": status,
            "cost_center": "Main - " + company_abbr,
            "employee_name": employee["employee_name"],
            "department": employee["department"],
            "employee": employee["name"],
            "expense_approver": employee["expense_approver"],
            "total_claimed_amount": total_amount,
            "total_sanctioned_amount": total_amount,
            "grand_total": total_amount,
            "payable_account": f"Creditors - {company_abbr}",
            "docstatus": 0 if approval_status == "Draft" else 1,
        }

        try:
            client.insert(expense_claim)
            inserted_count += 1
            logger.info(f"Created expense claim for employee {employee['employee_name']}")
        except Exception as e:
            logger.error(f"Failed to create expense claim for employee {employee['employee_name']}: {e!s}")

    return inserted_count


async def delete_all_expense_claims():
    """
    Delete all expense claims from the system.
    """
    client = frappe_client.create_client()

    expense_claims = client.get_list(
        "Expense Claim",
        fields=["name", "status", "docstatus"],
        limit_page_length=settings.LIST_LIMIT,
    )
    for expense_claim in expense_claims:
        try:
            if expense_claim["status"] not in ["Draft", "Cancelled"]:
                try:
                    client.update(
                        {
                            "doctype": "Expense Claim",
                            "name": expense_claim["name"],
                            "docstatus": 2,
                            "status": "Cancelled",
                        }
                    )
                    logger.info(f"Cancelled expense claim {expense_claim['name']}")
                except Exception as e:
                    logger.error(f"Failed to cancel expense claim {expense_claim['name']}: {e!s}")

            client.delete("Expense Claim", expense_claim["name"])
            logger.info(f"Deleted expense claim {expense_claim['name']}")
        except Exception as e:
            logger.error(f"Failed to delete expense claim {expense_claim['name']}: {e!s}")
