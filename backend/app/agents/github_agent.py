import json
from typing import Any

from langchain_core.messages import (
    AIMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)
from langchain_ollama import ChatOllama

from app.core.config import settings
from app.state.manager import manager
from app.tools.github_tools import (
    create_repository,
    fetch_repositories,
    generate_linkedin_post,
    generate_resume_points,
    upload_project_zip,
    upload_single_file,
)


SYSTEM_PROMPT = """
You are a GitHub assistant.

You help the authenticated user perform supported GitHub operations.

Available actions:
1. List the user's GitHub repositories.
2. Create a GitHub repository.
3. Upload a single file.
4. Upload a ZIP project.
5. Generate a LinkedIn post from a repository README.
6. Generate resume bullet points from a repository README.

Rules:
- Use the provided tools whenever a request requires GitHub data or an action.
- Never invent repository names, files, README content, or GitHub results.
- Do not claim that an action succeeded unless the tool confirms success.
- Ask for missing required information.
- Never expose access tokens, API keys, secrets, or internal session data.
- Do not execute arbitrary scripts or shell commands.
- Keep responses clear and concise.
"""


def create_cloud_llm(temperature: float = 0.2) -> ChatOllama:
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


def normalise_tool_result(result: Any) -> dict[str, Any]:
    """
    Convert a tool result into a predictable dictionary.
    """

    if isinstance(result, dict):
        return result

    if isinstance(result, str):
        return {
            "success": True,
            "message": result,
            "data": None,
        }

    return {
        "success": True,
        "message": "Tool completed successfully.",
        "data": result,
    }


def tool_result_as_text(result: dict[str, Any]) -> str:
    """
    Safely serialise a tool result for the LLM.
    """

    try:
        return json.dumps(result, default=str)
    except (TypeError, ValueError):
        return str(result)


