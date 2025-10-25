#!/usr/bin/env python3
"""
Wait for GitLab to be ready before starting import
"""

import os
import sys
import time

import requests


GITLAB_URL = os.getenv("GITLAB_URL", "http://gitlab:80")
MAX_RETRIES = 60  # 10 minutes with 10s intervals
RETRY_INTERVAL = 10


def check_gitlab_health():
    """Check if GitLab is ready to accept requests"""
    try:
        # Check basic connectivity
        response = requests.get(f"{GITLAB_URL}", timeout=5)
        if response.status_code in [200, 302]:
            print(f"✅ GitLab is responding at {GITLAB_URL}")

            # Check API endpoint
            api_response = requests.get(f"{GITLAB_URL}/api/v4/version", timeout=5)
            if api_response.status_code == 200:
                version_info = api_response.json()
                print(f"✅ GitLab API is ready - Version: {version_info.get('version', 'Unknown')}")
                return True
            else:
                print(f"⏳ GitLab API not ready yet (HTTP {api_response.status_code})")
                return False
        else:
            print(f"⏳ GitLab not ready yet (HTTP {response.status_code})")
            return False

    except requests.exceptions.RequestException as e:
        print(f"⏳ Waiting for GitLab... ({e})")
        return False


def main():
    print(f"🔍 Checking GitLab availability at {GITLAB_URL}")

    for attempt in range(1, MAX_RETRIES + 1):
        print(f"Attempt {attempt}/{MAX_RETRIES}")

        if check_gitlab_health():
            print("🎉 GitLab is ready for imports!")
            return 0

        if attempt < MAX_RETRIES:
            print(f"⏱️  Waiting {RETRY_INTERVAL}s before next attempt...")
            time.sleep(RETRY_INTERVAL)

    print(f"❌ GitLab did not become ready within {MAX_RETRIES * RETRY_INTERVAL}s")
    return 1


if __name__ == "__main__":
    sys.exit(main())
