from enum import Enum
from typing import Any

import google.generativeai as genai
from anthropic import Anthropic
from openai import OpenAI


class ModelProvider(Enum):
    """The model provider."""

    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    GOOGLE = "google"
    DEEPSEEK = "deepseek"

    @classmethod
    def from_model(cls, model: str) -> "ModelProvider":
        """Get the model provider from the model name.

        Args:
            model (str): The model name.

        Returns:
            ModelProvider: The model provider.
        """
        for prefix, provider in PREFIX_TO_MODEL.items():
            if model.startswith(prefix):
                return provider
        raise ValueError(f"Unknown model: {model}")


PREFIX_TO_MODEL = {
    "gpt": ModelProvider.OPENAI,
    "o1": ModelProvider.OPENAI,
    "claude": ModelProvider.ANTHROPIC,
    "gemini": ModelProvider.GOOGLE,
    "deepseek": ModelProvider.DEEPSEEK,
}


class Model:
    """The model class.

    Attributes:
        model (str): The model name.
        api_key (str): The API key.
        system_prompt (str): The system prompt.
        max_tokens (int): The maximum tokens.
    """

    def __init__(  # noqa: D107
        self,
        model: str,
        api_key: str,
        is_full_context: bool,
        max_tokens: int = 4196,
    ):
        self.model = model
        self.system_prompt = (
            FULL_CONTEXT_SYSTEM_PROMPT
            if is_full_context
            else SINGLE_CHUNK_SYSTEM_PROMPT
        )
        self.max_tokens = max_tokens
        self.provider = ModelProvider.from_model(model)
        self.session = self.create_session(api_key)

    def create_session(self, api_key: str) -> Any:
        """Create a session for the model.

        Args:
            api_key (str): The API key.

        Returns:
            Any: The session.
        """
        match self.provider:
            case ModelProvider.OPENAI:
                return OpenAI(api_key=api_key)
            case ModelProvider.ANTHROPIC:
                return Anthropic(api_key=api_key)
            case ModelProvider.GOOGLE:
                genai.configure(api_key=api_key)
                return genai.GenerativeModel(model=self.model, api_key=api_key)
            case ModelProvider.DEEPSEEK:
                return OpenAI(api_key=api_key, base_url="https://api.deepseek.com")

    def request(self, prompt: str) -> str:
        """Request the model to generate a response.

        Args:
            prompt (str): The prompt to generate a response for.

        Returns:
            str: The generated response.
        """
        match self.provider:
            case ModelProvider.OPENAI | ModelProvider.DEEPSEEK:
                response = self.session.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": self.system_prompt},
                        {"role": "user", "content": prompt},
                    ],
                    temperature=0.2,
                    max_tokens=self.max_tokens,
                    top_p=1,
                    frequency_penalty=0,
                    presence_penalty=0,
                )
                return response.choices[0].message.content.strip()
            case ModelProvider.ANTHROPIC:
                response = self.session.messages.create(
                    model=self.model,
                    messages=[{"role": "user", "content": prompt}],
                    system=[
                        {
                            "type": "text",
                            "text": self.system_prompt,
                            "cache_control": {"type": "ephemeral"},
                        }
                    ],
                    temperature=0.2,
                    max_tokens=self.max_tokens,
                )
                return response.content[0].text.strip()
            case ModelProvider.GOOGLE:
                response = self.session.generate_content(prompt)
                return response.text.strip()

    def get_response_single_chunk(
        self, file: str, title: str, description: str, chunk: str
    ) -> str:
        """Get the response for a single chunk.

        Args:
            file (str): The file name.
            title (str): The pull request title.
            description (str): The pull request description.
            chunk (str): The diff chunk.

        Returns:
            str: The response.
        """
        prompt = SINGLE_CHUNK_USER_PROMPT.format(file, title, description, chunk)
        return self.request(prompt)

    def get_response_full_context(
        self, title: str, description: str, file_contents: list[str]
    ) -> str:
        """Get the response for full context.

        Args:
            title (str): The pull request title.
            description (str): The pull request description.
            file_contents (list[str]): The file contents, diffs.

        Returns:
            str: The response.
        """
        try:
            prompt = FULL_CONTEXT_USER_PROMPT.format(
                title, description, "\n".join(file_contents)
            )
            return self.request(prompt)
        except Exception as e:
            print(f"Error during full context response: {e}")
            print(prompt)
            return None


SINGLE_CHUNK_SYSTEM_PROMPT = (
    "Your task is to review pull requests. Instructions:\n"
    "- Provide the response in the following JSON format:  "
    """[{{"lineNumber":  <line_number>, "reviewComment": "<review comment>"}}] \n"""
    "- lineNumber is about the line number of the code that in new file. \n"
    "- Do not give positive comments or compliments. \n"
    "- Provide comments and suggestions ONLY if there is something to improve"
    "otherwise return an empty array. \n"
    "- Write the comment in GitHub Markdown format. \n"
    "- Use the given description only for the overall context "
    "and only comment the code. \n"
    "- IMPORTANT: NEVER suggest adding comments to the code. \n"
)
SINGLE_CHUNK_USER_PROMPT = (
    "Review the following code diff in the file "
    "{} and take the pull request title and description into account "
    "when writing the response. \n"
    "Pull request title: {} \n"
    "Pull request description: \n"
    "--- \n"
    "{} \n"
    "--- \n"
    "Git diff to review: \n"
    "```diff \n"
    "{} \n"
    "```"
)

FULL_CONTEXT_SYSTEM_PROMPT = (
    "You are an experienced software engineer specializing in reviewing pull "
    "requests. Your task is to provide an overall code review summary for a PR. "
    "Focus on assessing the following aspects:\n"
    "1. **Code Structure & Architecture:** "
    "Evaluate whether the code is well-organized, modular, "
    "and adheres to clean code principles. Suggest improvements if needed.\n"
    "2. **Refactoring Opportunities:** "
    "Identify areas where the code can be optimized or simplified without changing "
    "its behavior.\n"
    "3. **Potential Future Problems:** "
    "Highlight possible scalability, maintainability, or dependency issues that might "
    "arise in the future based on the current implementation.\n"
    "Be constructive and clear in your feedback. Avoid commenting on trivial issues "
    "or syntax errors—focus on high-level feedback.\n"
    "Precise instructions:\n"
    "- Do not give positive comments or compliments.\n"
    "- Provide comments and suggestions ONLY if there is something to improve, "
    "otherwise return an empty string.\n"
    "- Write the comment in GitHub Markdown format.\n"
    "- Do not start with 'markdown' or '```markdown'.\n"
    "- IMPORTANT: Give example code block or pseudo code if you can.\n"
)

FULL_CONTEXT_USER_PROMPT = (
    "Review the following code and take the pull request title "
    "and description into account when writing the response. \n"
    "Pull request title: {} \n"
    "Pull request description: \n"
    "--- \n"
    "{} \n"
    "--- \n"
    "Code to review: \n"
    "{}"
)