class GitHubAgent:
    def __init__(self) -> None:
        self.tools = [
            fetch_repositories,
            create_repository,
            upload_single_file,
            upload_project_zip,
            generate_linkedin_post,
            generate_resume_points,
        ]

        self.tools_by_name = {
            tool.name: tool
            for tool in self.tools
        }

        # This model decides whether a tool must be called.
        self.tool_llm = create_cloud_llm(
            temperature=0.1
        ).bind_tools(self.tools)

        # This model writes the final natural-language answer.
        self.final_llm = create_cloud_llm(
            temperature=0.2
        )

    async def chat(
        self,
        session_id: str,
        message: str,
    ) -> dict[str, Any]:
        """
        Process one chat message for an authenticated session.
        """

        try:
            state = manager.get(session_id)

            if state is None:
                return {
                    "success": False,
                    "message": (
                        "Your session is missing or expired. "
                        "Please log in with GitHub again."
                    ),
                    "action": "session_expired",
                    "data": None,
                    "error": "Session not found",
                }

            if not state.github_access_token:
                return {
                    "success": False,
                    "message": "Please log in with GitHub first.",
                    "action": "authentication_required",
                    "data": None,
                    "error": "GitHub access token is missing",
                }

            if not message or not message.strip():
                return {
                    "success": False,
                    "message": "Please enter a message.",
                    "action": "validation_error",
                    "data": None,
                    "error": "Message cannot be empty",
                }

            if not state.messages:
                state.messages.append(
                    SystemMessage(content=SYSTEM_PROMPT)
                )

            state.messages.append(
                HumanMessage(content=message.strip())
            )

            first_response = await self.tool_llm.ainvoke(
                state.messages
            )

            tool_calls = getattr(
                first_response,
                "tool_calls",
                None,
            ) or []

            # The model answered without needing a tool.
            if not tool_calls:
                state.messages.append(first_response)
                manager.save(state)

                return {
                    "success": True,
                    "message": (
                        first_response.content
                        or "Request completed."
                    ),
                    "action": "chat_response",
                    "data": None,
                    "error": None,
                }

            state.messages.append(first_response)

            executed_signatures: set[str] = set()
            completed_results: list[dict[str, Any]] = []

            for tool_call in tool_calls:
                tool_name = tool_call.get("name")
                tool_call_id = tool_call.get("id")
                tool_args = dict(
                    tool_call.get("args") or {}
                )

                if not tool_name or tool_name not in self.tools_by_name:
                    invalid_result = {
                        "success": False,
                        "message": (
                            f"The requested tool "
                            f"'{tool_name}' is unavailable."
                        ),
                        "data": None,
                        "error": "Unknown tool",
                    }

                    state.messages.append(
                        ToolMessage(
                            content=tool_result_as_text(
                                invalid_result
                            ),
                            tool_call_id=tool_call_id or tool_name or "unknown",
                        )
                    )

                    completed_results.append(
                        {
                            "tool_name": tool_name,
                            "result": invalid_result,
                        }
                    )
                    continue

                # Every GitHub tool needs the authenticated session.
                tool_args["session_id"] = session_id

                signature = json.dumps(
                    {
                        "name": tool_name,
                        "args": tool_args,
                    },
                    sort_keys=True,
                    default=str,
                )

                if signature in executed_signatures:
                    duplicate_result = {
                        "success": False,
                        "message": (
                            "Duplicate tool execution was prevented."
                        ),
                        "data": None,
                        "error": "Duplicate tool call",
                    }

                    state.messages.append(
                        ToolMessage(
                            content=tool_result_as_text(
                                duplicate_result
                            ),
                            tool_call_id=tool_call_id or tool_name,
                        )
                    )
                    continue

                executed_signatures.add(signature)

                try:
                    raw_result = await self.tools_by_name[
                        tool_name
                    ].ainvoke(tool_args)

                    result = normalise_tool_result(
                        raw_result
                    )

                except Exception as exc:
                    result = {
                        "success": False,
                        "message": (
                            f"The {tool_name} operation failed."
                        ),
                        "data": None,
                        "error": str(exc),
                    }

                completed_results.append(
                    {
                        "tool_name": tool_name,
                        "result": result,
                    }
                )

                state.messages.append(
                    ToolMessage(
                        content=tool_result_as_text(result),
                        tool_call_id=tool_call_id or tool_name,
                    )
                )

                if not result.get("success", True):
                    manager.save(state)

                    return {
                        "success": False,
                        "message": result.get(
                            "message",
                            "The GitHub operation failed.",
                        ),
                        "action": f"{tool_name}_error",
                        "data": result.get("data"),
                        "error": result.get("error"),
                    }

            # Content-generation tools already return final content.
            for completed in completed_results:
                tool_name = completed["tool_name"]
                result = completed["result"]

                if tool_name == "generate_linkedin_post":
                    content = (
                        result.get("linkedin_post")
                        or result.get("data")
                        or result.get("message")
                    )

                    state.messages.append(
                        AIMessage(content=str(content))
                    )
                    manager.save(state)

                    return {
                        "success": True,
                        "message": str(content),
                        "action": "linkedin_post_generated",
                        "data": result.get("data"),
                        "error": None,
                    }

                if tool_name == "generate_resume_points":
                    points = (
                        result.get("resume_points")
                        or result.get("data")
                    )

                    if isinstance(points, list):
                        content = "\n".join(
                            f"• {point}"
                            for point in points
                        )
                    else:
                        content = str(
                            points
                            or result.get("message")
                            or "Resume points generated."
                        )

                    state.messages.append(
                        AIMessage(content=content)
                    )
                    manager.save(state)

                    return {
                        "success": True,
                        "message": content,
                        "action": "resume_points_generated",
                        "data": result.get("data"),
                        "error": None,
                    }

            final_response = await self.final_llm.ainvoke(
                state.messages
            )

            state.messages.append(final_response)
            manager.save(state)

            return {
                "success": True,
                "message": (
                    final_response.content
                    or "The operation completed successfully."
                ),
                "action": "github_action_completed",
                "data": [
                    completed["result"]
                    for completed in completed_results
                ],
                "error": None,
            }

        except Exception as exc:
            return {
                "success": False,
                "message": (
                    "Something went wrong while processing "
                    "your request."
                ),
                "action": "chat_error",
                "data": None,
                "error": str(exc),
            }


github_agent = GitHubAgent()