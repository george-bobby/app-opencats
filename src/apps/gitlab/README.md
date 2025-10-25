# GitLab - Steps to Replicate

## Prerequisites
- Docker and Docker Compose running
- Virtual environment activated: `source .venv/bin/activate`
- GitHub personal access token (for importing repositories)

## Setup Process

### 1. Start the container
```bash
python cli.py gitlab up
```

### 2. Setup GitLab Access Token
1. Wait 2-5 minutes for GitLab to fully start
2. Open `http://localhost` in your browser
3. Login with: `root` / `MyPassword@123`
4. Go to **Accounts -> Preferences -> Access Tokens**
5. Create token with all scopes.
6. Add this token to `settings.py`

### 3. Enable Import/Export Settings If not enabled
1. Go to **Admin Area** (wrench icon in bottom left)
2. Navigate to **Settings → General**
3. Expand **Import and export settings**
4. Enable all import featuers.
6. Click **Save changes**


### 4. Configure Repositories
Edit `config/settings.py` and update the `REPOSITORY_MAPPINGS` constant:
```python
REPOSITORY_MAPPINGS = {
    "my-repo": "https://github.com/username/my-repo",
    "another-repo": "https://github.com/username/another-repo",
    "simple-python": "https://github.com/username/simple-python",
    "hello-world": "https://github.com/username/hello-world"
}
```

### 5. Seed the database
```bash
python cli.py gitlab seed
```

## Available Commands
- `up` - Start GitLab services
- `down` - Stop services and cleanup
- `seed` - Import GitHub repositories to GitLab
- `status` - Check GitLab container status


> **Seeding Optimization Guide**

To achieve optimal seeding and realistic user attribution in imported repositories, follow this recommended process:

> **Important:**  
> **Before running any of the seeding or fix scripts below, you must:**
> 1. **Create a GitLab access token** (with all required scopes) from your GitLab instance.
> 2. **Add this token to your `settings.py` as `GITLAB_TOKEN`.**
> 3. **Pre-seed your GitLab application with users and any required base data.**
>
> Running these scripts on an empty GitLab instance or without a valid access token may result in incomplete or unrealistic user attribution, or failed API calls.

**Recommended Steps:**

1. **Run with `--fix-project-members` first (or ensure each project has members):**
   - This ensures every imported project has a pool of users/members.
   - Example:
     ```bash
     python cli.py gitlab seed --fix-project-members
     ```

2. **Then run with `--fix-create-user-name`:**
   - This step updates the `import_user` name for each issue and pull request, selecting randomly from the available project members.
   - **Note:** This fix is applied directly in the database; there is no GitLab API for this operation. The script connects to the database and updates the relevant records.
   - Example:
     ```bash
     python cli.py gitlab seed --fix-create-user-name
     ```

3. **Or combine both flags for a single optimized run:**
   - This ensures the correct order: project members are fixed/created before user attribution is updated.
   - Example:
     ```bash
     python cli.py gitlab seed --fix-project-members --fix-create-user-name
     ```

**Why this order?**
- The `fix-create-user-name` logic depends on having a pool of users in each project. If you run it before adding members, there may not be enough users to assign, resulting in less realistic or incomplete attribution.
- The `fix-create-user-name` operation is a direct database fix, not available via the GitLab API.

**Summary Table**

| Step | Flag                      | Purpose                                         |
|------|---------------------------|-------------------------------------------------|
| 1    | `--fix-project-members`   | Ensure each project has members                 |
| 2    | `--fix-create-user-name`  | Update import_user for issues/PRs (DB direct)   |

> **Best Practice:**  
> Always ensure project members exist before fixing user attribution for imported issues and PRs.  
> Also, always pre-seed your GitLab instance with users and base data, and make sure your access token is set in `settings.py` before running these scripts.
