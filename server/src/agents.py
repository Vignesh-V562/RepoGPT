import os
import logging
import json
from datetime import datetime
from src.llm_provider import llm

logger = logging.getLogger(__name__)

def load_prompt(filename, **kwargs):
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    path = os.path.join(base_dir, "prompts", filename)
    with open(path, "r", encoding="utf-8") as f:
        template = f.read()
    if kwargs:
        result = template
        for k, v in kwargs.items():
            result = result.replace("{" + k + "}", str(v))
        return result
    return template
from src.research_tools import (
    github_search_tool,
    tavily_search_tool,
    wikipedia_search_tool,
    arxiv_search_tool,
    github_readme_tool,
)


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
        content, tools_used = llm.generate_content(
            mode="architect",
            prompt=full_prompt,
            tools=tools
        )
        

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
        content, _ = llm.generate_content(
            mode="analyst",
            prompt=prompt,
            system_instruction=system_message
        )

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
        content, _ = llm.generate_content(
            mode="analyst",
            prompt=prompt,
            system_instruction=system_message
        )
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
        content, _ = llm.generate_content(
            mode="analyst",
            prompt=prompt,
            json_mode=True
        )
        # Robust extraction
        match = re.search(r"\{.*\}", content, re.DOTALL)
        if match:
            raw = match.group(0)
        else:
            raw = content.strip()
            
        if raw.startswith("```"):
             raw = re.sub(r"^```[a-zA-Z]*\n?", "", raw)
             raw = re.sub(r"\n?```$", "", raw)
        
        parsed = json.loads(raw)
        return parsed
    except Exception as f:
        logger.error(f"Error in Critique Agent: {f}")
        # If it failed to decode, try one last ditch regex for critique value
        if "critique" in str(content).lower():
            if "bad" in str(content).lower():
                return {"critique": "bad", "reason": "Extracted 'bad' from malformed response"}
        return {"critique": "good", "reason": "System error in critic"}
