import os
import logging
import tempfile
from github import Github, GithubException
from git import Repo, GitCommandError

# Configure logging at the beginning of the file
logging.basicConfig(level=logging.INFO, format='%(levelname)s - %(message)s')

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

def setup_repo_sync(target_repo_url, source_repo_url):
    logging.info(f"Starting sync process for repository: {target_repo_url}")
    try:
        with tempfile.TemporaryDirectory() as repo_path:
            logging.info(f"Created temporary directory at {repo_path}")
            
            logging.info(f"Cloning repository from {target_repo_url} into {repo_path}")
            repo = Repo.clone_from(target_repo_url, repo_path)
            logging.info(f"Successfully cloned repository from {target_repo_url} into {repo_path}")
            
            logging.info(f"Fetching latest changes for repository at {repo_path}")
            repo.remotes.origin.fetch()
            logging.info(f"Successfully fetched latest changes for repository at {repo_path}")
            
            logging.info("Adding source remote:")
            repo.create_remote('source', source_repo_url)
            logging.info(f"Added remote 'source' with URL '{source_repo_url}' to the repository.")
            
            # Log the list of remotes after adding the new remote
            logging.info("Current remotes in the repository:")
            for remote in repo.remotes:
                for url in remote.urls:
                    logging.info(f"Remote name: {remote.name}, URL: {url}")
            
            logging.info(f"Sync process completed for repository: {target_repo_url}")
            return repo
    except GitCommandError as e:
        logging.error(f"Failed to clone or fetch repository: {e}")
        raise e
    except GithubException as e:
        logging.error(f"GitHub error: {e}")
        raise e

def main():
    target_repo_url, source_repo_url, target_branch, source_branch, github_token = check_env_vars()
    setup_repo_sync(target_repo_url, source_repo_url)

if __name__ == "__main__":
    main()