import os
import logging
import tempfile
from github import Github, GithubException
from git import Repo, GitCommandError

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
            repo.git.checkout('-b', new_branch_name)  # Create a new branch from the target branch
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

def merge_branches(repo, source_branch, new_branch):
    try:
        logging.info(f"Attempting to merge {source_branch} into {new_branch}")
        # Using --allow-unrelated-histories to allow merging unrelated histories
        repo.git.merge(source_branch, '--allow-unrelated-histories')
        logging.info(f"Merge of {source_branch} into {new_branch} successful")
        return True  # Merge was successful
    except GitCommandError as e:
        if 'CONFLICT' in str(e):
            logging.error(f"Merge conflict detected while merging {source_branch} into {new_branch}")
            
            # Add and commit the conflicted state to push the changes with conflicts
            logging.info("Staging conflicted files")
            repo.git.add(A=True)  # Add all files (even conflicted)
            
            logging.info("Committing the conflicted state")
            repo.git.commit('-m', f"Merge conflict between {new_branch} and {source_branch}")
            
            return False  # Merge conflict detected
        else:
            logging.error(f"Failed to merge branch {source_branch}: {e}")
            raise e

def get_commits_between_branches(repo, target_branch, new_branch, repo_full_name):
    """Get the list of commits between two branches, including their SHAs and GitHub links."""
    commits = list(repo.iter_commits(f'{target_branch}..{new_branch}'))
    
    # Reverse the commits to show them from oldest to newest
    commits.reverse()
    
    commit_messages = []
    for commit in commits:
        sha = commit.hexsha[:7]  # Shorten the SHA to 7 characters (standard GitHub format)
        message = commit.message.strip()
        commit_url = f"https://github.com/{repo_full_name}/commit/{commit.hexsha}"
        commit_messages.append(f"- [{sha}]({commit_url}): {message}")
    
    return "\n".join(commit_messages)

def create_pull_request(github_token, repo_full_name, new_branch, target_branch, is_draft, commit_messages):
    try:
        g = Github(github_token)
        repo = g.get_repo(repo_full_name)

        # Check if a pull request already exists for the sync-branch
        pulls = repo.get_pulls(state='open', head=f"{repo_full_name.split('/')[0]}:{new_branch}", base=target_branch)
        if pulls.totalCount > 0:
            logging.info(f"A pull request already exists for {new_branch} -> {target_branch}. Skipping PR creation.")
            return

        # Create the pull request if no existing one was found
        pr_body = f"PR created to sync changes from {target_branch} to {new_branch}.\n\n### Commits included in this PR:\n{commit_messages}"
        pr = repo.create_pull(
            title=f"Sync {new_branch} with {target_branch}",
            body=pr_body,
            head=new_branch,
            base=target_branch,
            draft=is_draft  # Mark as draft if there are conflicts
        )
        logging.info(f"Pull request created: {pr.html_url}")
    except GithubException as e:
        logging.error(f"Failed to create pull request: {e}")
        raise e

def setup_repo_sync(target_repo_url, source_repo_url, target_branch, source_branch, github_token, repo_full_name):
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
            
            # Retrieve the list of commits between the branches (regardless of merge conflicts)
            commit_messages = get_commits_between_branches(repo, target_branch, new_branch, repo_full_name)

            # Attempt to merge the source branch into the new branch and check for conflicts
            if merge_branches(repo, f'source/{source_branch}', new_branch):
                push_branch(repo, new_branch)  # Push the merged branch if no conflicts
                logging.info("Merge completed successfully. No conflicts.")
                return True, commit_messages
            else:
                # Push the conflict state
                push_branch(repo, new_branch)
                logging.info(f"Conflict detected. Pushed branch '{new_branch}' with conflicts.")
                return False, commit_messages

    except GitCommandError as e:
        logging.error(f"Failed to clone or fetch repository: {e}")
        raise e
    except GithubException as e:
        logging.error(f"GitHub error: {e}")
        raise e


def main():
    target_repo_url, source_repo_url, target_branch, source_branch, github_token = check_env_vars()
    
    # Extract the repo name in the format "owner/repo-name"
    repo_full_name = target_repo_url.split(':')[1].replace('.git', '')

    # Setup the repository and handle sync
    merge_success, commit_messages = setup_repo_sync(target_repo_url, source_repo_url, target_branch, source_branch, github_token, repo_full_name)
    
    # Whether merge was successful or not, we still want to create a PR
    if merge_success:
        logging.info("Merge was successful. Creating regular pull request.")
        create_pull_request(github_token, repo_full_name, 'sync-branch', target_branch, is_draft=False, commit_messages=commit_messages)
    else:
        logging.info("Creating draft pull request due to conflicts.")
        create_pull_request(github_token, repo_full_name, 'sync-branch', target_branch, is_draft=True, commit_messages="")

if __name__ == "__main__":
    main()
