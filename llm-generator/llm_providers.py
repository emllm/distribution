import asyncio
import httpx
import openai
import anthropic
from typing import Dict, Any, Optional
from abc import ABC, abstractmethod


class LLMProvider(ABC):
    """Abstract base class for LLM providers"""

    @abstractmethod
    async def generate_code(self, prompt: str, model_params: Dict[str, Any] = None) -> Dict[str, Any]:
        """Generate code based on prompt"""
        pass

    @abstractmethod
    async def test_connection(self) -> str:
        """Test connection to LLM service"""
        pass


class OpenAIProvider(LLMProvider):
    def __init__(self, api_key: str):
        self.client = openai.AsyncOpenAI(api_key=api_key)
        self.default_model = "gpt-4-turbo-preview"

    async def generate_code(self, prompt: str, model_params: Dict[str, Any] = None) -> Dict[str, Any]:
        try:
            params = {
                "model": self.default_model,
                "messages": [
                    {"role": "system",
                     "content": "You are an expert software developer who generates complete, working applications with proper structure and documentation."},
                    {"role": "user", "content": prompt}
                ],
                "max_tokens": 4000,
                "temperature": 0.7,
                **(model_params or {})
            }

            response = await self.client.chat.completions.create(**params)

            return {
                "success": True,
                "content": response.choices[0].message.content,
                "model": response.model,
                "usage": response.usage.dict() if response.usage else None
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }

    async def test_connection(self) -> str:
        try:
            response = await self.client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[{"role": "user", "content": "Hello"}],
                max_tokens=10
            )
            return "healthy"
        except:
            return "unhealthy"


class AnthropicProvider(LLMProvider):
    def __init__(self, api_key: str):
        self.client = anthropic.AsyncAnthropic(api_key=api_key)
        self.default_model = "claude-3-sonnet-20240229"

    async def generate_code(self, prompt: str, model_params: Dict[str, Any] = None) -> Dict[str, Any]:
        try:
            params = {
                "model": self.default_model,
                "max_tokens": 4000,
                "temperature": 0.7,
                "messages": [
                    {"role": "user", "content": prompt}
                ],
                **(model_params or {})
            }

            response = await self.client.messages.create(**params)

            return {
                "success": True,
                "content": response.content[0].text,
                "model": response.model,
                "usage": {
                    "input_tokens": response.usage.input_tokens,
                    "output_tokens": response.usage.output_tokens
                }
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }

    async def test_connection(self) -> str:
        try:
            response = await self.client.messages.create(
                model=self.default_model,
                max_tokens=10,
                messages=[{"role": "user", "content": "Hello"}]
            )
            return "healthy"
        except:
            return "unhealthy"


class OllamaProvider(LLMProvider):
    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip('/')
        self.default_model = "codellama:7b-instruct"

    async def generate_code(self, prompt: str, model_params: Dict[str, Any] = None) -> Dict[str, Any]:
        try:
            params = {
                "model": self.default_model,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": 0.7,
                    "top_p": 0.9,
                    **(model_params or {})
                }
            }

            async with httpx.AsyncClient(timeout=120.0) as client:
                response = await client.post(
                    f"{self.base_url}/api/generate",
                    json=params
                )

                if response.status_code == 200:
                    result = response.json()
                    return {
                        "success": True,
                        "content": result["response"],
                        "model": result["model"],
                        "usage": {
                            "total_duration": result.get("total_duration"),
                            "load_duration": result.get("load_duration"),
                            "prompt_eval_count": result.get("prompt_eval_count"),
                            "eval_count": result.get("eval_count")
                        }
                    }
                else:
                    return {
                        "success": False,
                        "error": f"Ollama API error: {response.status_code} - {response.text}"
                    }
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }

    async def test_connection(self) -> str:
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(f"{self.base_url}/api/tags")
                return "healthy" if response.status_code == 200 else "unhealthy"
        except:
            return "unhealthy"

