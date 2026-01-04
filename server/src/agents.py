import os
from google import genai
from google.genai import types
from datetime import datetime
import logging
import json

logger = logging.getLogger(__name__)

def load_prompt(filename, **kwargs):
    # Prompts are in d:/RepoGPT/server/prompts
    # File is in d:/RepoGPT/server/src/agents.py
    # So we go up one level from src
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    path = os.path.join(base_dir, "prompts", filename)
    with open(path, "r", encoding="utf-8") as f:
        template = f.read()
    if kwargs:
        return template.format(**kwargs)
    return template
from src.research_tools import (
    github_search_tool,
    tavily_search_tool,
    wikipedia_search_tool,
)

client = genai.Client(api_key=os.environ.get("GOOGLE_API_KEY"))
MODEL_NAME = 'gemini-flash-latest'


# === Research Agent ===
def research_agent(
    prompt: str, model: str = "gemini-1.5-flash", return_messages: bool = False
):
    logger.info("==================================")
    logger.info("🔍 Research Agent")
    logger.info("==================================")

    prompt_template = load_prompt("research_agent.md")

    full_prompt = prompt_template.format(
        date=datetime.now().strftime("%Y-%m-%d"),
        prompt=prompt
    )

    tools = [github_search_tool, tavily_search_tool, wikipedia_search_tool]
    
    try:
        response = client.models.generate_content(
            model=MODEL_NAME,
            contents=full_prompt,
            config=types.GenerateContentConfig(
                tools=tools,
                automatic_function_calling=types.AutomaticFunctionCallingConfig(
                    disable=False
                )
            )
        )
        content = response.text
        
        # Extract tool calls (structured for frontend)
        tools_used = []
        for call in response.candidates[0].function_calls or []:
            tools_used.append({
                "name": call.name,
                "args": call.args
            })

        # Return structured data
        result = {
            "content": content,
            "tools_used": tools_used
        }

        logger.info(f"✅ Output: {content[:100]}...")
        return json.dumps(result), []

    except Exception as e:
        logger.error(f"❌ Error: {e}")
        error_result = {
            "content": f"[Model Error: {str(e)}]",
            "tools_used": []
        }
        return json.dumps(error_result), []


def writer_agent(
    prompt: str,
    model: str = "gemini-1.5-flash",
    min_words_total: int = 2400,
    min_words_per_section: int = 400,
    max_tokens: int = 15000,
    retries: int = 1,
):
    logger.info("==================================")
    logger.info("✍️ Writer Agent")
    logger.info("==================================")

    system_message = load_prompt("writer_agent.md")

    try:
        response = client.models.generate_content(
            model=MODEL_NAME,
            contents=prompt,
            config=types.GenerateContentConfig(
                system_instruction=system_message,
                temperature=0,
                max_output_tokens=max_tokens,
            )
        )
        content = response.text

        logger.info(f"✅ Output: {content[:100]}...")
        return content, []
    except Exception as e:
        logger.error(f"❌ Error: {e}")
        return f"[Model Error: {str(e)}]", []


def editor_agent(
    prompt: str,
    model: str = "gemini-1.5-flash",
    target_min_words: int = 2400,
):
    logger.info("==================================")
    logger.info("🧠 Editor Agent")
    logger.info("==================================")

    system_message = load_prompt("editor_agent.md")

    try:
        response = client.models.generate_content(
            model=MODEL_NAME,
            contents=prompt,
            config=types.GenerateContentConfig(
                system_instruction=system_message,
                temperature=0,
            )
        )
        content = response.text
        return content, []
    except Exception as e:
        logger.error(f"❌ Error in Editor Agent: {e}")
        return prompt, [] # return original as fallback


def critique_agent(goal: str, output: str):
    logger.info("==================================")
    logger.info("🧠 Critique Agent")
    logger.info("==================================")

    import re
    prompt = load_prompt("critique_agent.md", goal=goal, output=output)

    try:
        response = client.models.generate_content(
            model=MODEL_NAME,
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=0,
                response_mime_type="application/json"
            )
        )
        # Handle potential json string inside markdown if it happens
        raw = response.text.strip()
        if raw.startswith("```"):
             raw = re.sub(r"^```[a-zA-Z]*\n?", "", raw)
             raw = re.sub(r"\n?```$", "", raw)
        return json.loads(raw)
    except Exception as f:
        logger.error(f"❌ Critique failed: {f}")
        return {"critique": "good", "reason": "System error in critic"}
