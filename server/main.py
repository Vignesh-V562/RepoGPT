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
    clean_query = query.lower().strip().strip('?!.')
    # Only match if the query is EXACTLY a greeting, not if it contains technical keywords
    if clean_query in greetings:
        technical_keywords = ["plan", "build", "architecture", "setup", "how to", "create", "implement"]
        if any(keyword in clean_query for keyword in technical_keywords):
            return False
        return True
    return False

app = FastAPI(title="RepoGPT API", version="2.0.0")
# ... (lines 38-153)
@app.post("/api/chat/analyze")
async def chat_analyze(request: RepoChatRequest):
    print(f"--- DEBUG: RECEIVED ANALYZE REQUEST: {request.query[:50]} ---")
    logger.info(f"RECEIVED ANALYZE REQUEST: {request.query[:50]}...")

    async def event_generator():
        import json
        full_response = ""
        execution_history = []
        
        # Send Immediate Awake Signal
        yield f"data: {json.dumps({'type': 'status', 'content': 'Architect: Initializing session...'})}\n\n"
        
        session_id = request.sessionId
        try:
            if not session_id:
                res = supabase.table("chat_sessions").insert({
                    "user_id": request.userId,
                    "title": f"Research: {request.query[:30]}",
                    "repository_id": None
                }).execute()
                session_id = res.data[0]['id']
            
            yield f"data: {json.dumps({'type': 'session', 'sessionId': session_id})}\n\n"

            supabase.table("messages").insert({
                "session_id": session_id,
                "role": "user",
                "content": request.query
            }).execute()
        except Exception as e:
            logger.error(f"Error in chat_analyze initialization: {e}")
            yield f"data: {json.dumps({'type': 'error', 'content': f'Initialization Error: {str(e)}'})}\n\n"
            yield "data: [DONE]\n\n"
            return

        if is_greeting(request.query):
            response = "Hello! I am RepoGPT Architect. I can help you research architecture patterns and plan your next big project. What are we building?"
            yield f"data: {json.dumps({'type': 'token', 'content': response})}\n\n"
            supabase.table("messages").insert({
                "session_id": session_id,
                "role": "ai",
                "content": response
            }).execute()
            yield "data: [DONE]\n\n"
            return

        logger.info(f"ARCHITECT: Processing query: {request.query[:50]}...")
        yield f"data: {json.dumps({'type': 'status', 'content': 'Planning research strategy...'})}\n\n"
        
        try:
            loop = asyncio.get_event_loop()
            initial_plan_steps = await loop.run_in_executor(
                global_pool, planner_agent, request.query
            )
            
            logger.info(f"ARCHITECT: Plan generated with {len(initial_plan_steps) if initial_plan_steps else 0} steps")
            if not initial_plan_steps:
                raise ValueError("Planner failed to generate steps.")
                
            yield f"data: {json.dumps({'type': 'plan', 'steps': initial_plan_steps})}\n\n"
            yield f"data: {json.dumps({'type': 'status', 'content': f'Architect: Plan generated. Executing {len(initial_plan_steps)} research steps...' })}\n\n"
            # Execute steps
            for i, plan_step_title in enumerate(initial_plan_steps):
                status_msg = f"Architect: {plan_step_title}"
                if "research" in plan_step_title.lower():
                    status_msg = f"🔍 Researching: {plan_step_title.split(':')[-1].strip() if ':' in plan_step_title else plan_step_title}"
                elif "write" in plan_step_title.lower() or "draft" in plan_step_title.lower():
                    status_msg = f"✍️ Writing: {plan_step_title.split(':')[-1].strip() if ':' in plan_step_title else plan_step_title}"
                
                yield f"data: {json.dumps({'type': 'status', 'content': status_msg})}\n\n"
                
                try:
                    # HEARTBEAT IMPLEMENTATION
                    # Instead of a simple await, we'll run the task and yield 'ping' events every 15s
                    # We wrap it in a future to use with asyncio
                    future = loop.run_in_executor(
                        global_pool, executor_agent_step, plan_step_title, execution_history, request.query
                    )
                    
                    actual_step_description = plan_step_title
                    agent_name = "unknown"
                    output = "No output produced."

                    while not future.done():
                        try:
                            # Wait for 15 seconds for the task to complete
                            # Use asyncio.wait to avoid consuming the result or raising exceptions inside the loop
                            done, pending = await asyncio.wait([asyncio.wrap_future(future)], timeout=15.0)
                            if not done:
                                # If it times out, send a heartbeat and continue waiting
                                logger.info(f"ARCHITECT: Sending heartbeat for step '{plan_step_title}'")
                                yield f"data: {json.dumps({'type': 'heartbeat', 'content': 'Still working...'})}\n\n"
                        except Exception as wait_err:
                            logger.error(f"ARCHITECT: Error during wait loop: {wait_err}")
                            break
                    
                    # Task is done or loop broken, get the result
                    if future.done():
                        actual_step_description, agent_name, output = future.result()
                    else:
                        raise TimeoutError(f"Step '{plan_step_title}' did not complete in time.")

                except Exception as e:
                    logger.error(f"ARCHITECT: Step '{plan_step_title}' failed: {e}")
                    agent_name = "system"
                    output = f"Error: Research step '{plan_step_title}' failed: {str(e)}"
                    actual_step_description = plan_step_title
                
                execution_history.append([plan_step_title, actual_step_description, output])
                
                logger.info(f"ARCHITECT: Step {i} complete. Yielding step_complete.")
                yield f"data: {json.dumps({
                    'type': 'step_complete', 
                    'index': i, 
                    'agent': agent_name, 
                    'output': output
                })}\n\n"

            # Final result is the last output
            full_response = execution_history[-1][-1] if execution_history else "No report generated."
            
            # CRITICAL: Always yield the final report as tokens
            logger.info("ARCHITECT: Yielding final report tokens")
            # Split by smaller chunks if it's very large, but here we just send it
            yield f"data: {json.dumps({'type': 'token', 'content': full_response})}\n\n"
            
            try:
                supabase.table("messages").insert({
                    "session_id": session_id,
                    "role": "ai",
                    "content": full_response
                }).execute()
            except Exception as e:
                logger.error(f"Failed to save final AI report: {e}")
            
        except Exception as e:
            import traceback
            error_msg = f"ARCHITECT_ERROR: {str(e)}\n{traceback.format_exc()}"
            logger.error(error_msg)
            yield f"data: {json.dumps({'type': 'error', 'content': str(e)})}\n\n"
        finally:
            logger.info(f"ARCHITECT: Closing stream for session {session_id}")
            yield "data: [DONE]\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")

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

