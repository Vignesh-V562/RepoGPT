import os
import sys
from dotenv import load_dotenv

# Add current dir and src to path
sys.path.append(os.getcwd())

load_dotenv()

# Explicitly set the env var for aisuite if it's in .env but not in os.environ
if "GOOGLE_API_KEY" in os.environ:
    print(f"DEBUG: GOOGLE_API_KEY found in environment (length: {len(os.environ['GOOGLE_API_KEY'])})")
else:
    print("DEBUG: GOOGLE_API_KEY NOT found in environment")

from src.research_tools import github_search_tool
from src.planning_agent import planner_agent

def test_github_search():
    print("Testing GitHub Search Tool...")
    results = github_search_tool("fastapi", max_results=2)
    for r in results:
        print(f"- {r.get('name')}: {r.get('stars')} stars, {r.get('url')}")
    return len(results) > 0

def test_planner():
    print("\nTesting Planner Agent...")
    try:
        steps = planner_agent("A decentralized ride-sharing app")
        print("Steps generated:")
        for i, step in enumerate(steps):
            print(f"{i+1}. {step}")
        return len(steps) > 0
    except Exception as e:
        print(f"Planner failed: {e}")
        return False

if __name__ == "__main__":
    github_ok = test_github_search()
    planner_ok = test_planner()
    
    if github_ok and planner_ok:
        print("\n✅ Verification passed!")
    else:
        print("\n❌ Verification failed!")
        sys.exit(1)
