import json

from langchain_core.messages import (
    HumanMessage,
    SystemMessage,
    ToolMessage,
)
from langchain_ollama import ChatOllama

from app.core.exceptions import GitHubAPIError
from app.state.manager import manager
from app.tools.github_tools import (
    create_repository,
    fetch_repositories,
    generate_linkedin_post,
    generate_resume_points,
    upload_project_zip,
    upload_single_file,
)
from app.core.config import settings


SYSTEM_PROMPT = """
You are a GitHub assistant for authenticated users.

Supported actions:
1. Fetch GitHub repositories.
2. Create public or private repositories.
3. Upload one prepared file using an upload_id.
4. Upload a prepared ZIP project using an upload_id.
5. Generate a LinkedIn post from a repository README.
6. Generate three resume bullet points from a repository README.

Rules:
- Never ask for access tokens, passwords, PATs or OAuth secrets.
- Never invent repository information.
- Never invent an upload_id.
- Use only the tools required by the user's current request.
- Do not repeat the same tool call.
- Do not call LinkedIn and resume tools together unless the user asks for both.
- Do not claim success unless the tool reports success.
- Keep responses concise.
"""


class GitHubAgent:
    def __init__(self):
        tools = [
            fetch_repositories,
            create_repository,
            upload_single_file,
            upload_project_zip,
            generate_linkedin_post,
            generate_resume_points,
        ]

        self.tools = {
            tool.name: tool
            for tool in tools
        }

        # Used only to decide which tools to call.
        self.tool_llm = ChatOllama(
            model=settings.ollama_model,
            base_url=settings.ollama_base_url,
            client_kwargs={
                "headers": {
                    "Authorization": (
                        f"Bearer {settings.ollama_api_key}"
                    )
            }
        },
        ).bind_tools(tools)

        # Used for the final answer.
        # It cannot call tools again.
        self.final_llm = ChatOllama(
            model="qwen2.5",
            temperature=0.2,
        )

    async def chat(
        self,
        session_id: str,
        user_message: str,
    ) -> dict:
        session = manager.get(session_id)

        if session is None:
            return {
                "success": False,
                "message": "Session is invalid or expired.",
                "action": "authentication_required",
                "data": None,
                "error": "Invalid session.",
            }

        messages = session.messages

        if not messages:
            messages.append(
                SystemMessage(content=SYSTEM_PROMPT)
            )

        messages.append(
            HumanMessage(content=user_message)
        )

        try:
            response = await self.tool_llm.ainvoke(messages)

            # No tool required: return normal conversation.
            if not response.tool_calls:
                messages.append(response)

                session.messages = messages
                manager.save(session)

                return {
                    "success": True,
                    "message": response.content,
                    "action": "chat",
                    "data": None,
                    "error": None,
                }

            messages.append(response)

            executed_calls = set()
            tool_results = []
            last_tool_name = None

            for tool_call in response.tool_calls:
                tool_name = tool_call["name"]
                tool_args = dict(tool_call.get("args", {}))

                # Backend controls session identity.
                tool_args["session_id"] = session_id

                # Prevent duplicate tool calls.
                call_signature = json.dumps(
                    {
                        "name": tool_name,
                        "args": tool_args,
                    },
                    sort_keys=True,
                    default=str,
                )

                if call_signature in executed_calls:
                    continue

                executed_calls.add(call_signature)

                tool = self.tools.get(tool_name)

                if tool is None:
                    result = {
                        "success": False,
                        "error": f"Unknown tool: {tool_name}",
                    }
                else:
                    print("TOOL NAME:", tool_name)
                    print("TOOL ARGS:", tool_args)

                    try:
                        result = await tool.ainvoke(tool_args)

                    except GitHubAPIError as error:
                        result = {
                            "success": False,
                            "error": error.message,
                            "status_code": error.status_code,
                            "details": error.details,
                        }

                    except Exception as error:
                        result = {
                            "success": False,
                            "error": "Tool execution failed.",
                            "details": str(error),
                        }

                    print("TOOL RESULT:", result)

                tool_results.append({
                    "tool": tool_name,
                    "result": result,
                })

                last_tool_name = tool_name

                messages.append(
                    ToolMessage(
                        content=json.dumps(
                            result,
                            default=str,
                        ),
                        tool_call_id=tool_call["id"],
                    )
                )

                # Stop immediately after a failed tool.
                if result.get("success") is False:
                    session.messages = messages
                    manager.save(session)

                    return {
                        "success": False,
                        "message": result.get(
                            "error",
                            "The requested action failed.",
                        ),
                        "action": tool_name,
                        "data": result,
                        "error": (
                            result.get("details")
                            or result.get("error")
                        ),
                    }

            if not tool_results:
                return {
                    "success": False,
                    "message": "No valid tool was executed.",
                    "action": "tool_error",
                    "data": None,
                    "error": "Duplicate or invalid tool calls.",
                }

            # Content tools already return finished content.
            if (
                len(tool_results) == 1
                and last_tool_name == "generate_linkedin_post"
            ):
                result = tool_results[0]["result"]
                final_message = result["linkedin_post"]

            elif (
                len(tool_results) == 1
                and last_tool_name == "generate_resume_points"
            ):
                result = tool_results[0]["result"]

                final_message = "\n".join(
                    f"• {point}"
                    for point in result["resume_points"]
                )

            else:
                # Normal model summarises results but cannot call tools.
                final_response = await self.final_llm.ainvoke(
                    messages
                )

                final_message = (
                    final_response.content
                    or "Request completed successfully."
                )

                messages.append(final_response)

            session.messages = messages
            manager.save(session)

            final_data = (
                tool_results[0]["result"]
                if len(tool_results) == 1
                else tool_results
            )

            return {
                "success": True,
                "message": final_message,
                "action": last_tool_name or "chat",
                "data": final_data,
                "error": None,
            }

        except Exception as error:
            print("AGENT ERROR:", repr(error))

            return {
                "success": False,
                "message": (
                    "Something went wrong while processing "
                    "your request."
                ),
                "action": "chat_error",
                "data": None,
                "error": str(error),
            }


github_agent = GitHubAgent()