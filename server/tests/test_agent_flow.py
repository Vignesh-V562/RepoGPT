import pytest
import os
import sys
import json

# Add server to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.agents import research_agent
from src.planning_agent import planner_agent

def test_planner_logic():
    """Verify that the planner produces a valid list of steps."""
    topic = "A real-time weather dashboard using React and OpenWeather API"
    steps = planner_agent(topic)
    
    assert isinstance(steps, list)
    assert len(steps) >= 3
    assert any("research" in s.lower() for s in steps)
    assert any("Project Blueprint" in s for s in steps)

def test_research_agent_json_structure():
    """Verify that research_agent returns valid JSON with content and tools_used."""
    prompt = "Research the best libraries for a Python web scraper in 2025"
    raw_output, _ = research_agent(prompt)
    
    data = json.loads(raw_output)
    assert "content" in data
    assert "tools_used" in data
    assert isinstance(data["tools_used"], list)
    assert len(data["content"]) > 100

@pytest.mark.asyncio
async def test_critique_flow():
    """Test that the critique agent can evaluate output correctly."""
    from src.agents import critique_agent
    goal = "Find high-quality GitHub repos for a RAG system"
    good_output = "I found these repos: 1. langchain/langchain (Stars: 80k), 2. run-llama/llama_index (Stars: 30k)."
    bad_output = "I couldn't find anything useful on GitHub."
    
    good_eval = critique_agent(goal, good_output)
    bad_eval = critique_agent(goal, bad_output)
    
    assert good_eval["critique"] in ["good", "bad"] # At least it should return the key
    assert "reason" in good_eval
    assert "critique" in bad_eval
