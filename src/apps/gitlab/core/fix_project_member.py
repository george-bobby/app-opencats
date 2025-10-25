"""
Script to distribute GitLab users evenly across projects as members.
Ensures 1-1 mapping where each user is assigned to exactly one project.

Usage:
    python src/apps/gitlab/core/fix_project_member.py
    python src/apps/gitlab/core/fix_project_member.py --debug  # Enable debug mode

Or import and use programmatically:
    from apps.gitlab.core.fix_project_member import ProjectMemberDistributor
    distributor = ProjectMemberDistributor()
    distributor.run(access_level=30)  # 30 = Developer access
    distributor.run(access_level=30, debug_mode=True)  # With debugging

How it works:
1. Fetches all users from GitLab instance
2. Fetches all projects from GitLab instance
3. Identifies users who are NOT already members of any project
4. Distributes remaining users evenly across all projects
5. Adds users to projects with specified access level (default: Developer)

Example:
- 7 projects, 700 available users → 100 users per project
- 7 projects, 701 available users → first project gets 101, others get 100
- Ensures 1-to-1 mapping: each user belongs to exactly one project

Access Levels:
- 10 = Guest access
- 20 = Reporter access
- 30 = Developer access (default)
- 40 = Maintainer access
- 50 = Owner access
"""

import sys
import time
from pathlib import Path

from apps.gitlab.core.gitlab_client import GitLabClient
from common.logger import logger


# Add the src directory to Python path for standalone execution
if __name__ == "__main__":
    # Get the src directory (4 levels up from this file)
    src_dir = Path(__file__).parent.parent.parent.parent
    if src_dir not in sys.path:
        sys.path.insert(0, str(src_dir))


