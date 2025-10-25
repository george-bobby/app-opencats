"""
Fix GitLab Issues and MRs Created by Import User

This script:
1. Uses GitLab API to get projects and members
2. Directly updates the database to change issue/MR authors from "Import User" to random project members
3. Ensures each project's issues/MRs are assigned to actual members of that project

IMPORTANT: This directly modifies the database. Always backup first!

Usage:
    python fix_create_user_name.py --dry-run
    python fix_create_user_name.py --execute
"""

import random
import sys
from pathlib import Path

import psycopg2

from apps.gitlab.core.gitlab_client import GitLabClient
from common.logger import logger


# Add the src directory to Python path
if __name__ == "__main__":
    src_dir = Path(__file__).parent.parent.parent.parent
    if src_dir not in sys.path:
        sys.path.insert(0, str(src_dir))


class DirectDBImportUserFixer:
    """Fixes Import User issues and MRs using API + direct database updates"""

    def __init__(self, db_config: dict):
        self.db_config = db_config
        self.conn = None
        self.gitlab = GitLabClient()
        self.import_user_id = None

    def connect_db(self):
        """Connect to GitLab PostgreSQL database"""
        try:
            self.conn = psycopg2.connect(**self.db_config)
            logger.succeed("Connected to GitLab database")
            return True
        except Exception as e:
            logger.fail(f"Failed to connect to database: {e}")
            return False

    def find_import_user_id(self):
        """Find the Import User ID using GitLab API"""
        logger.info("Finding Import User via API...")

        # Search for users with "import" in username or name
        response = self.gitlab._request("GET", "/users?search=import")
        if not response or response.status_code != 200:
            logger.fail("Failed to search for import user via API")
            return None

        users = response.json()
        for user in users:
            user_id = user["id"]
            username = user["username"]
            name = user["name"]
            logger.info(f"Found potential Import User: {name} ({username}) - ID: {user_id}")

            # Usually the import user has "import" in the name
            if "import" in name.lower():
                self.import_user_id = user_id
                logger.info(f"Using Import User ID: {user_id}")
                return user_id

        if users:
            # If no exact match, use the first one found
            self.import_user_id = users[0]["id"]
            logger.info(f"Using first found user as Import User ID: {self.import_user_id}")
            return self.import_user_id

        logger.warning("No Import User found")
        return None

    def get_all_projects_via_api(self):
        """Get all projects using GitLab API"""
        logger.info("Fetching projects via API...")

        projects = []
        page = 1
        per_page = 100

        while True:
            response = self.gitlab._request("GET", f"/projects?page={page}&per_page={per_page}&simple=true")
            if not response or response.status_code != 200:
                break

            project_list = response.json()
            if not project_list:
                break

            projects.extend(project_list)

            if len(project_list) < per_page:
                break
            page += 1

        logger.info(f"Found {len(projects)} projects via API")
        return projects

    def get_project_members_via_api(self, project_id):
        """Get project members using GitLab API"""
        members = []
        page = 1
        per_page = 100

        while True:
            response = self.gitlab._request("GET", f"/projects/{project_id}/members?page={page}&per_page={per_page}")
            if not response or response.status_code != 200:
                break

            project_members = response.json()
            if not project_members:
                break

            # Filter active members (exclude bots and inactive users)
            for member in project_members:
                if member.get("state") == "active" and not member.get("bot", False) and member.get("username") not in ["root", "ghost"]:
                    members.append({"user_id": member["id"], "username": member["username"], "name": member["name"]})

            if len(project_members) < per_page:
                break
            page += 1

        return members

    def get_all_project_members_map(self):
        """Get project members for all projects using API"""
        logger.info("Getting project members via API...")

        # Get all projects first
        projects = self.get_all_projects_via_api()

        project_members = {}
        for project in projects:
            project_id = project["id"]
            project_name = project["name"]

            logger.info(f"Getting members for project: {project_name}")
            members = self.get_project_members_via_api(project_id)

            if members:
                project_members[project_id] = members
                logger.info(f"  Found {len(members)} members")
            else:
                logger.warning("  No members found")

        logger.info(f"Found members for {len(project_members)} projects")
        return project_members

    def get_import_user_issues(self):
        """Get all issues created by Import User from database"""
        cursor = self.conn.cursor()

        cursor.execute(
            """
            SELECT i.id, i.iid, i.project_id, i.title, p.name as project_name
            FROM issues i
            JOIN projects p ON i.project_id = p.id
            WHERE i.author_id = %s
            ORDER BY i.project_id, i.id
        """,
            (self.import_user_id,),
        )

        issues = cursor.fetchall()
        logger.info(f"Found {len(issues)} issues created by Import User")
        return issues

    def get_import_user_merge_requests(self):
        """Get all merge requests created by Import User from database"""
        cursor = self.conn.cursor()

        cursor.execute(
            """
            SELECT mr.id, mr.iid, mr.target_project_id as project_id, mr.title, p.name as project_name
            FROM merge_requests mr
            JOIN projects p ON mr.target_project_id = p.id
            WHERE mr.author_id = %s
            ORDER BY mr.target_project_id, mr.id
        """,
            (self.import_user_id,),
        )

        merge_requests = cursor.fetchall()
        logger.info(f"Found {len(merge_requests)} merge requests created by Import User")
        return merge_requests

    def update_issues(self, issues, project_members, dry_run=True):
        """Update issue authors"""
        cursor = self.conn.cursor()
        updated_count = 0

        for issue_id, issue_iid, project_id, title, project_name in issues:
            if project_id not in project_members or not project_members[project_id]:
                logger.warning(f"No members found for project {project_name}, skipping issue #{issue_iid}")
                continue

            # Pick random member from project
            random_member = random.choice(project_members[project_id])
            new_author_id = random_member["user_id"]
            new_author_username = random_member["username"]

            if dry_run:
                logger.info(f"[DRY RUN] Issue #{issue_iid} in {project_name}: '{title[:50]}...' -> {new_author_username}")
            else:
                cursor.execute(
                    """
                    UPDATE issues 
                    SET author_id = %s, updated_at = NOW()
                    WHERE id = %s AND author_id = %s
                """,
                    (new_author_id, issue_id, self.import_user_id),
                )

                if cursor.rowcount > 0:
                    logger.succeed(f"Updated issue #{issue_iid} in {project_name}: '{title[:50]}...' -> {new_author_username}")
                    updated_count += 1
                else:
                    logger.fail(f"Failed to update issue #{issue_iid}")

        return updated_count

    def update_merge_requests(self, merge_requests, project_members, dry_run=True):
        """Update merge request authors"""
        cursor = self.conn.cursor()
        updated_count = 0

        for mr_id, mr_iid, project_id, title, project_name in merge_requests:
            if project_id not in project_members or not project_members[project_id]:
                logger.warning(f"No members found for project {project_name}, skipping MR !{mr_iid}")
                continue

            # Pick random member from project
            random_member = random.choice(project_members[project_id])
            new_author_id = random_member["user_id"]
            new_author_username = random_member["username"]

            if dry_run:
                logger.info(f"[DRY RUN] MR !{mr_iid} in {project_name}: '{title[:50]}...' -> {new_author_username}")
            else:
                cursor.execute(
                    """
                    UPDATE merge_requests 
                    SET author_id = %s, updated_at = NOW()
                    WHERE id = %s AND author_id = %s
                """,
                    (new_author_id, mr_id, self.import_user_id),
                )

                if cursor.rowcount > 0:
                    logger.succeed(f"Updated MR !{mr_iid} in {project_name}: '{title[:50]}...' -> {new_author_username}")
                    updated_count += 1
                else:
                    logger.fail(f"Failed to update MR !{mr_iid}")

        return updated_count

    def run(self, dry_run=True):
        """Main execution function"""
        logger.start("Starting direct database Import User fix...")

        if not self.connect_db():
            return

        try:
            # Find Import User
            if not self.find_import_user_id():
                return

            # Get project members mapping via API
            project_members = self.get_all_project_members_map()
            if not project_members:
                logger.warning("No project members found")
                return

            # Get issues and MRs to update
            issues = self.get_import_user_issues()
            merge_requests = self.get_import_user_merge_requests()

            # Check total counts to understand the data
            cursor = self.conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM issues")
            total_issues = cursor.fetchone()[0]
            cursor.execute("SELECT COUNT(*) FROM merge_requests")
            total_mrs = cursor.fetchone()[0]
            cursor.execute("SELECT COUNT(*) FROM users WHERE LOWER(name) LIKE '%import%'")
            import_users_count = cursor.fetchone()[0]

            logger.info("\nDatabase Overview:")
            logger.info(f"  • Total issues in database: {total_issues}")
            logger.info(f"  • Total merge requests in database: {total_mrs}")
            logger.info(f"  • Users with 'import' in name: {import_users_count}")
            logger.info(f"  • Issues by Import User (ID {self.import_user_id}): {len(issues)}")
            logger.info(f"  • MRs by Import User (ID {self.import_user_id}): {len(merge_requests)}")

            if not issues and not merge_requests:
                logger.warning("\nNo issues or merge requests found for Import User")
                logger.info("This could mean:")
                logger.info("1. All issues/MRs have already been fixed")
                logger.info("2. The Import User ID is different")
                logger.info("3. Issues/MRs are created by a different user")

                # Check what users have created the most issues/MRs
                cursor.execute(
                    """
                    SELECT u.name, u.username, u.id, COUNT(i.id) as issue_count
                    FROM users u
                    LEFT JOIN issues i ON u.id = i.author_id
                    GROUP BY u.id, u.name, u.username
                    HAVING COUNT(i.id) > 0
                    ORDER BY issue_count DESC
                    LIMIT 5
                """
                )
                top_issue_creators = cursor.fetchall()

                logger.info("\nTop 5 issue creators:")
                for name, username, user_id, count in top_issue_creators:
                    logger.info(f"  • {name} ({username}) - ID: {user_id} - {count} issues")

                return

            # Update issues
            issues_updated = 0
            if issues:
                logger.info(f"\n📝 Processing {len(issues)} issues...")
                issues_updated = self.update_issues(issues, project_members, dry_run)

            # Update merge requests
            mrs_updated = 0
            if merge_requests:
                logger.info(f"\n🔀 Processing {len(merge_requests)} merge requests...")
                mrs_updated = self.update_merge_requests(merge_requests, project_members, dry_run)

            # Commit changes if not dry run
            if not dry_run:
                self.conn.commit()
                logger.succeed("Database changes committed")
            else:
                logger.succeed("Dry run completed - no changes made")

            # Summary
            logger.succeed(f"{'[DRY RUN] ' if dry_run else ''}Process completed!")
            logger.info(f"  • Issues updated: {issues_updated}")
            logger.info(f"  • Merge Requests updated: {mrs_updated}")
            logger.info(f"  • Total updates: {issues_updated + mrs_updated}")

        except Exception as e:
            logger.fail(f"Error during processing: {e}")
            if not dry_run:
                self.conn.rollback()
                logger.warning("Database changes rolled back")
        finally:
            if self.conn:
                self.conn.close()


