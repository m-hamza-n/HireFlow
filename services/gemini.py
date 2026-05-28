# pyright: reportArgumentType=false, reportReturnType=false, reportOptionalMemberAccess=false, reportOptionalSubscript=false, reportCallIssue=false
import asyncio
import json
import logging
from typing import List, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from google import genai
from google.genai import types
from config import settings

logger = logging.getLogger(__name__)

client = genai.Client(api_key=settings.GEMINI_API_KEY)
MODEL_NAME = "gemini-2.0-flash"
EMBEDDING_MODEL = "gemini-embedding-001"

def get_embedding(text: str):
    try:
        result = client.models.embed_content(
            model=EMBEDDING_MODEL,
            contents=text
        )
        return result.embeddings[0].values
    except Exception as e:
        logger.exception(f"Embedding error: {e}")
        return None

def chat_completion(prompt: str) -> str:
    try:
        response = client.models.generate_content(
            model=MODEL_NAME,
            contents=prompt
        )
        return response.text
    except Exception as e:
        logger.exception(f"Chat error: {e}")
        return None

async def chat_with_tools(
    messages: List[Dict[str, str]],
    user_id: str,
    user_role: str,
    db: AsyncSession
) -> Dict[str, Any]:
    from services import agent_tools
    from models import Candidate
    from sqlalchemy import select

    system_prompt = f"""You are HireFlow's AI assistant. You help candidates find jobs and understand their application status, and help recruiters manage their hiring pipeline.
Current user role: {user_role}
Current user ID: {user_id}
Use the available tools to answer questions. Be concise and helpful.
If a candidate asks about recruiter-only info, politely decline."""

    tools = [
        types.Tool(function_declarations=[
            types.FunctionDeclaration(
                name="search_jobs",
                description="Search for active jobs by keyword, location, or job type.",
                parameters=types.Schema(
                    type="object",
                    properties={
                        "query": types.Schema(type="string"),
                        "location": types.Schema(type="string"),
                        "job_type": types.Schema(type="string"),
                    },
                    required=["query"]
                )
            ),
            types.FunctionDeclaration(
                name="get_job_details",
                description="Get full details of a specific job by its ID.",
                parameters=types.Schema(
                    type="object",
                    properties={"job_id": types.Schema(type="string")},
                    required=["job_id"]
                )
            ),
            types.FunctionDeclaration(
                name="get_application_status",
                description="Get the status of all applications for the current candidate.",
                parameters=types.Schema(
                    type="object",
                    properties={"candidate_id": types.Schema(type="string")},
                    required=["candidate_id"]
                )
            ),
            types.FunctionDeclaration(
                name="search_knowledge_base",
                description="Search hiring guidelines and interview tips.",
                parameters=types.Schema(
                    type="object",
                    properties={"query": types.Schema(type="string")},
                    required=["query"]
                )
            ),
            types.FunctionDeclaration(
                name="get_top_candidates",
                description="Get top matched candidates for a job (recruiter only).",
                parameters=types.Schema(
                    type="object",
                    properties={
                        "job_id": types.Schema(type="string"),
                        "limit": types.Schema(type="integer"),
                    },
                    required=["job_id"]
                )
            ),
        ])
    ]

    config = types.GenerateContentConfig(
        system_instruction=system_prompt,
        tools=tools
    )

    last_user_msg = messages[-1]["content"] if messages else ""
    tool_calls_made = []

    try:
        response = await asyncio.to_thread(
            client.models.generate_content,
            model=MODEL_NAME,
            contents=last_user_msg,
            config=config
        )
    except Exception as e:
        logger.exception("Gemini chat error")
        error_msg = str(e)
        if "429" in error_msg or "quota" in error_msg.lower():
            reply = "I'm currently rate-limited. Please try again in a minute or upgrade your API plan."
        else:
            reply = "Sorry, I encountered an error. Please try again later."
        return {"reply": reply, "tool_calls_made": []}

    # Handle tool calls (wrapped in try/except as well)
    try:
        while response.candidates and response.candidates[0].content.parts:
            part = response.candidates[0].content.parts[0]
            if hasattr(part, "function_call") and part.function_call:
                fn_call = part.function_call
                tool_calls_made.append(fn_call.name)
                result = await _execute_tool(fn_call.name, dict(fn_call.args), user_id, user_role, db)
                response = await asyncio.to_thread(
                    client.models.generate_content,
                    model=MODEL_NAME,
                    contents=[
                        types.Content(parts=[types.Part(function_response=types.FunctionResponse(
                            name=fn_call.name, response={"result": result}
                        ))])
                    ],
                    config=config
                )
            else:
                break
    except Exception as e:
        logger.exception("Tool call error")
        return {"reply": "Sorry, I had trouble processing that request.", "tool_calls_made": tool_calls_made}

    reply = response.text if response.text else "I couldn't process that request."
    return {"reply": reply, "tool_calls_made": tool_calls_made}

async def _execute_tool(tool_name: str, args: Dict, user_id: str, user_role: str, db: AsyncSession) -> str:
    from services import agent_tools
    from models import Candidate
    from sqlalchemy import select
    try:
        if tool_name == "search_jobs":
            jobs = await agent_tools.search_jobs(db, args.get("query"), args.get("location"), args.get("job_type"))
            return json.dumps(jobs, default=str)
        elif tool_name == "get_job_details":
            job = await agent_tools.get_job_details(db, args["job_id"])
            return json.dumps(job, default=str) if job else "Job not found"
        elif tool_name == "get_application_status":
            if user_role != "candidate":
                return "This tool is only for candidates."
            result = await db.execute(select(Candidate).where(Candidate.user_id == user_id))
            candidate = result.scalar_one_or_none()
            if not candidate:
                return "No candidate profile found."
            apps = await agent_tools.get_application_status(db, str(candidate.id))
            return json.dumps(apps, default=str)
        elif tool_name == "search_knowledge_base":
            return await agent_tools.search_knowledge_base(args["query"])
        elif tool_name == "get_top_candidates":
            if user_role != "recruiter":
                return "This tool is only available to recruiters."
            candidates = await agent_tools.get_top_candidates(db, args["job_id"], args.get("limit", 5))
            return json.dumps(candidates, default=str)
        else:
            return f"Unknown tool: {tool_name}"
    except Exception as e:
        logger.exception(f"Tool execution error: {e}")
        return f"Error: {str(e)}"
