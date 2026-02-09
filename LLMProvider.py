"""
LLM Provider Abstraction Layer

This module provides a unified interface for multiple LLM providers:
- AWS Bedrock (Anthropic Claude, Llama, Mistral, etc.)
- OpenAI (GPT-4, GPT-3.5, etc.)
- Azure OpenAI
- Future: Google Gemini, Cohere, etc.

This abstraction enables easy switching between providers and models
without changing agent logic.
"""

import os
import json
import logging
import boto3
import time
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional
from dataclasses import dataclass

logger = logging.getLogger("llm_provider")
logger.setLevel(logging.DEBUG)


@dataclass
class ModelConfig:
    """Configuration for an LLM model"""
    provider: str  # "bedrock", "openai", "azure_openai"
    model_id: str  # e.g., "anthropic.claude-3-sonnet-20240229-v1:0"
    max_tokens: int = 1000
    temperature: float = 0.3
    region: Optional[str] = None  # For AWS Bedrock
    api_key: Optional[str] = None  # For OpenAI/Azure
    api_version: Optional[str] = None  # For Azure OpenAI


class LLMProvider(ABC):
    """Abstract base class for LLM providers"""
    
    @abstractmethod
    def invoke(self, prompt: str, config: ModelConfig) -> Dict[str, Any]:
        """
        Invoke the LLM with a prompt
        
        Args:
            prompt: The prompt to send to the model
            config: ModelConfig with provider settings
            
        Returns:
            Dict with keys: text (response), cost (estimated), provider, model
            Or dict with error key if failed
        """
        pass


class BedrockProvider(LLMProvider):
    """AWS Bedrock LLM Provider"""
    
    def __init__(self):
        self.provider_name = "bedrock"
        logger.debug("Initialized BedrockProvider")
    
    def invoke(self, prompt: str, config: ModelConfig) -> Dict[str, Any]:
        """Invoke AWS Bedrock model"""
        logger.info(f"BedrockProvider: Invoking {config.model_id}")
        start_time = time.time()
        
        try:
            region = config.region or os.getenv("AWS_REGION", "us-east-1")
            client = boto3.client("bedrock-runtime", region_name=region)
            
            body = json.dumps({
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": config.max_tokens,
                "temperature": config.temperature,
                "messages": [{"role": "user", "content": prompt}]
            })
            
            logger.debug(f"BedrockProvider: Sending request ({len(body)} bytes)")
            response = client.invoke_model(modelId=config.model_id, body=body)
            
            response_body = json.loads(response["body"].read())
            text = response_body.get("content", [])[0].get("text", "")
            
            elapsed = time.time() - start_time
            logger.info(f"BedrockProvider: Response received ({len(text)} chars, {elapsed:.2f}s)")
            
            # Try to parse as JSON
            try:
                result_json = json.loads(text)
                logger.debug("BedrockProvider: Successfully parsed JSON response")
                return {
                    "text": json.dumps(result_json),
                    "parsed_json": result_json,
                    "cost": self._estimate_cost(config.model_id, len(prompt), len(text)),
                    "provider": self.provider_name,
                    "model": config.model_id,
                    "elapsed_seconds": elapsed
                }
            except json.JSONDecodeError:
                logger.warning("BedrockProvider: Response is not JSON, returning as text")
                return {
                    "text": text,
                    "format": "text",
                    "cost": self._estimate_cost(config.model_id, len(prompt), len(text)),
                    "provider": self.provider_name,
                    "model": config.model_id,
                    "elapsed_seconds": elapsed
                }
                
        except Exception as e:
            elapsed = time.time() - start_time
            logger.error(f"BedrockProvider failed after {elapsed:.2f}s: {type(e).__name__}: {e}", exc_info=True)
            return {
                "error": str(e),
                "provider": self.provider_name,
                "model": config.model_id,
                "elapsed_seconds": elapsed
            }
    
    @staticmethod
    def _estimate_cost(model_id: str, input_chars: int, output_chars: int) -> float:
        """Rough cost estimation for Bedrock models (USD)"""
        # Approximate pricing per 1K tokens (chars ~= 4 tokens)
        pricing = {
            "anthropic.claude-3-sonnet": {"input": 0.003, "output": 0.015},
            "anthropic.claude-3-haiku": {"input": 0.00025, "output": 0.00125},
            "anthropic.claude-3-opus": {"input": 0.015, "output": 0.075},
        }
        
        base_model = next((k for k in pricing.keys() if k in model_id), None)
        if not base_model:
            return 0.0
        
        input_cost = (input_chars / 4000) * pricing[base_model]["input"]
        output_cost = (output_chars / 4000) * pricing[base_model]["output"]
        return round(input_cost + output_cost, 6)


