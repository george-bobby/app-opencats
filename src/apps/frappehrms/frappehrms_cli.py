import asyncio
import subprocess
from pathlib import Path

import click

from apps.frappehrms.core import (
    appraisals,
    attendances,
    companies,
    departments,
    designations,
    desk,
    employees,
    expenses,
    leaves,
    recruitments,
    salaries,
    taxes,
    users,
)
from common.logger import logger


@click.group()
def frappehrms_cli():
    pass


@frappehrms_cli.command()
def up():
    """Run docker compose up in the docker directory"""

    docker_dir = Path(__file__).parent.joinpath("docker")
    subprocess.run(["docker", "compose", "up"], cwd=docker_dir)


@frappehrms_cli.command()
@click.option("--volumes", is_flag=True, help="Remove volumes as well (deletes all data)")
@click.option("--force", is_flag=True, help="Force remove everything including orphaned containers and prune volumes")
def down(volumes: bool, force: bool):
    """Stop and remove containers, networks, and optionally volumes"""

    docker_dir = Path(__file__).parent.joinpath("docker")

    # Basic down command
    cmd = ["docker", "compose", "down", "--remove-orphans"]
    if volumes:
        cmd.append("--volumes")
    subprocess.run(cmd, cwd=docker_dir)

    # If force is specified, also prune volumes to ensure complete cleanup
    if force:
        print("Force cleanup: removing all unused volumes...")
        subprocess.run(["docker", "volume", "prune", "-f"])


@frappehrms_cli.command()
# @click.option("--n-employees", type=int, default=150, help="Number of employees to generate")
# @click.option("--n-users", type=int, default=150, help="Number of users to generate")
@click.option("--n-job-openings", type=int, default=20, help="Number of job openings to generate")
@click.option("--n-job-applicants", type=int, default=150, help="Number of job applicants to generate")
@click.option("--n-job-offerings", type=int, default=20, help="Number of job offerings to generate")
def generate(
    # n_employees: int,
    # n_users: int,
    n_job_openings: int,
    n_job_applicants: int,
    n_job_offerings: int,
):
    """Generate data using LLMs and save to JSON files"""

    async def async_generate():
        logger.start("Generating departments...")
        await departments.generate_departments()
        logger.succeed("Generated departments")

        logger.start("Generating designations...")
        await designations.generate_designations()
        logger.succeed("Generated designations")

        logger.start(f"Generating {n_job_openings} job openings...")
        await recruitments.generate_job_openings(n_job_openings)
        logger.succeed(f"Generated {n_job_openings} job openings")

        logger.start(f"Generating {n_job_applicants} job applicants...")
        await recruitments.generate_job_applicants(n_job_applicants)
        logger.succeed(f"Generated {n_job_applicants} job applicants")

        logger.start(f"Generating {n_job_offerings} job offerings...")
        await recruitments.generate_job_offerings(n_job_offerings)
        logger.succeed(f"Generated {n_job_offerings} job offerings")

    asyncio.run(async_generate())


