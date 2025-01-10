# Code Review Action

**Code Review Action** is a Gitea/GitHub Action that automatically reviews pull requests using one or multiple AI Large Language Models (LLMs). It analyzes code diffs and provides both granular file-level feedback as well as an overall review summary.

## Table of Contents

- [Features](#features)
- [Usage](#usage)
- [Inputs](#inputs)
- [Example Workflow](#example-workflow)
- [License](#license)

---

## Features

- **Single Chunk Review**: The action analyzes each file’s diff and provides line-specific suggestions (if applicable).
- **Full Context Review**: Analyzes entire file contents plus diffs, giving an overall code review summary.
- **Configurable Models**: Supports multiple LLM providers (OpenAI, Anthropic, Google, etc.) via model prefixes (`gpt-`, `claude-`, `gemini-`, `deepseek-`).
- **Exclusion Filters**: Skip certain files (e.g. `.yaml`) based on matching patterns.

---

## Usage

1. **Add this Action** to your repository’s workflow (e.g., `.github/workflows/pr-review.yml` or `.gitea/workflows/pr-review.yml` in Gitea).
2. **Provide required inputs** (API keys, model names, etc.) as shown below.
3. **Submit a pull request** against the repository. The Action will automatically run on PR events (`opened` or `synchronize`) and post review comments.

> **Note**: This action is intended primarily for use with Gitea.

---

## Inputs

| Input Name              | Required | Default        | Description                                                                                             |
|-------------------------|----------|----------------|---------------------------------------------------------------------------------------------------------|
| `access-token`          | Yes      | -              | The Gitea or GitHub token with permissions to read and comment on PRs (e.g., `$GITHUB_TOKEN`).          |
| `full-context-model`    | Yes      | `gpt-4o`       | The model to use for the full context review. Supports prefixes: `gpt-`, `claude-`, `gemini-`, etc.      |
| `full-context-api-key`  | Yes      | -              | The API key to use with the specified full-context model.                                               |
| `single-chunk-model`    | Yes      | `gpt-4o`       | The model to use for single-chunk review (file-by-file).                                                |
| `single-chunk-api-key`  | Yes      | -              | The API key to use with the specified single-chunk model.                                               |
| `exclude-files`         | No       | `*.yml,*.yaml` | Comma-separated file pattern(s) to exclude from diffs (e.g., `*.md,*.yaml`).                             |

---

## Example Workflow

Below is an example workflow file you can place in your repository (e.g., `.github/workflows/pr-review.yml` on GitHub or `.gitea/workflows/pr-review.yml` on Gitea). Adjust the version/tag/branch reference as needed.

```yaml
name: PR Review

on:
  pull_request:
    types: [opened, synchronize]

permissions:
  contents: read
  pull-requests: write

jobs:
  review:
    runs-on: ubuntu-latest
    steps:
      - name: AI Code Review
        uses: YOUR-ORG/CODE-REVIEW-ACTION@v1
        with:
          access-token: ${{ secrets.ACCESS_TOKEN }}
          full-context-model: "gpt-4o"
          full-context-api-key: ${{ secrets.OPENAI_API_KEY }}
          single-chunk-model: "claude-3-5-sonnet-20240620"
          single-chunk-api-key: ${{ secrets.ANTHROPIC_API_KEY }}
          exclude-files: "*.md,*.yaml"
```

### Explanation

1. **`on.pull_request.types`**: The workflow triggers when a pull request is opened or synchronized (i.e., new commits pushed).
2. **`permissions`**: We grant `read` permission to contents and `write` to pull-requests so the Action can post review comments.
3. **`steps.uses`**: References your published action. Replace `YOUR-ORG/CODE-REVIEW-ACTION@v1` with the actual owner/repo name and a valid version tag (e.g., `@main` or `@v1`).
4. **`with`**: Provides the necessary inputs.
   - `access-token`: Must be a secret that can post to PRs (e.g., `$GITHUB_TOKEN` or a personal access token on Gitea).
   - `full-context-model` & `single-chunk-model`: Choose which models to use (OpenAI GPT, Anthropic Claude, Google PaLM, etc.).
   - `full-context-api-key` & `single-chunk-api-key`: Corresponding API keys for each model.
   - `exclude-files`: If you want to skip reviewing certain file types, specify patterns here (default is `*.yml,*.yaml`).

---

## License

This project is available under the [MIT License](LICENSE). Feel free to modify and adapt to your own needs.

---

If you have any questions, issues, or feedback, please [open an issue](../../issues) in this repository. Happy reviewing!