from langchain_ollama import ChatOllama
from langchain_core.messages import HumanMessage, SystemMessage
from app.core.config import settings


MAX_README_CHARS = 10000


class ContentService:
    def __init__(self):
        self.llm = ChatOllama(
            model=settings.ollama_model,
            base_url=settings.ollama_base_url,
            client_kwargs={
                "headers": {
                "Authorization": (
                f"Bearer {settings.ollama_api_key}"
                )
            }
        },
    )

    def _trim_readme(self, readme_content: str) -> str:
        content = readme_content.strip()

        if len(content) <= MAX_README_CHARS:
            return content

        return (
            content[:MAX_README_CHARS]
            + "\n\n[README shortened for faster processing]"
        )

    async def generate_linkedin_post(
        self,
        readme_content: str,
    ) -> str:
        clean_readme = self._trim_readme(readme_content)

        response = await self.llm.ainvoke([
            SystemMessage(
                content=(
                    "Write a concise, natural LinkedIn post "
                    "about the software project. "
                    "Do not invent features, metrics, or results. "
                    "Keep it under 350 words."
                )
            ),
            HumanMessage(
                content=(
                    "Create a LinkedIn post from this README:\n\n"
                    f"{clean_readme}"
                )
            ),
        ])

        return response.content.strip()

    async def generate_resume_points(
        self,
        readme_content: str,
    ) -> list[str]:
        clean_readme = self._trim_readme(readme_content)

        response = await self.llm.ainvoke([
            SystemMessage(
                content=(
                    "Generate exactly 3 concise resume bullet points. "
                    "Focus on implementation, technologies, and value. "
                    "Do not invent metrics. "
                    "Return only one bullet per line."
                )
            ),
            HumanMessage(
                content=(
                    "Generate resume points from this README:\n\n"
                    f"{clean_readme}"
                )
            ),
        ])

        points = [
            line.strip().lstrip("-•1234567890. ").strip()
            for line in response.content.splitlines()
            if line.strip()
        ]

        return points[:3]


content_service = ContentService()