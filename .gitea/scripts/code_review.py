import fnmatch
import json
import os
import re
from typing import Any, Optional

import requests
from model import Model

ACCESS_TOKEN = os.getenv("ACCESS_TOKEN", "")
HEADERS = {"Authorization": f"token {ACCESS_TOKEN}"}

GITHUB_EVENT_PATH = os.getenv("GITHUB_EVENT_PATH")
try:
    with open(GITHUB_EVENT_PATH, "r") as f:
        EVENT_DATA = json.load(f)
except FileNotFoundError:
    print("Failed to load event data.")
    exit(1)

FULL_CONTEXT_MODEL_NAME = os.getenv("FULL_CONTEXT_MODEL", "")
SINGLE_CHUNK_MODEL_NAME = os.getenv("SINGLE_CHUNK_MODEL", "")
FULL_CONTEXT_API_KEY = os.getenv("FULL_CONTEXT_API_KEY", "")
SINGLE_CHUNK_API_KEY = os.getenv("SINGLE_CHUNK_API_KEY", "")

EXCLUDE_PATTERNS = os.getenv("EXCLUDE", "").split(",")


def get_diff() -> str | None:
    """Get code difference between base and head from Gitea.

    Returns:
        str | None: code difference between base and head, or None if failed to get diff
    """
    url = EVENT_DATA["pull_request"]["diff_url"]
    try:
        response = requests.get(url, headers=HEADERS)
        response.raise_for_status()
        return response.text
    except requests.RequestException as e:
        print(f"Failed to get diff: {e}")
        return None


def parse_diff(diff: str) -> list[dict[str, Any]]:
    """Parse diff into list of dicts.

    Args:
        diff: str, code difference between base and head

    Returns:
        list[dict[str, Any]]: list of dicts, each dict represents a code chunks
    """
    file_pattern = re.compile(
        r"(?s)diff --git a/(.+?) b/(.*?)\r?\n(.*?)(?=diff --git a/|$)", re.S
    )
    old_new_pattern = re.compile(r"(?m)^(---|\+\+\+)\s+(.*)$")
    hunk_pattern = re.compile(
        r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@(.*?)(?=^@@ |$)",
        re.MULTILINE | re.DOTALL,
    )
    list_diff = []
    for match in file_pattern.finditer(diff):
        diff_text = match.group(3)

        old_new_match = list(old_new_pattern.finditer(diff_text))
        if len(old_new_match) != 2:
            continue

        old_file = old_new_match[0].group(2)
        old_file = old_file.lstrip("a/") if old_file.startswith("a/") else old_file

        new_file = old_new_match[1].group(2)
        if new_file == "/dev/null":
            print("Neglict deleted file")
            continue
        new_file = new_file.lstrip("b/")

        hunk_match = hunk_pattern.search(diff_text)
        if hunk_match is None:
            continue
        old_idx = int(hunk_match.group(1))
        new_idx = int(hunk_match.group(3))
        remain_text = diff_text[hunk_match.end() + 1 :]
        diff_text = []
        for line in remain_text.splitlines():
            if line.startswith("-"):
                diff_text.append(f"{old_idx} {line}")
                old_idx += 1
            elif line.startswith("+"):
                diff_text.append(f"{new_idx} {line}")
                new_idx += 1
            else:
                diff_text.append(line)
        diff_text = "\n".join(diff_text)

        if any(fnmatch.fnmatch(new_file, pattern) for pattern in EXCLUDE_PATTERNS):
            print(f"Exclude file {new_file}")
            continue

        list_diff.append(
            {
                "file": new_file,
                "chunk": diff_text,
            }
        )
    return list_diff