class OpenAIProvider(LLMProvider):
    """OpenAI LLM Provider (GPT-4, GPT-3.5-turbo)"""
    
    def __init__(self):
        self.provider_name = "openai"
        self.api_key = os.getenv("OPENAI_API_KEY")
        logger.debug("Initialized OpenAIProvider")
    
    def invoke(self, prompt: str, config: ModelConfig) -> Dict[str, Any]:
        """Invoke OpenAI model"""
        logger.info(f"OpenAIProvider: Invoking {config.model_id}")
        start_time = time.time()
        
        if not self.api_key and not config.api_key:
            error_msg = "OpenAI API key not configured"
            logger.error(error_msg)
            return {"error": error_msg, "provider": self.provider_name, "model": config.model_id}
        
        try:
            import openai
            
            client = openai.OpenAI(api_key=config.api_key or self.api_key)
            
            logger.debug(f"OpenAIProvider: Sending request to {config.model_id}")
            response = client.chat.completions.create(
                model=config.model_id,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=config.max_tokens,
                temperature=config.temperature
            )
            
            text = response.choices[0].message.content
            elapsed = time.time() - start_time
            
            logger.info(f"OpenAIProvider: Response received ({len(text)} chars, {elapsed:.2f}s)")
            
            # Try to parse as JSON
            try:
                result_json = json.loads(text)
                logger.debug("OpenAIProvider: Successfully parsed JSON response")
                return {
                    "text": json.dumps(result_json),
                    "parsed_json": result_json,
                    "cost": self._estimate_cost(config.model_id, response.usage.prompt_tokens, response.usage.completion_tokens),
                    "provider": self.provider_name,
                    "model": config.model_id,
                    "elapsed_seconds": elapsed
                }
            except json.JSONDecodeError:
                logger.warning("OpenAIProvider: Response is not JSON, returning as text")
                return {
                    "text": text,
                    "format": "text",
                    "cost": self._estimate_cost(config.model_id, response.usage.prompt_tokens, response.usage.completion_tokens),
                    "provider": self.provider_name,
                    "model": config.model_id,
                    "elapsed_seconds": elapsed
                }
                
        except ImportError:
            error_msg = "openai package not installed. Run: pip install openai"
            logger.error(error_msg)
            return {"error": error_msg, "provider": self.provider_name, "model": config.model_id}
        except Exception as e:
            elapsed = time.time() - start_time
            logger.error(f"OpenAIProvider failed after {elapsed:.2f}s: {type(e).__name__}: {e}", exc_info=True)
            return {
                "error": str(e),
                "provider": self.provider_name,
                "model": config.model_id,
                "elapsed_seconds": elapsed
            }
    
    @staticmethod
    def _estimate_cost(model_id: str, input_tokens: int, output_tokens: int) -> float:
        """Cost estimation for OpenAI models (USD)"""
        # Pricing per 1K tokens
        pricing = {
            "gpt-4-turbo": {"input": 0.01, "output": 0.03},
            "gpt-4": {"input": 0.03, "output": 0.06},
            "gpt-3.5-turbo": {"input": 0.0015, "output": 0.002},
        }
        
        base_model = next((k for k in pricing.keys() if k in model_id), None)
        if not base_model:
            return 0.0
        
        input_cost = (input_tokens / 1000) * pricing[base_model]["input"]
        output_cost = (output_tokens / 1000) * pricing[base_model]["output"]
        return round(input_cost + output_cost, 6)


