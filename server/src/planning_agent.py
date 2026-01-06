import os
import json
import re
import logging
from datetime import datetime
from google import genai
from google.genai import types
from src.agents import (
    research_agent,
    writer_agent,
    editor_agent,
)

logger = logging.getLogger(__name__)

client = genai.Client(api_key=os.environ.get("GOOGLE_API_KEY"))
MODEL_NAME = os.environ.get("LLM_MODEL_NAME", "gemini-2.5-flash-lite")


def clean_json_block(raw: str) -> str:
    raw = raw.strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```[a-zA-Z]*\n?", "", raw)
        raw = re.sub(r"\n?```$", "", raw)
    return raw.strip("` \n")


from typing import List
import json, ast


def planner_agent(topic: str) -> List[str]:
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    prompt_path = os.path.join(base_dir, "prompts", "planner_agent.md")
    with open(prompt_path, "r", encoding="utf-8") as f:
        prompt_template = f.read()
    
    prompt = prompt_template.format(topic=topic)

    response = client.models.generate_content(
        model=MODEL_NAME,
        contents=prompt,
        config=types.GenerateContentConfig(temperature=0.2)
    )
    raw = response.text.strip()

    def _coerce_to_list(s: str) -> List[str]:
        s = s.strip()
        if s.startswith("```"):
            s = re.sub(r"^```[a-zA-Z]*\n?", "", s)
            s = re.sub(r"\n?```$", "", s)
        
        try:
            obj = json.loads(s)
            if isinstance(obj, list) and all(isinstance(x, str) for x in obj):
                return obj
        except:
            pass
            
        try:
            obj = ast.literal_eval(s)
            if isinstance(obj, list) and all(isinstance(x, str) for x in obj):
                return obj
        except:
            pass
            
        if "\n" in s:
            lines = [l.strip("-* 123456789. ") for l in s.split("\n") if l.strip()]
            return [l for l in lines if len(l) > 10]
            
        return []

    steps = _coerce_to_list(raw)

    final_required = "Writer agent: Generate a 'Project Blueprint' that lists Core Features, Recommended Stack, and a table of Reference GitHub Repositories (with links)."
    
    if not steps:
        return [
            f"Research agent: Use Tavily to research architecture patterns for '{topic}'.",
            f"Research agent: Use github_search_tool to find repositories matching '{topic}'.",
            "Research agent: Synthesize data and identify core technical requirements.",
            final_required
        ]

    if not any("Project Blueprint" in s for s in steps):
        steps.append(final_required)
    
    return steps[:5]


def executor_agent_step(step_title: str, history: list, prompt: str):
    """
    Executes a step of the executor agent.
    Returns:
        - step_title (str)
        - agent_name (str)
        - output (str)
    """

    context = f"User Prompt:\n{prompt}\n\nHistory so far:\n"
    
    def truncate_text(text: str, max_chars: int = 2000) -> str:
        if len(text) <= max_chars:
            return text
        return text[:max_chars] + f"\n\n... [TRUNCATED - Total {len(text)} characters] ..."

    for i, (desc, agent, output) in enumerate(history):
        # We allow the very last step to be a bit longer if it's the draft we are currently editing
        is_last_step = (i == len(history) - 1)
        limit = 4000 if is_last_step else 2000
        
        truncated_output = truncate_text(output.strip(), max_chars=limit)
        
        if "draft" in desc.lower() or agent == "writer_agent":
            context += f"\n✍️ Draft (Step {i + 1}):\n{truncated_output}\n"
        elif "feedback" in desc.lower() or agent == "editor_agent":
            context += f"\n🧠 Feedback (Step {i + 1}):\n{truncated_output}\n"
        elif "research" in desc.lower() or agent == "research_agent":
            context += f"\n🔍 Research (Step {i + 1}):\n{truncated_output}\n"
        else:
            context += f"\n🧩 Other (Step {i + 1}) by {agent}:\n{truncated_output}\n"

    enriched_task = f"""{context}

🧩 Your next task:
{step_title}
"""

    step_lower = step_title.lower()
    if "research" in step_lower:
        max_retries = 1
        current_attempt = 0
        final_content = ""
        
        while current_attempt <= max_retries:
            logger.info(f"Attempt {current_attempt + 1} for step: {step_title}")
            raw_output, _ = research_agent(prompt=enriched_task)
            
            try:
                parsed = json.loads(raw_output)
                content = parsed["content"]
                import time
                time.sleep(5) 

                from src.agents import critique_agent
                evaluation = critique_agent(goal=prompt, output=content)
                
                if evaluation.get("critique") == "bad":
                    reason = evaluation.get('reason', 'Unknown reason')
                    logger.warning(f"Attempt {current_attempt + 1} failed critique: {reason}")
                    
                    if current_attempt < max_retries:
                        enriched_task += f"\n\n CRITIQUE FROM PREVIOUS ATTEMPT:\n{reason}\n\nPlease revise your research to address the critique above."
                        current_attempt += 1
                        continue
                    else:
                        final_content = f" SELF-CORRECTION FAILED after {max_retries + 1} attempts.\nReason: {reason}\n\n{content}"
                else:
                    final_content = content
                break
            except Exception as e:
                logger.error(f"Error in research processing: {e}")
                final_content = raw_output
                break

        return step_title, "research_agent", final_content
    elif "draft" in step_lower or "write" in step_lower or "blueprint" in step_lower:
        content, _ = writer_agent(prompt=enriched_task)
        return step_title, "writer_agent", content
    elif "revise" in step_lower or "edit" in step_lower or "feedback" in step_lower:
        content, _ = editor_agent(prompt=enriched_task)
        return step_title, "editor_agent", content
    else:
        logger.warning(f"Unknown step type: {step_title}, falling back to writer_agent")
        content, _ = writer_agent(prompt=enriched_task)
        return step_title, "writer_agent", content