def create_comment(
    file: str, ai_response: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Create comments for single chunk review.

    Args:
        file: str, file name
        ai_response: list[dict[str, Any]], AI response for single chunk review

    Returns:
        list[dict[str, Any]]: comments for single chunk review
    """
    comments = []
    for ai_response in ai_response:
        comments.append(
            {
                "body": f"[REVIEW] {ai_response['reviewComment']}",
                "path": file,
                "new_position": int(ai_response["lineNumber"]),
            }
        )
    return comments


def analyze_single_chunks(
    single_chunk_model: Model, parsed_diff: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Analyze single chunks and create comments.

    Args:
        single_chunk_model: AI Session for single chunk analysis
        parsed_diff: list[dict[str, Any]], parsed diff

    Returns:
        list[dict[str, Any]]: comments for single chunk review
    """
    comments = []
    title = EVENT_DATA["pull_request"]["title"]
    description = EVENT_DATA["pull_request"]["body"]
    for diff in parsed_diff:
        file = diff["file"]
        chunk = diff["chunk"]
        response = single_chunk_model.get_response_single_chunk(
            file, title, description, chunk
        )
        response = response.strip("`").lstrip("json").strip() or "[]"

        try:
            response_json = json.loads(response)
            new_comments = create_comment(file, response_json)
            comments.extend(new_comments)
        except json.JSONDecodeError:
            print(f"Failed to parse response: {response}")
            continue

    return comments


def get_file_content(file: str) -> str | None:
    """Get file content from Gitea.

    Args:
        file: str, file name

    Returns:
        str | None: file content, or None if failed to get file content
    """
    repo_url = EVENT_DATA["pull_request"]["head"]["repo"]["url"]
    branch = EVENT_DATA["pull_request"]["head"]["ref"]

    replaced_file = file.replace("/", "%2F")
    url = f"{repo_url}/raw/{branch}%2F{replaced_file}?ref={branch}"

    try:
        response = requests.get(url, headers=HEADERS)
        response.raise_for_status()
        return response.text
    except requests.RequestException as e:
        print(f"Failed to get file content: {e}")
        return None


def analyze_full_context(
    full_context_model: Model, parsed_diff: list[dict[str, Any]]
) -> str:
    """Analyze full context and create review.

    Args:
        full_context_model: AI Session for full context analysis
        parsed_diff: list[dict[str, Any]], parsed diff

    Returns:
        str: review for full context
    """
    file_contents = []
    for diff in parsed_diff:
        file = diff["file"]
        chunk = diff["chunk"]
        content = get_file_content(file)
        if content is None:
            continue
        file_contents.append(f"File: {file}")
        file_contents.append(content)
        file_contents.append(f"Diff: {chunk}")

    title = EVENT_DATA["pull_request"]["title"]
    description = EVENT_DATA["pull_request"]["body"]
    response = full_context_model.get_response_full_context(
        title, description, file_contents
    )
    response = response.strip("`").lstrip("markdown").strip()
    return response


def post_review(
    full_context_review: str, single_chunk_comments: list[dict[str, Any]]
) -> None:
    """Post review to Gitea.

    Args:
        full_context_review: str, review for full context
        single_chunk_comments: list[dict[str, Any]], comments for single chunk review
    """
    repo_url = EVENT_DATA["pull_request"]["head"]["repo"]["url"]
    pull_number = EVENT_DATA["number"]
    commit_id = EVENT_DATA["pull_request"]["head"]["sha"]
    url = f"{repo_url}/pulls/{pull_number}/reviews"
    data = {
        "body": full_context_review,
        "event": "COMMENT",
        "comments": single_chunk_comments,
        "commit_id": commit_id,
    }
    response = requests.post(url, headers=HEADERS, json=data)
    response.raise_for_status()


def main() -> None:
    """Code Reviewer for Gitea."""
    if EVENT_DATA["action"] not in ["opened", "synchronized"]:
        print("Unsupproted event.")
        return

    diff = get_diff()
    if diff is None:
        return
    elif not diff:
        print("No diff found.")
        return

    full_context_model = Model(
        model=FULL_CONTEXT_MODEL_NAME,
        api_key=FULL_CONTEXT_API_KEY,
        is_full_context=True,
    )
    single_chunk_model = Model(
        model=SINGLE_CHUNK_MODEL_NAME,
        api_key=SINGLE_CHUNK_API_KEY,
        is_full_context=False,
    )

    parsed_diff = parse_diff(diff)
    comments = analyze_single_chunks(single_chunk_model, parsed_diff)
    full_context_response = analyze_full_context(full_context_model, parsed_diff)
    post_review(full_context_response, comments)


if __name__ == "__main__":
    main()
