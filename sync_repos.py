import argparse
import tempfile
import logging
from git import Repo, GitCommandError

logging.basicConfig(level=logging.INFO, format='%(levelname)s - %(message)s')

def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument('--target', type=str, required=True, help='The GitHub repository where changes will be applied.')
    parser.add_argument('--source', type=str, required=True, help='The GitHub repository from which commits will be cherry-picked.')
    parser.add_argument('--target-branch', type=str, required=True, help='The branch in the target repository where changes will be applied.')
    parser.add_argument('--source-branch', type=str, required=True, help='The branch in the source repository from which commits will be cherry-picked.')
    parser.add_argument('--sync-branch', type=str, required=True, help='The new branch to create for the sync process.')
    return parser.parse_args()

def cherry_pick_commits(repo, source_branch):
    """Cherry-picks commits from the source branch one by one, handling conflicts automatically."""
    try:
        # Fetch the commits from the source branch
        source_commits = list(repo.iter_commits(f'source/{source_branch}'))
        for commit in reversed(source_commits):  # Reverse to apply them in chronological order
            logging.info(f"Cherry-picking commit: {commit.hexsha}")
            try:
                # Try to cherry-pick the commit with '-m1' and '-x'
                repo.git.cherry_pick(commit, '-m1', '-x')  # -m1 and -x to record commit info
            except GitCommandError as e:
                logging.warning(f"Conflict detected while cherry-picking commit {commit.hexsha}. Resolving conflict and continuing.")
                
                # Handle the conflict by staging changes and continuing
                repo.git.add(A=True)  # Stage all changes (resolved and conflicting files)
                try:
                    repo.git.cherry_pick('--continue')  # Continue the cherry-pick process
                    logging.info(f"Cherry-pick continued after resolving conflicts for commit {commit.hexsha}.")
                except GitCommandError as e:
                    logging.error(f"Failed to continue cherry-pick for commit {commit.hexsha}.")
                    raise e
    except GitCommandError as e:
        logging.error(f"Cherry-pick failed: {e}")
        raise e

def sync_repos_setup(target_repo_url, source_repo_url, target_branch, source_branch, sync_branch):
    try:
        with tempfile.TemporaryDirectory() as repo_path:
            # Clone the target repository
            logging.info(f"Cloning target repository from {target_repo_url} into {repo_path}")
            repo = Repo.clone_from(target_repo_url, repo_path)
            
            # Add source repository as a remote
            repo.create_remote('source', source_repo_url)
            logging.info(f"Added remote 'source' with URL '{source_repo_url}'")
            
            # Checkout the target branch
            repo.git.checkout(target_branch)
            logging.info(f"Checked out target branch '{target_branch}'")
            
            # Create and checkout the sync branch
            repo.git.checkout('-b', sync_branch)
            logging.info(f"Created and checked out new branch '{sync_branch}'")
            
            # Fetch the latest changes from the source branch
            repo.git.fetch('source', source_branch)
            logging.info(f"Fetched source branch '{source_branch}' from remote 'source'")
            
            # Cherry-pick the commits from the source branch into the new sync branch
            cherry_pick_commits(repo, source_branch)
            
            # Push the newly created branch to the remote target repository
            logging.info(f"Pushing new branch '{sync_branch}' to the remote repository.")
            repo.git.push('origin', sync_branch)
            logging.info(f"Successfully pushed branch '{sync_branch}' to the remote repository.")
            
    except GitCommandError as e:
        logging.error(f"Git command failed: {e}")
        raise e

if __name__ == "__main__":
    args = parse_args()
    sync_repos_setup(args.target, args.source, args.target_branch, args.source_branch, args.sync_branch)
