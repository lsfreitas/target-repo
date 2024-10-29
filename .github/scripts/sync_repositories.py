#!/usr/bin/env python3

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
    parser.add_argument('--target-repo', type=str, required=True, help='The GitHub repository where changes will be applied. Example: scylladb/scylla-enterprise-pkg')
    parser.add_argument('--source-repo', type=str, required=True, help='The GitHub repository from which changes will be merged. Example: scylladb/scylla-pkg')
    parser.add_argument('--target-branch', type=str, required=True, help='The branch in the target repository where changes will be merged. Example: next-enterprise')
    parser.add_argument('--source-branch', type=str, required=True, help='The branch in the source repository from which changes will be merged. Example: master')
    return parser.parse_args()

def sync_repos(args):
    try:
        github_token = os.getenv('GITHUB_TOKEN')
        if not github_token:
            raise ValueError("GitHub token not found. Please set the GITHUB_TOKEN environment variable.")
        
        # Step 1: Initialize GitHub client and get the repository
        g = Github(github_token)
        github_repo = g.get_repo(args.target_repo)

        with tempfile.TemporaryDirectory() as repo_path:
            # Step 2: Clone the target repository
            logging.info(f"Cloning target repository '{args.target_repo}' into temporary directory.")
            repo = Repo.clone_from(f'https://github.com/{args.target_repo}.git', repo_path)

            # Step 3: Add the source repository as a remote
            repo.create_remote('source', f'https://github.com/{args.source_repo}.git')
            logging.info(f"Added source repository '{args.source_repo}' as a remote.")

            # Step 4: Checkout the target branch and check if repos are in sync
            logging.info(f"Checking out target branch '{args.target_branch}'.")
            repo.git.checkout(args.target_branch)

            # Fetch the latest commit from the source branch
            logging.info(f"Fetching latest commit from source branch '{args.source_branch}'.")
            repo.git.fetch('source', args.source_branch)
            source_commit = repo.git.rev_parse(f'source/{args.source_branch}', short=7)
            logging.info(f"Latest commit from source repo: '{source_commit}'")

            # Check if the commit is already in the target branch
            try:
                # If source_commit is an ancestor of the latest commit in target_branch, this will return 0
                repo.git.merge_base('--is-ancestor', source_commit, args.target_branch)
                logging.info("Repositories are in sync. Skipping sync action.")
                return  # Exit the function early if the commit is already in the target branch
            except:
                logging.info("New commits available. Proceeding with sync.")

            sync_branch_name = f"sync-branch-{source_commit}"

            # Step 5: Check if there's any PR with the latest changes and created new branch for sync if there's none
            open_prs = github_repo.get_pulls(state='open', head=f"{args.target_repo.split('/')[0]}:{sync_branch_name}", base=args.target_branch)
            if open_prs.totalCount > 0:
                logging.info(f"There's already a PR open for the latest changes from {args.source_repo}. Check it here: {open_prs[0].html_url}")
                return  # Exit the function early if there's already a PR

            # Create a new branch for the sync
            logging.info(f"Creating new sync branch '{sync_branch_name}' from '{args.target_branch}'.")
            repo.git.checkout('-b', sync_branch_name)

            # Step 6: Merge the source branch into the sync branch
            is_draft = False
            try:
                logging.info(f"Merging source branch '{args.source_branch}' into sync branch '{sync_branch_name}'.")
                repo.git.merge(f'source/{args.source_branch}')
            except GitCommandError as e:
                logging.warning(f"Merge conflict detected. Attempting automatic conflict resolution.")
                is_draft = True  # Mark the PR as draft if there's a conflict
                repo.git.add(A=True)  # Stage changes to continue
                try:
                    repo.git.commit('--no-edit')  # Commit the resolution
                except GitCommandError as commit_error:
                    if 'nothing to commit' in str(commit_error):
                        logging.info(f"No changes detected after conflict resolution. Proceeding.")
                    else:
                        raise commit_error

            # Step 7: Push the new branch to the remote target repository
            repo.git.remote('set-url', 'origin', f'https://{github_token}@github.com/{args.target_repo}.git')
            logging.info(f"Pushing new branch '{sync_branch_name}' to the remote target repository.")
            repo.git.push('origin', sync_branch_name, force=True)
            
            # Step 8: Create a pull request with the merge
            pr_title = f"Sync repositories: from {args.source_repo} into {args.target_repo}"
            
            # Gather commits from the sync branch
            commit_log = repo.git.log(f'{args.target_branch}..{sync_branch_name}', '--no-merges', '--pretty=format:%h %s')
            # Create links to the commits in the pull request
            commit_links = []
            for line in commit_log.splitlines():
                commit_hash, commit_message = line.split(' ', 1)
                commit_links.append(f"[{commit_hash}](https://github.com/{args.target_repo}/commit/{commit_hash}) : {commit_message}")
            
            # Create a markdown list of commits
            commit_list = "\n".join(commit_links)
            pr_body = f"Applying changes from `{args.source_repo}`(branch: `{args.source_branch}`) into `{args.target_repo}`(branch: `{args.source_branch}`).\n\n### List of commits:\n{commit_list}"

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