class AzureOpenAIProvider(LLMProvider):
    """Azure OpenAI LLM Provider"""
    
    def __init__(self):
        self.provider_name = "azure_openai"
        self.api_key = os.getenv("AZURE_OPENAI_KEY")
        self.api_endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
        logger.debug("Initialized AzureOpenAIProvider")
    
    def invoke(self, prompt: str, config: ModelConfig) -> Dict[str, Any]:
        """Invoke Azure OpenAI model"""
        logger.info(f"AzureOpenAIProvider: Invoking {config.model_id}")
        start_time = time.time()
        
        if not self.api_key or not self.api_endpoint:
            error_msg = "Azure OpenAI credentials not configured"
            logger.error(error_msg)
            return {"error": error_msg, "provider": self.provider_name, "model": config.model_id}
        
        try:
            import openai
            
            client = openai.AzureOpenAI(
                api_key=config.api_key or self.api_key,
                api_version=config.api_version or "2024-02-15-preview",
                azure_endpoint=self.api_endpoint
            )
            
            logger.debug(f"AzureOpenAIProvider: Sending request to {config.model_id}")
            response = client.chat.completions.create(
                model=config.model_id,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=config.max_tokens,
                temperature=config.temperature
            )
            
            text = response.choices[0].message.content
            elapsed = time.time() - start_time
            
            logger.info(f"AzureOpenAIProvider: Response received ({len(text)} chars, {elapsed:.2f}s)")
            
            # Try to parse as JSON
            try:
                result_json = json.loads(text)
                logger.debug("AzureOpenAIProvider: Successfully parsed JSON response")
                return {
                    "text": json.dumps(result_json),
                    "parsed_json": result_json,
                    "cost": self._estimate_cost(config.model_id, response.usage.prompt_tokens, response.usage.completion_tokens),
                    "provider": self.provider_name,
                    "model": config.model_id,
                    "elapsed_seconds": elapsed
                }
            except json.JSONDecodeError:
                logger.warning("AzureOpenAIProvider: Response is not JSON, returning as text")
                return {
                    "text": text,
                    "format": "text",
                    "cost": self._estimate_cost(config.model_id, response.usage.prompt_tokens, response.usage.completion_tokens),
                    "provider": self.provider_name,
                    "model": config.model_id,
                    "elapsed_seconds": elapsed
                }
                
        except ImportError:
            error_msg = "openai package not installed. Run: pip install openai"
            logger.error(error_msg)
            return {"error": error_msg, "provider": self.provider_name, "model": config.model_id}
        except Exception as e:
            elapsed = time.time() - start_time
            logger.error(f"AzureOpenAIProvider failed after {elapsed:.2f}s: {type(e).__name__}: {e}", exc_info=True)
            return {
                "error": str(e),
                "provider": self.provider_name,
                "model": config.model_id,
                "elapsed_seconds": elapsed
            }
    
    @staticmethod
    def _estimate_cost(model_id: str, input_tokens: int, output_tokens: int) -> float:
        """Cost estimation for Azure OpenAI models (USD)"""
        # Azure pricing per 1K tokens (similar to OpenAI but may vary)
        pricing = {
            "gpt-4": {"input": 0.03, "output": 0.06},
            "gpt-35-turbo": {"input": 0.0015, "output": 0.002},
        }
        
        base_model = next((k for k in pricing.keys() if k in model_id), None)
        if not base_model:
            return 0.0
        
        input_cost = (input_tokens / 1000) * pricing[base_model]["input"]
        output_cost = (output_tokens / 1000) * pricing[base_model]["output"]
        return round(input_cost + output_cost, 6)


