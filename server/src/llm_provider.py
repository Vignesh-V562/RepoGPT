import os
import json
import logging
import time
import random
from typing import List, Dict, Any, Optional, Union
from google import genai
from google.genai import types
from groq import Groq
import re

logger = logging.getLogger(__name__)

# Model constants
LLAMA_3_3_70B = "llama-3.3-70b-versatile"
LLAMA_3_1_8B = "llama-3.1-8b-instant"

# Mode routing as requested by user
MODE_CONFIG = {
    "architect": LLAMA_3_3_70B,
    "analyst": LLAMA_3_3_70B,
    "chat": LLAMA_3_1_8B,
    "default": LLAMA_3_3_70B
}

class LLMProvider:
    def __init__(self):
        self.google_client = None
        self.groq_client = None
        self._check_keys()

    def _check_keys(self):
        """Pick up API keys if they were loaded after initialization (e.g. by load_dotenv)"""
        if not self.google_client:
            google_key = os.environ.get("GOOGLE_API_KEY")
            if google_key:
                try:
                    self.google_client = genai.Client(api_key=google_key)
                    logger.info("Google GenAI client initialized.")
                except Exception as e:
                    logger.error(f"Failed to init Google client: {e}")

        if not self.groq_client:
            groq_key = os.environ.get("GROQ_API_KEY")
            if groq_key and groq_key != "your_groq_api_key_here":
                try:
                    self.groq_client = Groq(api_key=groq_key)
                    logger.info("Groq client initialized.")
                except Exception as e:
                    logger.error(f"Failed to init Groq client: {e}")

    def get_model_for_mode(self, mode: str) -> str:
        return MODE_CONFIG.get(mode, MODE_CONFIG["default"])

    def generate_content(
        self, 
        mode: str, 
        prompt: str, 
        system_instruction: Optional[str] = None, 
        tools: Optional[List[Any]] = None,
        json_mode: bool = False,
        retries: int = 3
    ):
        self._check_keys()
        model_id = self.get_model_for_mode(mode)
        
        # If user explicitly sets LLM_MODEL_NAME in env, override but keep mode-based logic if possible
        # Actually, user wants to use Groq for Architect mode.
        
        if "llama" in model_id.lower():
            if not self.groq_client:
                logger.error("Groq client not initialized but Llama model requested.")
                # Fallback to Google if available
                if self.google_client:
                    return self._generate_with_google(os.environ.get("LLM_MODEL_NAME", "gemini-2.0-flash-lite"), prompt, system_instruction, tools, json_mode, retries)
                raise ValueError("GROQ_API_KEY not found")
            return self._generate_with_groq(model_id, prompt, system_instruction, tools, json_mode, retries)
        else:
            if not self.google_client:
                raise ValueError("GOOGLE_API_KEY not found")
            return self._generate_with_google(model_id, prompt, system_instruction, tools, json_mode, retries)

    def generate_content_stream(
        self, 
        mode: str, 
        prompt: str, 
        system_instruction: Optional[str] = None
    ):
        self._check_keys()
        model_id = self.get_model_for_mode(mode)
        
        if "llama" in model_id.lower():
            return self._stream_with_groq(model_id, prompt, system_instruction)
        else:
            return self._stream_with_google(model_id, prompt, system_instruction)

    def _stream_with_google(self, model_id, prompt, system_instruction):
        config_params = {"temperature": 0.1}
        if system_instruction:
            config_params["system_instruction"] = system_instruction
            
        try:
            response_stream = self.google_client.models.generate_content_stream(
                model=model_id,
                contents=prompt,
                config=types.GenerateContentConfig(**config_params)
            )
            for chunk in response_stream:
                if chunk.text:
                    yield chunk.text
        except Exception as e:
            logger.error(f"Google streaming error: {e}")
            yield f"[Streaming Error: {str(e)}]"

    def _stream_with_groq(self, model_id, prompt, system_instruction):
        messages = []
        if system_instruction:
            messages.append({"role": "system", "content": system_instruction})
        messages.append({"role": "user", "content": prompt})
        
        try:
            response = self.groq_client.chat.completions.create(
                model=model_id,
                messages=messages,
                temperature=0.1,
                stream=True
            )
            for chunk in response:
                if chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content
        except Exception as e:
            logger.error(f"Groq streaming error: {e}")
            yield f"[Streaming Error: {str(e)}]"

    def _generate_with_google(self, model_id, prompt, system_instruction, tools, json_mode, retries):
        from google.genai import types
        
        config_params = {
            "temperature": 0.1,
        }
        if system_instruction:
            config_params["system_instruction"] = system_instruction
        if json_mode:
            config_params["response_mime_type"] = "application/json"
        
        if tools:
            config_params["tools"] = tools
            config_params["automatic_function_calling"] = types.AutomaticFunctionCallingConfig(disable=False)

        for attempt in range(retries):
            try:
                response = self.google_client.models.generate_content(
                    model=model_id,
                    contents=prompt,
                    config=types.GenerateContentConfig(**config_params)
                )
                
                # Extract tools used
                tools_used = []
                try:
                    # Access function calls from candidates
                    if response.candidates and response.candidates[0].function_calls:
                        for call in response.candidates[0].function_calls:
                            tools_used.append({
                                "name": call.name,
                                "args": call.args
                            })
                except (AttributeError, IndexError):
                    pass
                    
                return response.text, tools_used
            except Exception as e:
                if self._is_retryable(e) and attempt < retries - 1:
                    wait = (2 ** attempt) + random.uniform(0, 1)
                    time.sleep(wait)
                    continue
                raise e

    def _generate_with_groq(self, model_id, prompt, system_instruction, tools, json_mode, retries):
        messages = []
        if system_instruction:
            messages.append({"role": "system", "content": system_instruction})
        messages.append({"role": "user", "content": prompt})
        
        # Convert tools to Groq format (OpenAI format)
        groq_tools = None
        if tools:
            from src.research_tools import arxiv_tool_def, tavily_tool_def, github_tool_def, github_readme_tool_def, tool_mapping
            # Map tools to their definitions
            groq_tools = []
            tool_name_map = {
                "arxiv_search_tool": arxiv_tool_def,
                "tavily_search_tool": tavily_tool_def,
                "github_search_tool": github_tool_def,
                "github_readme_tool": github_readme_tool_def
            }
            
            for t in tools:
                name = t.__name__ if hasattr(t, '__name__') else str(t)
                if name in tool_name_map:
                    groq_tools.append(tool_name_map[name])
                elif isinstance(t, dict) and "function" in t:
                    groq_tools.append(t)

        for attempt in range(retries):
            try:
                params = {
                    "model": model_id,
                    "messages": messages,
                    "temperature": 0.1,
                }
                if json_mode:
                    params["response_format"] = {"type": "json_object"}
                if groq_tools:
                    params["tools"] = groq_tools
                    params["tool_choice"] = "auto"

                response = self.groq_client.chat.completions.create(**params)
                message = response.choices[0].message
                content = message.content or ""
                
                logger.debug(f"GROQ: Raw response received. Content length: {len(content)}")
                
                tools_used = []
                if message.tool_calls:
                    logger.info(f"GROQ: Tool calls detected: {[t.function.name for t in message.tool_calls]}")
                    for tool_call in message.tool_calls:
                        tool_name = tool_call.function.name
                        tool_args = json.loads(tool_call.function.arguments)
                        
                        # Execute tool immediately if it's in tool_mapping to match "automatic_function_calling"
                        from src.research_tools import tool_mapping
                        if tool_name in tool_mapping:
                            tool_result = tool_mapping[tool_name](**tool_args)
                            # Add to messages to get final response
                            messages.append(message)
                            messages.append({
                                "role": "tool",
                                "tool_call_id": tool_call.id,
                                "name": tool_name,
                                "content": json.dumps(tool_result)
                            })
                            tools_used.append({"name": tool_name, "args": tool_args})
                    
                    # Call again to get final answer after tool results
                    if tools_used:
                        logger.info("GROQ: Sending tool results back to model for final response...")
                        final_response = self.groq_client.chat.completions.create(
                            model=model_id,
                            messages=messages
                        )
                        content = final_response.choices[0].message.content or ""
                        logger.info("GROQ: Final response received.")
                
                return content, tools_used
            except Exception as e:
                if self._is_retryable(e) and attempt < retries - 1:
                    wait = (attempt + 1) * 2
                    time.sleep(wait)
                    continue
                raise e

    def _is_retryable(self, e):
        err = str(e).lower()
        return any(x in err for x in ["429", "rate limit", "overloaded", "503", "500", "resource_exhausted"])

# Global instance
llm = LLMProvider()
