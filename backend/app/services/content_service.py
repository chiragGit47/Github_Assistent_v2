from typing import Any

from langchain_core.messages import (
    HumanMessage,
    SystemMessage,
)
from langchain_ollama import ChatOllama

from app.core.config import settings


MAX_README_CHARS = 10_000


def create_cloud_llm(
    temperature: float = 0.3,
) -> ChatOllama:
    """
    Create a ChatOllama client configured for Ollama Cloud.
    """

    return ChatOllama(
        model=settings.ollama_model,
        base_url=settings.ollama_base_url,
        temperature=temperature,
        client_kwargs={
            "headers": {
                "Authorization": f"Bearer {settings.ollama_api_key}",
            }
        },
    )


def clean_readme_content(
    readme_content: str | None,
) -> str:
    """
    Clean and limit README content before sending it to the LLM.
    """

    if not readme_content:
        return ""

    cleaned = readme_content.strip()

    return cleaned[:MAX_README_CHARS]


class ContentService:
    def __init__(self) -> None:
        self.llm = create_cloud_llm(
            temperature=0.3
        )

    async def generate_linkedin_post(
        self,
        repo_name: str,
        readme_content: str,
        repo_url: str | None = None,
    ) -> str:
        """
        Generate a professional LinkedIn post using repository README content.
        """

        cleaned_readme = clean_readme_content(
            readme_content
        )

        if not cleaned_readme:
            raise ValueError(
                "README content is required to generate "
                "a LinkedIn post."
            )

        system_prompt = """
You are a professional technical-content writer.

Create a LinkedIn post about a software project using only the
repository information supplied by the user.

Rules:
- Do not invent technologies, features, results, metrics, or claims.
- Clearly explain what was built and why it was built.
- Mention important technical decisions found in the README.
- Keep the tone professional, genuine, and suitable for recruiters.
- Use short paragraphs.
- Use a limited number of relevant emojis.
- End with relevant hashtags.
- Do not use markdown headings.
- Do not mention that an AI generated the post.
"""

        repository_details = (
            f"Repository name: {repo_name}\n"
        )

        if repo_url:
            repository_details += (
                f"Repository URL: {repo_url}\n"
            )

        user_prompt = f"""
{repository_details}

README content:
----------------
{cleaned_readme}
----------------

Generate the final LinkedIn post.
"""

        response = await self.llm.ainvoke(
            [
                SystemMessage(content=system_prompt),
                HumanMessage(content=user_prompt),
            ]
        )

        content = response.content

        if isinstance(content, list):
            content = "\n".join(
                str(item)
                for item in content
            )

        if not content:
            raise RuntimeError(
                "The model returned an empty LinkedIn post."
            )

        return str(content).strip()

    async def generate_resume_points(
        self,
        repo_name: str,
        readme_content: str,
        repo_url: str | None = None,
    ) -> list[str]:
        """
        Generate concise, ATS-friendly resume bullet points.
        """

        cleaned_readme = clean_readme_content(
            readme_content
        )

        if not cleaned_readme:
            raise ValueError(
                "README content is required to generate "
                "resume points."
            )

        system_prompt = """
You are an expert technical resume writer.

Generate exactly four concise resume bullet points from the supplied
repository README.

Rules:
- Use only information present in the README.
- Do not invent metrics, users, performance gains, or technologies.
- Begin each point with a strong action verb.
- Explain technical implementation and practical value.
- Keep each point suitable for an AI Engineer or Software Engineer resume.
- Return one bullet point per line.
- Do not add headings, introductions, explanations, or closing text.
- Do not number the points.
"""

        repository_details = (
            f"Repository name: {repo_name}\n"
        )

        if repo_url:
            repository_details += (
                f"Repository URL: {repo_url}\n"
            )

        user_prompt = f"""
{repository_details}

README content:
----------------
{cleaned_readme}
----------------

Generate exactly four resume bullet points.
"""

        response = await self.llm.ainvoke(
            [
                SystemMessage(content=system_prompt),
                HumanMessage(content=user_prompt),
            ]
        )

        content: Any = response.content

        if isinstance(content, list):
            raw_text = "\n".join(
                str(item)
                for item in content
            )
        else:
            raw_text = str(content or "")

        if not raw_text.strip():
            raise RuntimeError(
                "The model returned empty resume points."
            )

        points: list[str] = []

        for line in raw_text.splitlines():
            cleaned_line = line.strip()

            cleaned_line = cleaned_line.lstrip(
                "•-*0123456789. "
            ).strip()

            if cleaned_line:
                points.append(cleaned_line)

        if not points:
            raise RuntimeError(
                "No valid resume points were generated."
            )

        return points[:4]


content_service = ContentService()