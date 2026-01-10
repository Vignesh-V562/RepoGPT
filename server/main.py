import os
from dotenv import load_dotenv

# Load environment variables BEFORE importing any other local modules
load_dotenv()

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from app.models import IngestRequest, RepoChatRequest, ChatSession, Message, AnalystRequest
from app.supabase_client import supabase
from app.ingestion import repo_ingestion_service
from app.rag import query_repo
from src.planning_agent import planner_agent, executor_agent_step
import uuid
import json
import sys
import logging
import asyncio
from concurrent.futures import ThreadPoolExecutor

# Configure logging FIRST
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    stream=sys.stdout
)

logger = logging.getLogger(__name__)
global_pool = ThreadPoolExecutor(max_workers=10)

# Ensure src is in python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def is_greeting(query: str) -> bool:
    greetings = ["hi", "hello", "hey", "hola", "greetings", "hi there", "hello there"]
    return query.lower().strip().strip('?!.') in greetings

app = FastAPI(title="RepoGPT API", version="2.0.0")

# Production CORS: Allow environment-defined origins + default local
allowed_origins = os.getenv("ALLOWED_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000").split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def root():
    return {"message": "RepoGPT API is running"}

@app.post("/api/repo/ingest")
async def ingest_repo(request: IngestRequest, background_tasks: BackgroundTasks):
    # 1. Create Repository Record (if not exists)
    try:
        existing = supabase.table("repositories").select("*").eq("url", request.repoUrl).eq("user_id", request.userId).execute()
        if existing.data:
            repo_id = existing.data[0]['id']
            if existing.data[0]['status'] == 'ready':
                return {"message": "Repo already indexed", "repoId": repo_id}
        else:
            # Create new
            res = supabase.table("repositories").insert({
                "url": request.repoUrl,
                "user_id": request.userId,
                "name": request.repoUrl.split("/")[-1],
                "status": "pending"
            }).execute()
            repo_id = res.data[0]['id']

        # 2. Trigger Background Task
        background_tasks.add_task(repo_ingestion_service.ingest_repo, request.repoUrl, request.userId, repo_id)
        
        return {"message": "Ingestion started", "repoId": repo_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/chat/stream")
async def chat_stream(request: RepoChatRequest):
    # 1. Verify Session or Create One
    session_id = request.sessionId
    if not session_id:
        # Create new session
        res = supabase.table("chat_sessions").insert({
            "user_id": request.userId,
            "title": request.query[:30],
            "repository_id": request.repoId
        }).execute()
        session_id = res.data[0]['id']

    # 2. Save User Message
    supabase.table("messages").insert({
        "session_id": session_id,
        "role": "user",
        "content": request.query
    }).execute()

    # 3. Stream Response (SSE Format)
    async def event_generator():
        import json
        full_response = ""
        
        # Send Session ID
        yield f"data: {json.dumps({'type': 'session', 'sessionId': session_id})}\n\n"
        
        # Check for greeting
        if is_greeting(request.query):
            response = "Hello! I am RepoGPT, your AI codebase analyst. How can I help you today?"
            yield f"data: {json.dumps({'type': 'token', 'content': response})}\n\n"
            # Save AI Message
            supabase.table("messages").insert({
                "session_id": session_id,
                "role": "ai",
                "content": response
            }).execute()
            yield "data: [DONE]\n\n"
            return

        async for event in query_repo(request.repoId, request.query, request.sessionId):
            if isinstance(event, dict):
                if event["type"] == "token":
                    full_response += event["content"]
                yield f"data: {json.dumps(event)}\n\n"
            else:
                # Fallback for unexpected string yields
                full_response += str(event)
                yield f"data: {json.dumps({'type': 'token', 'content': str(event)})}\n\n"

        # 4. Save AI Message
        supabase.table("messages").insert({
            "session_id": session_id,
            "role": "ai",
            "content": full_response
        }).execute()
        
        # End stream
        yield "data: [DONE]\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")

