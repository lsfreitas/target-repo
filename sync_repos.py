import argparse
import tempfile
import logging
import os
from datetime import datetime
from git import Repo, GitCommandError
from github import Github, GithubException

logging.basicConfig(level=logging.INFO, format='%(levelname)s - %(message)s')

def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument('--target-repo', type=str, required=True, help='The GitHub repository where changes will be applied.')
    parser.add_argument('--source-repo', type=str, required=True, help='The GitHub repository from which commits will be cherry-picked.')
    parser.add_argument('--target-branch', type=str, required=True, help='The branch in the target repository where changes will be applied.')
    parser.add_argument('--source-branch', type=str, required=True, help='The branch in the source repository from which commits will be cherry-picked.')
    return parser.parse_args()

def sync_repos(args):
    try:
        github_token = os.getenv('SYNC_REPOS_TOKEN')
        if not github_token:
            raise ValueError("GitHub token not found. Please set the SYNC_REPOS_TOKEN environment variable.")
        
        # Step 1: Initialize GitHub client and get the repository
        g = Github(github_token)
        github_repo = g.get_repo(args.target_repo)
        logging.info(f"Args: {args}")
        logging.info(f"Github repository: {github_repo}")
        logging.info(f"Found target repository: {github_repo.full_name}")

        with tempfile.TemporaryDirectory() as repo_path:
            # Step 2: Clone the target repository
            target_repo_url = f'https://github.com/{args.target_repo}.git'
            logging.info(f"Cloning target repository '{args.target_repo}' into temporary directory.")
            repo = Repo.clone_from(target_repo_url, repo_path)

            # Step 3: Add the source repository as a remote
            repo.create_remote('source', args.source_repo)
            logging.info(f"Added source repository '{args.source_repo}' as a remote.")

            # Step 4: Checkout the target branch and create the sync branch
            logging.info(f"Checking out target branch '{args.target_branch}'.")
            repo.git.checkout(args.target_branch)
            
            # Generate a unique sync branch name (timestamp + latest commit SHA)
            timestamp = datetime.now().strftime('%Y%m%d-%H%M%S')
            sync_branch_name = f"sync-branch-{timestamp}"

            logging.info(f"Creating new sync branch '{sync_branch_name}' from '{args.target_branch}'.")
            repo.git.checkout('-b', sync_branch_name)

            # Step 5: Fetch the source branch from the source repository
            logging.info(f"Fetching changes from source branch '{args.source_branch}' in source repository.")
            repo.git.fetch('source', args.source_branch)

            # Step 6: Cherry-pick commits from source to target
            commits = []
            is_draft = False
            for commit in reversed(list(repo.iter_commits(f'source/{args.source_branch}'))):
                commits.append(commit.hexsha)  # Track all commits, even those that cause conflicts
                try:
                    logging.info(f"Cherry-picking commit: {commit.hexsha}")
                    repo.git.cherry_pick(commit, '-m1', '-x')
                except GitCommandError:
                    logging.warning(f"Conflict detected on commit {commit.hexsha}. Automatically resolving.")
                    is_draft = True  # Mark PR as draft if there's a conflict
                    repo.git.add(A=True)  # Stage changes to continue
                    repo.git.cherry_pick('--continue')

            # Step 7: Push the new branch to the remote target repository
            logging.info(f"Pushing new branch '{sync_branch_name}' to the remote target repository.")
            repo.git.push('origin', sync_branch_name)
            
            # Step 8: Create a pull request with all commits, including those with conflicts
            pr_body = 'Cherry-picked commits:\n' + '\n'.join([f'- [Commit {commit[:7]}]({args.target_repo}/commit/{commit})' for commit in commits])
            pr_title = f"Sync changes from {args.source_branch} to {args.target_branch}"
            try:
                pull_request = github_repo.create_pull(
                    title=pr_title,
                    body=pr_body,
                    head=sync_branch_name,
                    base=args.target_branch,
                    draft=is_draft
                )
                logging.info(f"Pull request created: {pull_request.html_url}")
            except GithubException as e:
                logging.error(f"Failed to create pull request: {e}")

    except Exception as e:
        logging.error(f"An error occurred: {e}")

if __name__ == "__main__":
    args = parse_args()
    sync_repos(args)
