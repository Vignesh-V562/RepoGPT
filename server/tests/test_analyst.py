import os
import sys

# Add server directory to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.planning_agent import planner_agent, executor_agent_step

def test_analyst_logic():
    print("Testing Analyst Mode logic...")
    
    topic = "University LMS architecture"
    
    try:
        print(f"\n1. Testing planner_agent with topic: {topic}")
        steps = planner_agent(topic)
        print(f"✅ Steps generated: {steps}")
        
        if not steps:
            print("❌ No steps generated!")
            return

        print(f"\n2. Testing executor_agent_step for first step: {steps[0]}")
        # We'll only test if it can start the step without crashing
        # Mocking history
        history = []
        # Note: This will actually call the Gemini API if GOOGLE_API_KEY is set
        # We just want to see if it reaches the step execution part
        
        step_title, agent_name, output = executor_agent_step(steps[0], history, topic)
        print(f"✅ Step executed by: {agent_name}")
        print(f"✅ Output snippet: {output[:100]}...")
        
    except Exception as e:
        print(f"❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    # Check if API Key is present
    if not os.environ.get("GOOGLE_API_KEY"):
        print("⚠️ Warning: GOOGLE_API_KEY not set in environment. This test may fail on LLM calls.")
    
    test_analyst_logic()
