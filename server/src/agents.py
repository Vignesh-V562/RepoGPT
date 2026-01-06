import os
import time
import random
import logging
import json
from datetime import datetime
from google import genai
from google.genai import types

logger = logging.getLogger(__name__)

def generate_with_retry(model, contents, config, retries=5, base_delay=10):
    """Helper to retry API calls on rate limit errors with exponential backoff."""
    for attempt in range(retries):
        try:
            return client.models.generate_content(
                model=model,
                contents=contents,
                config=config
            )
        except Exception as e:
            error_str = str(e).lower()
            if "429" in error_str or "503" in error_str or "resource" in error_str or "quota" in error_str or "overloaded" in error_str:
                if attempt == retries - 1:
                    logger.error(f"API Limit or Server error reached after {retries} retries: {e}")
                    raise e
                
                sleep_time = (base_delay * (2 ** attempt)) + random.uniform(1, 5)
                logger.warning(f"API Limit/Server hit. Retrying in {sleep_time:.1f}s... (Attempt {attempt+1}/{retries})")
                time.sleep(sleep_time)
            else:
                raise e

def load_prompt(filename, **kwargs):
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
    arxiv_search_tool,
    github_readme_tool,
)

client = genai.Client(api_key=os.environ.get("GOOGLE_API_KEY"))
MODEL_NAME = os.environ.get("LLM_MODEL_NAME", "gemini-2.5-flash-lite")


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

    tools = [github_search_tool, tavily_search_tool, wikipedia_search_tool, arxiv_search_tool, github_readme_tool]
    
    try:
        response = generate_with_retry(
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
        
        tools_used = []
        try:
            calls = getattr(response.candidates[0], 'function_calls', [])
            for call in calls:
                tools_used.append({
                    "name": call.name,
                    "args": call.args
                })
        except (AttributeError, IndexError):
            pass

        result = {
            "content": content,
            "tools_used": tools_used
        }

        logger.info(f"✅ Output: {content[:100]}...")
        return json.dumps(result), []

    except Exception as e:
        logger.error(f"Error: {e}")
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
        response = generate_with_retry(
            model=MODEL_NAME,
            contents=prompt,
            config=types.GenerateContentConfig(
                system_instruction=system_message,
                temperature=0,
                max_output_tokens=max_tokens,
            )
        )
        content = response.text

        logger.info(f"Output: {content[:100]}...")
        return content, []
    except Exception as e:
        logger.error(f"Error: {e}")
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
        response = generate_with_retry(
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
        logger.error(f"Error in Editor Agent: {e}")
        return prompt, [] 


def critique_agent(goal: str, output: str):
    logger.info("==================================")
    logger.info("🧠 Critique Agent")
    logger.info("==================================")

    import re
    prompt = load_prompt("critique_agent.md", goal=goal, output=output)

    try:
        response = generate_with_retry(
            model=MODEL_NAME,
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=0,
                response_mime_type="application/json"
            )
        )
        raw = response.text.strip()
        if raw.startswith("```"):
             raw = re.sub(r"^```[a-zA-Z]*\n?", "", raw)
             raw = re.sub(r"\n?```$", "", raw)
        return json.loads(raw)
    except Exception as f:
        logger.error(f"Error in Critique Agent: {f}")
        return {"critique": "good", "reason": "System error in critic"}
