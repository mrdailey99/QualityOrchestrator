import os
from typing import Any, Optional


def get_pr_data(
    repo: str,
    pr_number: int,
    token: Optional[str] = None,
) -> dict[str, Any]:
    """Fetch PR metadata and changed file list from GitHub.

    Returns a dict with keys: repo, pr_number, title, author,
    files_changed (list[str]), diff (str), additions, deletions.
    """
    try:
        from github import Github
    except ImportError as exc:
        raise ImportError("PyGithub is required: pip install PyGithub") from exc

    token = token or os.getenv("GITHUB_TOKEN")
    g = Github(token, timeout=10)

    gh_repo = g.get_repo(repo)
    pr = gh_repo.get_pull(pr_number)

    files = [f for f in pr.get_files() if f.status != "removed"]
    file_paths = [f.filename for f in files]

    diff_parts: list[str] = []
    for f in files:
        if f.patch:
            diff_parts.append(f"--- a/{f.filename}\n+++ b/{f.filename}\n{f.patch}")
    diff = "\n".join(diff_parts)

    return {
        "repo": repo,
        "pr_number": pr_number,
        "title": pr.title,
        "author": pr.user.login,
        "files_changed": file_paths,
        "diff": diff,
        "additions": pr.additions,
        "deletions": pr.deletions,
    }