@app.post("/api/chat/analyze")
async def chat_analyze(request: AnalystRequest):
    # 1. Verify Session or Create One
    session_id = request.sessionId
    if not session_id:
        res = supabase.table("chat_sessions").insert({
            "user_id": request.userId,
            "title": f"Research: {request.query[:30]}",
            "repository_id": None # No specific repo for initial research
        }).execute()
        session_id = res.data[0]['id']

    # 2. Save User Message
    try:
        supabase.table("messages").insert({
            "session_id": session_id,
            "role": "user",
            "content": request.query
        }).execute()
    except Exception as e:
        logger.error(f"Failed to save user message: {e}")

    # 3. Stream Response (SSE Format)
    async def event_generator():
        import json
        full_response = ""
        execution_history = []
        logger.info(f"ARCHITECT: Starting response stream for session {session_id}")
        # Send Session ID
        yield f"data: {json.dumps({'type': 'session', 'sessionId': session_id})}\n\n"
        
        # Check for greeting
        if is_greeting(request.query):
            response = "Hello! I am RepoGPT Architect. I can help you research architecture patterns and plan your next big project. What are we building?"
            yield f"data: {json.dumps({'type': 'token', 'content': response})}\n\n"
            # Save AI Message
            supabase.table("messages").insert({
                "session_id": session_id,
                "role": "ai",
                "content": response
            }).execute()
            yield "data: [DONE]\n\n"
            return

        logger.info(f"ARCHITECT: Processing non-greeting query: {request.query[:50]}...")
        yield f"data: {json.dumps({'type': 'status', 'content': 'Planning research strategy...'})}\n\n"
        
        try:
            # Plan the workflow - Run in thread pool as it's a blocking LLM call
            logger.info("ARCHITECT: Calling planner_agent...")
            loop = asyncio.get_event_loop()
            initial_plan_steps = await loop.run_in_executor(
                global_pool, planner_agent, request.query
            )
            
            yield f"data: {json.dumps({'type': 'status', 'content': f'Architect: Plan generated with {len(initial_plan_steps)} steps. Executing research...' })}\n\n"
            logger.info(f"ARCHITECT: Plan generated with {len(initial_plan_steps) if initial_plan_steps else 0} steps")
            if not initial_plan_steps:
                raise ValueError("Planner failed to generate steps.")
                
            yield f"data: {json.dumps({'type': 'plan', 'steps': initial_plan_steps})}\n\n"
            
            # Execute steps
            for i, plan_step_title in enumerate(initial_plan_steps):
                # Provide a more descriptive status update based on the step title
                status_msg = f"Architect: {plan_step_title}"
                if "research" in plan_step_title.lower():
                    status_msg = f"🔍 Researching: {plan_step_title.split(':')[-1].strip() if ':' in plan_step_title else plan_step_title}"
                elif "write" in plan_step_title.lower() or "draft" in plan_step_title.lower():
                    status_msg = f"✍️ Writing: {plan_step_title.split(':')[-1].strip() if ':' in plan_step_title else plan_step_title}"
                
                yield f"data: {json.dumps({'type': 'status', 'content': status_msg})}\n\n"
                
                try:
                    # Hard timeout of 240 seconds per research step to prevent hanging the whole request
                    actual_step_description, agent_name, output = await asyncio.wait_for(
                        loop.run_in_executor(
                            global_pool, executor_agent_step, plan_step_title, execution_history, request.query
                        ),
                        timeout=240.0
                    )
                except asyncio.TimeoutError:
                    logger.error(f"ARCHITECT: Step '{plan_step_title}' timed out after 240s")
                    agent_name = "system"
                    output = f"Error: Research step '{plan_step_title}' timed out and was skipped to prevent hanging."
                    actual_step_description = plan_step_title
                
                execution_history.append([plan_step_title, actual_step_description, output])
                
                # Send intermediate update
                yield f"data: {json.dumps({
                    'type': 'step_complete', 
                    'index': i, 
                    'agent': agent_name, 
                    'output': output
                })}\n\n"
                logger.info(f"Step {i} completed by {agent_name}")

            # Final result is the last output
            full_response = execution_history[-1][-1] if execution_history else "No report generated."
            
            # Send the final response to the frontend
            yield f"data: {json.dumps({'type': 'token', 'content': full_response})}\n\n"
            
            # 4. Save AI Message
            try:
                supabase.table("messages").insert({
                    "session_id": session_id,
                    "role": "ai",
                    "content": full_response
                }).execute()
            except Exception as e:
                logger.error(f"Failed to save final AI report (likely session was deleted): {e}")
            
        except Exception as e:
            import traceback
            error_msg = f"ARCHITECT_ERROR: {str(e)}\n{traceback.format_exc()}"
            logger.error(error_msg)
            yield f"data: {json.dumps({'type': 'error', 'content': str(e)})}\n\n"
        
        # End stream
        yield "data: [DONE]\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@app.get("/api/chat/history")
def get_history(userId: str):
    res = supabase.table("chat_sessions").select("*").eq("user_id", userId).order("created_at", desc=True).execute()
    return res.data

@app.get("/api/chat/{session_id}")
def get_chat_messages(session_id: str):
    res = supabase.table("messages").select("*").eq("session_id", session_id).order("created_at", desc=False).execute()
    return res.data

@app.delete("/api/chat/{session_id}")
def delete_chat_session(session_id: str):
    logger.info(f"Attempting to delete session: {session_id}")
    try:
        # Manually delete messages first as a safety measure in case cascade delete isn't enabled
        supabase.table("messages").delete().eq("session_id", session_id).execute()
        
        # Now delete the session
        res = supabase.table("chat_sessions").delete().eq("id", session_id).execute()
        
        # Check if deletion was successful
        if hasattr(res, 'error') and res.error:
             raise Exception(f"Supabase error: {res.error}")
             
        return {"message": "Chat session deleted successfully"}
    except Exception as e:
        logger.error(f"Delete failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to delete session: {str(e)}")