def main():
    """Main function"""

    # Database configuration - UPDATE THESE WITH YOUR ACTUAL GITLAB DATABASE SETTINGS!
    db_config = {
        "host": "",  # Your GitLab database host
        "port": "",  # Your GitLab database port
        "database": "",  # Your GitLab database name
        "user": "",  # Your GitLab database username
        "password": "",  # UPDATE THIS!
    }

    logger.warning("IMPORTANT: Update the database configuration above with your actual GitLab database settings!")
    logger.info(f"Current config: host={db_config['host']}, database={db_config['database']}, user={db_config['user']}")

    dry_run = "--dry-run" in sys.argv
    execute = "--execute" in sys.argv

    if not dry_run and not execute:
        logger.fail("Please specify either --dry-run or --execute")
        logger.info("Usage:")
        logger.info("  python direct_db_fix_import_user.py --dry-run   # Show what would be updated")
        logger.info("  python direct_db_fix_import_user.py --execute   # Actually update the database")
        return

    if execute:
        logger.warning("EXECUTING MODE - This will modify your database!")
        logger.warning("Make sure you have backed up your GitLab database!")

        confirm = input("Are you sure you want to proceed? Type 'YES' to continue: ")
        if confirm != "YES":
            logger.info("Operation cancelled")
            return

    fixer = DirectDBImportUserFixer(db_config)
    fixer.run(dry_run=dry_run)


if __name__ == "__main__":
    main()
