import os
import logging

logging.basicConfig(level=logging.INFO)

def check_env_vars():
    target_repo_url = os.getenv('TARGET_REPO_URL', 'git@github.com:lsfreitas/target-repo.git')
    source_repo_url = os.getenv('SOURCE_REPO_URL', 'git@github.com:lsfreitas/source-repo.git')
    target_branch = os.getenv('TARGET_BRANCH', 'main')
    source_branch = os.getenv('SOURCE_BRANCH', 'main')
    github_token = os.getenv('GITHUB_TOKEN')

    if not target_repo_url:
        logging.error("TARGET_REPO_URL environment variable must be set.")
    if not source_repo_url:
        logging.error("SOURCE_REPO_URL environment variable must be set.")
    if not target_branch:
        logging.error("TARGET_BRANCH environment variable must be set.")
    if not source_branch:
        logging.error("SOURCE_BRANCH environment variable must be set.")
    if not github_token:
        logging.error("GITHUB_TOKEN environment variable must be set.")

    return target_repo_url, source_repo_url, target_branch, source_branch, github_token

def main():
    # Load and validate environment variables
    target_repo_url, source_repo_url, target_branch, source_branch, github_token = check_env_vars()

if __name__ == "__main__":
    main()