import os
import requests
import git

def clone_repo(repo_url, repo_path):
    try:
        if not os.path.exists(repo_path):
            print(f"Cloning repository from {repo_url} into {repo_path}")
            return git.Repo.clone_from(repo_url, repo_path)
        else:
            repo = git.Repo(repo_path)
            print(f"Repository already exists at {repo_path}. Fetching latest changes...")
            repo.remotes.origin.fetch()
            print(f"Fetched latest changes from origin")
            return repo
    except git.exc.GitCommandError as e:
        print(f"Failed to clone or fetch from repository: {e}")
        raise e

def add_remote(repo, remote_name, remote_url):
    if remote_name not in [remote.name for remote in repo.remotes]:
        repo.create_remote(remote_name, remote_url)
        print(f"Added {remote_name} as remote with URL {remote_url}")

def fetch_branch(repo, remote_name, branch_name):
    remote = repo.remotes[remote_name]
    remote.fetch(f"{branch_name}:{remote_name}/{branch_name}")
    print(f"Fetched branch '{branch_name}' from remote '{remote_name}'")

def checkout_branch(repo, branch_name):
    repo.git.checkout(branch_name)
    print(f"Checked out to branch '{branch_name}'")

def create_auxiliary_branch(repo, base_branch, aux_branch_name):
    try:
        if aux_branch_name in repo.branches:
            print(f"Auxiliary branch '{aux_branch_name}' already exists. Checking it out.")
            repo.git.checkout(aux_branch_name)
        else:
            repo.git.checkout(base_branch)
            repo.git.checkout('-b', aux_branch_name)
            print(f"Created and checked out to new auxiliary branch '{aux_branch_name}'")
    except git.exc.GitCommandError as e:
        print(f"Error creating auxiliary branch: {e.stderr}")

def get_commits_to_merge(repo, source_branch, target_branch):
    try:
        commits = repo.git.rev_list(f"{target_branch}..{source_branch}").split('\n')
        return [commit for commit in commits if commit]
    except git.exc.GitCommandError as e:
        print(f"Error during commit comparison: {e.stderr}")
        return []

def merge_branches(repo, source_branch, aux_branch_name):
    try:
        repo.git.merge(source_branch, '--allow-unrelated-histories')
        print(f"Successfully merged '{source_branch}' into '{aux_branch_name}'")
        return True
    except git.exc.GitCommandError as e:
        print(f"Error during merge: {e.stderr}")
        return False

def push_changes(repo, branch_name):
    try:
        repo.remotes.origin.push(refspec=f'{branch_name}:{branch_name}')
        print(f"Successfully pushed the changes to '{branch_name}'")
    except git.exc.GitCommandError as e:
        print(f"Error during push: {e.stderr}")
        return False
    return True

def pull_request_exists(github_token, repo_url, aux_branch, target_branch):
    repo_name = repo_url.split(":")[1].replace(".git", "")
    api_url = f"https://api.github.com/repos/{repo_name}/pulls"
    headers = {"Authorization": f"token {github_token}"}
    
    params = {
        "head": aux_branch,
        "base": target_branch,
        "state": "open"
    }
    
    response = requests.get(api_url, headers=headers, params=params)
    
    if response.status_code == 200:
        pulls = response.json()
        if len(pulls) > 0:
            print(f"A pull request already exists for '{aux_branch}' to '{target_branch}'")
            return True
    else:
        print(f"Failed to check for existing pull requests: {response.status_code} {response.text}")
    
    return False