class LLMFactory:
    """Factory for creating LLM providers"""
    
    _providers = {
        "bedrock": BedrockProvider,
        "openai": OpenAIProvider,
        "azure_openai": AzureOpenAIProvider,
    }
    
    @classmethod
    def get_provider(cls, provider_name: str) -> LLMProvider:
        """Get a provider instance"""
        if provider_name not in cls._providers:
            logger.error(f"Unknown provider: {provider_name}")
            raise ValueError(f"Unknown LLM provider: {provider_name}")
        
        logger.debug(f"Creating provider: {provider_name}")
        return cls._providers[provider_name]()
    
    @classmethod
    def invoke(cls, prompt: str, config: ModelConfig) -> Dict[str, Any]:
        """Convenience method: create provider and invoke in one call"""
        provider = cls.get_provider(config.provider)
        return provider.invoke(prompt, config)
    
    @classmethod
    def register_provider(cls, name: str, provider_class: type):
        """Register a new provider (for extensibility)"""
        logger.debug(f"Registering new provider: {name}")
        cls._providers[name] = provider_class


class ModelConfigManager:
    """Manages model configurations from environment and config files"""
    
    def __init__(self, env_prefix: str = "LLM_"):
        """
        Initialize config manager
        
        Args:
            env_prefix: Prefix for environment variables (e.g., LLM_DATA_COLLECTOR_MODEL)
        """
        self.env_prefix = env_prefix
        self.region = os.getenv("AWS_REGION", "us-east-1")
    
    def get_config(self, agent_name: str) -> ModelConfig:
        """
        Get ModelConfig for an agent from environment variables
        
        Expected env vars:
        - {env_prefix}{AGENT_NAME}_MODEL: model ID
        - {env_prefix}{AGENT_NAME}_PROVIDER: provider name (default: bedrock)
        - {env_prefix}{AGENT_NAME}_MAX_TOKENS: max tokens (default: 1000)
        - {env_prefix}{AGENT_NAME}_TEMPERATURE: temperature (default: 0.3)
        """
        agent_lower = agent_name.upper()
        
        # Get model ID
        model_id_key = f"{self.env_prefix}{agent_lower}_MODEL"
        model_id = os.getenv(model_id_key)
        if not model_id:
            logger.warning(f"Model ID not configured for {agent_name}, using default")
            model_id = "anthropic.claude-3-sonnet-20240229-v1:0"  # Default fallback
        
        # Get provider
        provider_key = f"{self.env_prefix}{agent_lower}_PROVIDER"
        provider = os.getenv(provider_key, "bedrock")
        
        # Get max tokens
        max_tokens_key = f"{self.env_prefix}{agent_lower}_MAX_TOKENS"
        max_tokens = int(os.getenv(max_tokens_key, "1000"))
        
        # Get temperature
        temp_key = f"{self.env_prefix}{agent_lower}_TEMPERATURE"
        temperature = float(os.getenv(temp_key, "0.3"))
        
        logger.debug(f"Loaded config for {agent_name}: provider={provider}, model={model_id}")
        
        return ModelConfig(
            provider=provider,
            model_id=model_id,
            max_tokens=max_tokens,
            temperature=temperature,
            region=self.region
        )
    
    @staticmethod
    def load_from_file(filepath: str) -> Dict[str, ModelConfig]:
        """Load model configs from JSON file"""
        logger.debug(f"Loading model configs from {filepath}")
        try:
            with open(filepath, 'r') as f:
                data = json.load(f)
            
            configs = {}
            for agent_name, config_dict in data.items():
                configs[agent_name] = ModelConfig(**config_dict)
            
            logger.info(f"Loaded {len(configs)} model configs from file")
            return configs
        except Exception as e:
            logger.error(f"Failed to load configs from {filepath}: {e}")
            return {}


if __name__ == "__main__":
    # Quick test
    print("LLM Provider Abstraction Layer - Test")
    print("=" * 50)
    
    # Test configuration
    config = ModelConfig(
        provider="bedrock",
        model_id="anthropic.claude-3-haiku-20240307-v1:0",
        max_tokens=100,
        temperature=0.3
    )
    
    print(f"Provider: {config.provider}")
    print(f"Model: {config.model_id}")
    print(f"Max tokens: {config.max_tokens}")
    print(f"Temperature: {config.temperature}")
    
    # Test config manager
    print("\nTesting ModelConfigManager:")
    manager = ModelConfigManager()
    data_collector_config = manager.get_config("DATA_COLLECTOR")
    print(f"DataCollector config: {data_collector_config}")