class ProjectMemberDistributor:
    """Handles distribution of users across projects as members"""

    def __init__(self):
        self.gitlab = GitLabClient()

    def test_connection(self) -> bool:
        """Test GitLab API connection"""
        logger.info("Testing GitLab API connection...")
        logger.info(f"GitLab URL: {self.gitlab.base_url}")

        response = self.gitlab._request("GET", "/user")
        if response and response.status_code == 200:
            user_data = response.json()
            logger.info(f"✓ Connected as: {user_data.get('name')} ({user_data.get('username')})")
            return True
        else:
            if response:
                logger.fail(f"✗ Connection failed: {response.status_code} - {response.text}")
            else:
                logger.fail("✗ Connection failed: No response")
            return False

    def debug_api_endpoints(self):
        """Debug different API endpoints to understand what's available"""
        logger.info("=== Debugging GitLab API Endpoints ===")

        # First, test basic connectivity and authentication
        logger.info("1. Testing basic API connectivity...")
        basic_endpoints = ["/version", "/user", "/application/settings"]

        for endpoint in basic_endpoints:
            logger.info(f"Testing basic endpoint: {endpoint}")
            response = self.gitlab._request("GET", endpoint)
            if response:
                logger.info(f"  Status: {response.status_code}")
                if response.status_code == 200:
                    try:
                        data = response.json()
                        if endpoint == "/version":
                            logger.info(f"  GitLab version: {data.get('version', 'Unknown')}")
                        elif endpoint == "/user":
                            logger.info(f"  Authenticated as: {data.get('name', 'Unknown')} ({data.get('username', 'Unknown')})")
                            logger.info(f"  User is admin: {data.get('is_admin', False)}")
                        elif endpoint == "/application/settings":
                            logger.info(f"  Import sources: {data.get('import_sources', [])}")
                    except Exception as e:
                        logger.fail(f"  JSON parse error: {e}")
                else:
                    logger.fail(f"  Error: {response.text[:200]}")
            else:
                logger.fail("  No response")

        logger.info("\n2. Testing project endpoints...")
        # Test different project endpoints
        endpoints_to_test = [
            "/projects",
            "/projects?simple=true",
            "/projects?owned=true",
            "/projects?membership=true",
            "/projects?visibility=public",
            "/projects?visibility=internal",
            "/projects?visibility=private",
            "/projects?per_page=5",
            "/projects?per_page=5&simple=true",
            "/projects?per_page=5&statistics=false",
            "/projects?archived=false",
            "/projects?order_by=id&sort=asc",
        ]

        for endpoint in endpoints_to_test:
            logger.info(f"Testing endpoint: {endpoint}")
            response = self.gitlab._request("GET", endpoint)
            if response:
                logger.info(f"  Status: {response.status_code}")
                if response.status_code == 200:
                    try:
                        data = response.json()
                        logger.info(f"  Projects found: {len(data)}")
                        if data and len(data) > 0:
                            project = data[0]
                            logger.info(f"  Sample project: {project.get('name', 'N/A')} (ID: {project.get('id', 'N/A')})")
                            logger.info(f"  Project keys: {list(project.keys())}")
                    except Exception as e:
                        logger.fail(f"  JSON parse error: {e}")
                elif response.status_code == 401:
                    logger.fail("  Authentication failed")
                elif response.status_code == 403:
                    logger.fail("  Access forbidden")
                elif response.status_code == 429:
                    logger.fail("  Rate limited")
                else:
                    logger.fail(f"  Error: {response.text[:200]}")
            else:
                logger.fail("  No response")

            time.sleep(0.5)

        logger.info("=== End Debug ===")
        return

    def get_all_users(self) -> dict[int, dict]:
        """Get all GitLab users"""
        logger.info("Fetching all GitLab users...")

        all_users = {}
        page = 1
        per_page = 100

        while True:
            endpoint = f"/users?page={page}&per_page={per_page}"
            logger.info(f"Making request to: {endpoint}")

            response = self.gitlab._request("GET", endpoint)

            if not response:
                logger.fail("No response from GitLab API")
                break

            logger.info(f"Response status code: {response.status_code}")

            if response.status_code != 200:
                logger.fail(f"API request failed with status {response.status_code}: {response.text}")
                break

            try:
                users = response.json()
                logger.info(f"Retrieved {len(users)} users on page {page}")
            except Exception as e:
                logger.fail(f"Failed to parse JSON response: {e}")
                logger.fail(f"Response text: {response.text}")
                break

            if not users:
                logger.info("No more users found, stopping pagination")
                break

            for user in users:
                # Skip root/admin users and bots
                if user.get("username") not in ["root", "ghost"] and not user.get("bot", False):
                    all_users[user["id"]] = {"id": user["id"], "username": user["username"], "name": user["name"], "email": user.get("email", ""), "state": user.get("state", "active")}
                    logger.info(f"Added user: {user['username']} (ID: {user['id']}, State: {user.get('state', 'active')})")

            page += 1

        logger.info(f"Found {len(all_users)} total users")
        return all_users

    def get_all_projects(self) -> dict[int, dict]:
        """Get all GitLab projects"""
        logger.info("Fetching all GitLab projects...")

        all_projects = {}
        page = 1
        per_page = 100

        while True:
            # Try different endpoint parameters to get all projects
            # Remove membership=false as it might be causing issues
            endpoint = f"/projects?page={page}&per_page={per_page}&simple=true"
            logger.info(f"Making request to: {endpoint}")

            response = self.gitlab._request("GET", endpoint)

            if not response:
                logger.fail("No response from GitLab API")
                logger.fail("This could be due to:")
                logger.fail("1. Network connectivity issues")
                logger.fail("2. Invalid GitLab URL or token")
                logger.fail("3. GitLab server not responding")
                logger.fail("4. Authentication issues")
                break

            logger.info(f"Response status code: {response.status_code}")

            if response.status_code == 401:
                logger.fail("Authentication failed - check your GITLAB_TOKEN")
                break
            elif response.status_code == 403:
                logger.fail("Access forbidden - user may not have permission to list projects")
                break
            elif response.status_code == 429:
                logger.fail("Rate limit exceeded - waiting 60 seconds before retry")

                time.sleep(60)
                continue
            elif response.status_code != 200:
                logger.fail(f"API request failed with status {response.status_code}: {response.text}")

                # Try alternative endpoints if the main one fails
                if page == 1:
                    logger.info("Trying alternative project endpoints...")
                    alternative_endpoints = [
                        f"/projects?page={page}&per_page={per_page}",
                        f"/projects?page={page}&per_page={per_page}&owned=true",
                        f"/projects?page={page}&per_page={per_page}&membership=true",
                        f"/projects?page={page}&per_page={per_page}&visibility=public",
                        f"/projects?page={page}&per_page={per_page}&visibility=internal",
                        f"/projects?page={page}&per_page={per_page}&visibility=private",
                    ]

                    for alt_endpoint in alternative_endpoints:
                        logger.info(f"Trying alternative endpoint: {alt_endpoint}")
                        alt_response = self.gitlab._request("GET", alt_endpoint)
                        if alt_response and alt_response.status_code == 200:
                            response = alt_response
                            logger.info(f"Success with alternative endpoint: {alt_endpoint}")
                            break

                    if response.status_code != 200:
                        logger.fail("All alternative endpoints failed")
                        break
                else:
                    break

            try:
                projects = response.json()
                logger.info(f"Retrieved {len(projects)} projects on page {page}")
            except Exception as e:
                logger.fail(f"Failed to parse JSON response: {e}")
                logger.fail(f"Response text: {response.text}")
                break

            if not projects:
                logger.info("No more projects found, stopping pagination")
                break

            for project in projects:
                # Handle both simple and full project responses
                project_id = project["id"]
                project_name = project.get("name", project.get("path", f"Project-{project_id}"))
                project_path = project.get("path", project.get("name", f"project-{project_id}"))
                project_web_url = project.get("web_url", f"{self.gitlab.base_url.replace('/api/v4', '')}/{project_path}")

                all_projects[project_id] = {"id": project_id, "name": project_name, "path": project_path, "web_url": project_web_url}
                logger.info(f"Added project: {project_name} (ID: {project_id})")

            # Check if we got a full page, if not, we're done
            if len(projects) < per_page:
                logger.info(f"Retrieved {len(projects)} projects (less than {per_page}), assuming last page")
                break

            page += 1

            # Safety check to prevent infinite loops
            if page > 1000:
                logger.warning("Reached maximum page limit (1000), stopping pagination")
                break

        logger.info(f"Found {len(all_projects)} total projects")
        return all_projects

    def get_project_members(self, project_id: int) -> set[int]:
        """Get all members of a specific project"""
        members = set()
        page = 1
        per_page = 100

        while True:
            response = self.gitlab._request("GET", f"/projects/{project_id}/members?page={page}&per_page={per_page}")
            if not response or response.status_code != 200:
                break

            project_members = response.json()
            if not project_members:
                break

            for member in project_members:
                members.add(member["id"])

            page += 1

        return members

    def get_users_already_in_projects(self, projects: dict[int, dict]) -> set[int]:
        """Get set of all user IDs that are already members of any project"""
        logger.info("Finding users who are already project members...")

        users_in_projects = set()

        for project_id, project_info in projects.items():
            logger.info(f"Checking members of project: {project_info['name']}")
            project_members = self.get_project_members(project_id)
            users_in_projects.update(project_members)

        logger.info(f"Found {len(users_in_projects)} users already in projects")
        return users_in_projects

    def distribute_users_to_projects(self, available_users: list[dict], projects: dict[int, dict]) -> dict[int, list[dict]]:
        """Distribute users evenly across projects"""
        num_projects = len(projects)
        num_users = len(available_users)

        if num_projects == 0:
            logger.fail("No projects available for distribution")
            return {}

        users_per_project = num_users // num_projects
        remaining_users = num_users % num_projects

        logger.info(f"Distributing {num_users} users across {num_projects} projects")
        logger.info(f"Each project will get {users_per_project} users, with {remaining_users} projects getting 1 extra user")

        distribution = {}
        user_index = 0

        project_ids = list(projects.keys())

        for i, project_id in enumerate(project_ids):
            # Calculate how many users this project should get
            users_for_this_project = users_per_project
            if i < remaining_users:  # First few projects get the extra users
                users_for_this_project += 1

            # Assign users to this project
            project_users = []
            for _ in range(users_for_this_project):
                if user_index < len(available_users):
                    project_users.append(available_users[user_index])
                    user_index += 1

            distribution[project_id] = project_users
            logger.info(f"Project '{projects[project_id]['name']}' will get {len(project_users)} users")

        return distribution

    def add_user_to_project(self, project_id: int, user_id: int, access_level: int = 30) -> bool:
        """Add a user to a project as a member

        Access levels:
        10 = Guest access
        20 = Reporter access
        30 = Developer access (default)
        40 = Maintainer access
        50 = Owner access
        """
        member_data = {"user_id": user_id, "access_level": access_level}

        response = self.gitlab._request("POST", f"/projects/{project_id}/members", member_data)

        if response and response.status_code == 201:
            return True
        elif response and response.status_code == 409:
            logger.warning(f"User {user_id} is already a member of project {project_id}")
            return True
        else:
            if response:
                logger.fail(f"Failed to add user {user_id} to project {project_id}: {response.status_code} - {response.text}")
            else:
                logger.fail(f"Failed to add user {user_id} to project {project_id}: No response")
            return False

    def execute_distribution(self, distribution: dict[int, list[dict]], projects: dict[int, dict], access_level: int = 30):
        """Execute the user distribution by adding users to projects"""
        logger.info("Starting user distribution to projects...")

        total_assignments = sum(len(users) for users in distribution.values())
        successful_assignments = 0
        failed_assignments = 0

        for project_id, users in distribution.items():
            project_name = projects[project_id]["name"]
            logger.info(f"Adding {len(users)} users to project '{project_name}'...")

            for user in users:
                success = self.add_user_to_project(project_id, user["id"], access_level)
                if success:
                    successful_assignments += 1
                    logger.info(f"✓ Added user '{user['username']}' to project '{project_name}'")
                else:
                    failed_assignments += 1
                    logger.fail(f"✗ Failed to add user '{user['username']}' to project '{project_name}'")

        logger.info(f"Distribution complete: {successful_assignments}/{total_assignments} successful, {failed_assignments} failed")

    def run(self, access_level: int = 30, debug_mode: bool = False):
        """Main execution function"""
        logger.info("Starting GitLab user-project distribution script...")

        # Test connection first
        if not self.test_connection():
            logger.fail("Cannot connect to GitLab API. Please check your configuration.")
            return

        # Run debug mode if requested or if we encounter issues
        if debug_mode:
            logger.info("Running in debug mode - will test various API endpoints")
            self.debug_api_endpoints()

        # Get all users and projects
        all_users = self.get_all_users()
        all_projects = self.get_all_projects()

        if not all_users:
            logger.fail("No users found in GitLab")
            if not debug_mode:
                logger.info("Running debug to understand the issue...")
                self.debug_api_endpoints()
            return

        if not all_projects:
            logger.fail("No projects found in GitLab")
            if not debug_mode:
                logger.info("Running debug to understand the issue...")
                self.debug_api_endpoints()
            return

        # Find users who are already project members
        users_in_projects = self.get_users_already_in_projects(all_projects)

        # Filter out users who are already project members
        available_users = []
        for user_id, user_info in all_users.items():
            if user_id not in users_in_projects and user_info["state"] == "active":
                available_users.append(user_info)

        logger.info(f"Available users for distribution: {len(available_users)}")

        if not available_users:
            logger.warning("No users available for distribution (all users are already project members)")
            return

        # Distribute users across projects
        distribution = self.distribute_users_to_projects(available_users, all_projects)

        # Execute the distribution
        self.execute_distribution(distribution, all_projects, access_level)

        logger.info("Script execution completed!")


def main():
    """Main function to run the distribution script"""

    distributor = ProjectMemberDistributor()

    # Check if debug mode is requested
    debug_mode = "--debug" in sys.argv or "-d" in sys.argv

    if debug_mode:
        logger.info("Debug mode enabled")

    # Run with Developer access level (30) by default
    # You can change this to:
    # 10 = Guest, 20 = Reporter, 30 = Developer, 40 = Maintainer, 50 = Owner
    distributor.run(access_level=30, debug_mode=debug_mode)


if __name__ == "__main__":
    main()