def create_pull_request(github_token, repo_url, aux_branch, target_branch, commit_list, draft=False):
    repo_name = repo_url.split(":")[1].replace(".git", "")
    api_url = f"https://api.github.com/repos/{repo_name}/pulls"
    headers = {"Authorization": f"token {github_token}"}
    body = f"Opening PR to merge changes from auxiliary branch '{aux_branch}' into '{target_branch}'.\n\nList of commits being merged:\n" + "\n".join(commit_list)
    data = {
        "title": f"Automated PR from {aux_branch} to {target_branch}",
        "head": aux_branch,
        "base": target_branch,
        "body": body,
        "draft": draft
    }

    if pull_request_exists(github_token, repo_url, aux_branch, target_branch):
        print(f"Skipping PR creation as it already exists.")
        return None

    response = requests.post(api_url, headers=headers, json=data)
    if response.status_code == 201:
        pr_url = response.json()['html_url']
        print(f"Pull request created successfully: {pr_url}")
        return pr_url
    else:
        print(f"Failed to create pull request: {response.json()}")
        return None

def get_commit_messages(repo, source_branch, target_branch):
    try:
        commits = repo.git.rev_list(f"{target_branch}..{source_branch}").split('\n')
        commit_messages = [f"{commit[:7]}: {repo.git.show('-s', '--format=%s', commit)}" for commit in commits if commit]
        return commit_messages
    except git.exc.GitCommandError as e:
        print(f"Error during commit message retrieval: {e.stderr}")
        return []

def get_merge_commit_message(repo, aux_branch_name):
    try:
        merge_commit = repo.git.rev_list('-n', '1', aux_branch_name).strip()
        merge_message = f"{merge_commit[:7]}: {repo.git.show('-s', '--format=%s', merge_commit)}"
        return merge_message
    except git.exc.GitCommandError as e:
        print(f"Error during merge commit message retrieval: {e.stderr}")
        return ""

def remove_remote(repo, remote_name):
    repo.delete_remote(remote_name)
    print(f"Removed remote '{remote_name}'")

def main():
    target_repo_url = os.getenv('TARGET_REPO_URL', 'git@github.com:lsfreitas/target-repo.git')
    source_repo_url = os.getenv('SOURCE_REPO_URL', 'git@github.com:lsfreitas/source-repo.git')
    target_branch = os.getenv('TARGET_BRANCH', 'main')
    source_branch = os.getenv('SOURCE_BRANCH', 'main')
    github_token = os.getenv('GITHUB_TOKEN')

    if not target_repo_url or not source_repo_url or not github_token:
        print("Error: TARGET_REPO_URL, SOURCE_REPO_URL, and GITHUB_TOKEN environment variables must be set.")
        return

    target_repo_path = "/tmp/target_repo"

    target_repo = clone_repo(target_repo_url, target_repo_path)
    print(f"Target repository cloned to {target_repo_path}")

    add_remote(target_repo, 'source_repo', source_repo_url)

    fetch_branch(target_repo, 'origin', target_branch)
    fetch_branch(target_repo, 'source_repo', source_branch)

    checkout_branch(target_repo, target_branch)

    aux_branch_name = f"aux-sync-{source_branch}"
    create_auxiliary_branch(target_repo, target_branch, aux_branch_name)

    commits_to_merge = get_commits_to_merge(target_repo, f'source_repo/{source_branch}', f'origin/{target_branch}')

    if not commits_to_merge:
        print("No new changes to merge from source repository.")
        remove_remote(target_repo, 'source_repo')
        return

    merge_success = merge_branches(target_repo, f'source_repo/{source_branch}', aux_branch_name)
    if not merge_success:
        print("Merge failed with conflicts. Creating draft pull request.")
        if push_changes(target_repo, aux_branch_name):
            commit_messages = get_commit_messages(target_repo, f'source_repo/{source_branch}', f'origin/{target_branch}')
            create_pull_request(github_token, target_repo_url, aux_branch_name, target_branch, commit_messages, draft=True)
        remove_remote(target_repo, 'source_repo')
        return

    if push_changes(target_repo, aux_branch_name):
        commit_messages = get_commit_messages(target_repo, f'source_repo/{source_branch}', f'origin/{target_branch}')
        merge_commit_message = get_merge_commit_message(target_repo, aux_branch_name)
        commit_messages.append(merge_commit_message)
        create_pull_request(github_token, target_repo_url, aux_branch_name, target_branch, commit_messages)
        remove_remote(target_repo, 'source_repo')

if __name__ == "__main__":
    main()