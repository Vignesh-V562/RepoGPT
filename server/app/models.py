from pydantic import BaseModel
from typing import List, Optional, Any
from datetime import datetime
import uuid

class IngestRequest(BaseModel):
    repoUrl: str
    userId: str # from client

class RepoChatRequest(BaseModel):
    repoId: Optional[str] = None
    query: str
    sessionId: Optional[str] = None
    userId: str 

class Message(BaseModel):
    role: str
    content: str
    sources: Optional[List[Any]] = None

class ChatSession(BaseModel):
    id: str
    title: str
    created_at: datetime
    
class ResearchRequest(BaseModel):
    query: str

class ResearchResponse(BaseModel):
    plan: str
    research_data: str

class AnalystRequest(BaseModel):
    userId: str
    query: str
    sessionId: Optional[str] = None
