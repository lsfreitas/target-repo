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

def create_and_checkout_branch(repo, target_branch, new_branch_name):
    try:
        repo.git.checkout(target_branch)
        logging.info(f"Checked out target branch: {target_branch}")
        if new_branch_name in repo.branches:
            repo.git.checkout(new_branch_name)
            logging.info(f"Checked out existing branch: {new_branch_name}")
        else:
            repo.git.checkout('-b', new_branch_name) # Create a new branch from the target branch
            logging.info(f"Created and checked out new branch: {new_branch_name}")
    except GitCommandError as e:
        logging.error(f"Failed to checkout and create branch: {e}")
        raise e

def fetch_branch(repo, remote_name, branch_name):
    try:
        remote = repo.remotes[remote_name]
        remote.fetch(branch_name)
        logging.info(f"Fetched branch '{branch_name}' from remote '{remote_name}'")
    except GitCommandError as e:
        logging.error(f"Failed to fetch branch '{branch_name}' from remote '{remote_name}': {e}")
        raise e

def push_branch(repo, branch_name):
    try:
        repo.git.push('origin', branch_name)
        logging.info(f"Pushed branch '{branch_name}' to remote 'origin'")
    except GitCommandError as e:
        logging.error(f"Failed to push branch '{branch_name}': {e}")
        raise e

def branch_exists_in_remote(repo, branch_name):
    try:
        branches = repo.git.ls_remote('--heads', 'origin', branch_name)
        return bool(branches)
    except GitCommandError as e:
        logging.error(f"Error checking if branch exists in remote: {e.stderr}")
        return False

def setup_repo_sync(target_repo_url, source_repo_url, target_branch, source_branch):
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
            if 'source' not in [remote.name for remote in repo.remotes]:
                repo.create_remote('source', source_repo_url)
                logging.info(f"Added remote 'source' with URL '{source_repo_url}' to the repository.")
            
            # Log the list of remotes after adding the new remote
            logging.info("Current remotes in the repository:")
            for remote in repo.remotes:
                for url in remote.urls:
                    logging.info(f"Remote name: {remote.name}, URL: {url}")
            
            logging.info(f"Sync process completed for repository: {target_repo_url}")
            
            # Check if the sync-branch exists in the remote repository
            new_branch = 'sync-branch'
            if branch_exists_in_remote(repo, new_branch):
                logging.info(f"Branch '{new_branch}' already exists in the remote repository. Checking it out.")
                repo.git.checkout(new_branch)
            else:
                create_and_checkout_branch(repo, target_branch, new_branch)
            
            # Fetch the source branch from the source remote
            fetch_branch(repo, 'source', source_branch)
            
            # Push the merged branch to the remote repository
            push_branch(repo, new_branch)
            
            return repo
    except GitCommandError as e:
        logging.error(f"Failed to clone or fetch repository: {e}")
        raise e
    except GithubException as e:
        logging.error(f"GitHub error: {e}")
        raise e

def main():
    target_repo_url, source_repo_url, target_branch, source_branch, github_token = check_env_vars()
    repo = setup_repo_sync(target_repo_url, source_repo_url, target_branch, source_branch)

if __name__ == "__main__":
    main()