@frappehrms_cli.command()
@click.option("--n-employees", type=int, default=150, help="Number of employees to insert")
@click.option("--n-users", type=int, default=150, help="Number of users to insert")
@click.option("--n-job-openings", type=int, default=20, help="Number of job openings to insert")
@click.option("--n-job-applicants", type=int, default=150, help="Number of job applicants to insert")
@click.option("--n-job-offerings", type=int, default=20, help="Number of job offerings to insert")
@click.option("--n-promomotions", type=int, default=30, help="Number of promotions to insert")
@click.option("--n-transfers", type=int, default=30, help="Number of transfers to insert")
@click.option("--n-separations", type=int, default=50, help="Number of separations to insert")
@click.option("--n-leave-allocations", type=int, default=100, help="Number of leave allocations to insert")
@click.option("--n-leave-applications", type=int, default=100, help="Number of leave applications to insert")
@click.option("--n-expense-claims", type=int, default=100, help="Number of expense claims to insert")
def seed(
    n_employees: int,
    n_users: int,
    n_job_openings: int,
    n_job_applicants: int,
    n_job_offerings: int,
    n_promomotions: int,
    n_transfers: int,
    n_separations: int,
    n_leave_allocations: int,
    n_leave_applications: int,
    n_expense_claims: int,
):
    """Insert data from JSON files into the HRMS system"""

    async def async_seed():
        logger.start("Setting up site...")
        await desk.setup_site()
        logger.succeed("Site setup completed")

        logger.start("Inserting companies...")
        await companies.insert_companies()
        logger.succeed("Inserted companies")

        logger.start("Inserting departments...")
        await departments.insert_departments()
        logger.succeed("Inserted departments")

        logger.start("Inserting designations...")
        await designations.insert_designations()
        logger.succeed("Inserted designations")

        logger.start(f"Inserting {n_employees} employees...")
        await employees.insert_employees(n_employees)
        logger.succeed(f"Inserted {n_employees} employees")

        logger.start("Updating employee reports to...")
        await employees.update_employee_reports_to()
        logger.succeed("Updated employee reports to")

        logger.start("Correcting employee statuses...")
        await employees.correct_employee_statuses()
        logger.succeed("Corrected employee statuses")

        logger.start("Updating employees salary data...")
        await employees.update_employees_salary_data()
        logger.succeed("Updated employees salary data")

        logger.start("Correcting employee relieving dates...")
        await employees.correct_employee_relieving_dates()
        logger.succeed("Corrected employee relieving dates")

        logger.start(f"Inserting {n_users} users...")
        await users.insert_users(n_users)
        logger.succeed(f"Inserted {n_users} users")

        logger.start("Creating user groups...")
        await users.create_user_groups()
        logger.succeed("Created user groups")

        logger.start(f"Inserting {n_job_openings} job openings...")
        await recruitments.insert_job_openings(n_job_openings)
        logger.succeed(f"Inserted {n_job_openings} job openings")

        logger.start(f"Inserting {n_job_applicants} job applicants...")
        await recruitments.insert_job_applicants(n_job_applicants)
        logger.succeed(f"Inserted {n_job_applicants} job applicants")

        logger.start("Inserting job offer terms...")
        await recruitments.insert_job_offer_terms()
        logger.succeed("Inserted job offer terms")

        logger.start(f"Inserting {n_job_offerings} job offerings...")
        await recruitments.insert_job_offerings(n_job_offerings)
        logger.succeed(f"Inserted {n_job_offerings} job offerings")

        logger.start(f"Inserting {n_promomotions} promotions...")
        await employees.insert_promomotions(n_promomotions)
        logger.succeed(f"Inserted {n_promomotions} promotions")

        logger.start(f"Inserting {n_transfers} transfers...")
        await employees.insert_transfers(n_transfers)
        logger.succeed(f"Inserted {n_transfers} transfers")

        logger.start(f"Inserting {n_separations} separations...")
        await employees.insert_separations(n_separations)
        logger.succeed(f"Inserted {n_separations} separations")

        logger.start("Inserting performance cycles...")
        await appraisals.insert_performance_cycles()
        logger.succeed("Inserted performance cycles")

        logger.start("Inserting appraisal templates...")
        await appraisals.insert_appraisal_templates(10)
        logger.succeed("Inserted appraisal templates")

        logger.start("Inserting appraisals...")
        await appraisals.insert_appraisals(100)
        logger.succeed("Inserted appraisals")

        logger.start("Inserting feedbacks...")
        await appraisals.insert_feedbacks(50)
        logger.succeed("Inserted feedbacks")

        logger.start("Inserting leave holidays...")
        await leaves.insert_leave_holidays()
        logger.succeed("Inserted leave holidays")

        logger.start("Assigning leave holidays...")
        await leaves.assign_leave_holidays()
        logger.succeed("Assigned leave holidays")

        logger.start("Inserting leave types...")
        await leaves.insert_leave_types()
        logger.succeed("Inserted leave types")

        logger.start("Assigning leave types...")
        await leaves.assign_leave_types()
        logger.succeed("Assigned leave types")

        logger.start("Updating leave approvers...")
        await leaves.update_leave_approvers()
        logger.succeed("Updated leave approvers")

        logger.start(f"Inserting {n_leave_allocations} leave allocations...")
        await leaves.insert_leave_allocations(n_leave_allocations)
        logger.succeed(f"Inserted {n_leave_allocations} leave allocations")

        logger.start(f"Inserting {n_leave_applications} leave applications...")
        await leaves.insert_leave_applications(n_leave_applications)
        logger.succeed(f"Inserted {n_leave_applications} leave applications")

        logger.start("Inserting attendances...")
        await attendances.insert_attendances(n_employees)
        logger.succeed("Inserted attendances")

        logger.start("Inserting expense accounts...")
        await expenses.insert_expense_accounts()
        logger.succeed("Inserted expense accounts")

        logger.start("Inserting expense claim types...")
        await expenses.insert_expense_claim_types()
        logger.succeed("Inserted expense claim types")

        logger.start("Assigning expense claim types...")
        await expenses.assign_expense_claim_types()
        logger.succeed("Assigned expense claim types")

        logger.start("Assigning expense approvers...")
        await expenses.assign_expense_approvers()
        logger.succeed("Assigned expense approvers")

        logger.start("Inserting suppliers...")
        await expenses.insert_suppliers()
        logger.succeed("Inserted suppliers")

        logger.start(f"Inserting {n_expense_claims} expense claims...")
        await expenses.insert_expense_claims(n_expense_claims)
        logger.succeed(f"Inserted {n_expense_claims} expense claims")

        logger.start("Inserting income tax slabs...")
        await taxes.insert_income_tax_slabs()
        logger.succeed("Inserted income tax slabs")

        logger.start("Inserting cost centers...")
        await salaries.insert_cost_centers()
        logger.succeed("Inserted cost centers")

        logger.start("Inserting fiscal years...")
        await salaries.insert_fiscal_years()
        logger.succeed("Inserted fiscal years")

        logger.start("Inserting salary components...")
        await salaries.insert_salary_components()
        logger.succeed("Inserted salary components")

        logger.start("Inserting salary structures...")
        await salaries.insert_salary_structures()
        logger.succeed("Inserted salary structures")

        logger.start("Inserting salary structure assignments...")
        await salaries.insert_salary_structure_assignments()
        logger.succeed("Inserted salary structure assignments")

        logger.start("Inserting payroll entries...")
        await salaries.insert_payroll_entries(from_date="2024-01-01")
        logger.succeed("Inserted payroll entries")

        logger.start("Updating salary slips...")
        await salaries.update_salary_slips()
        logger.succeed("Updated salary slips")

        logger.start("Submitting payroll entries...")
        await salaries.submit_payroll_entries()
        logger.succeed("Submitted payroll entries")

        logger.info("🎉 Seeding completed successfully!")

    asyncio.run(async_seed())
