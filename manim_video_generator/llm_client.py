import os
from langchain_openai import AzureChatOpenAI

# LLM client factory

def get_llm_client() -> AzureChatOpenAI:
    """Return an AzureChatOpenAI client configured from environment variables."""
    return AzureChatOpenAI(
        azure_endpoint=os.getenv('ENDPOINT_URL'),
        api_key=os.getenv('AZURE_OPENAI_API_KEY'),
        api_version='2024-12-01-preview',
        azure_deployment=os.getenv('AZURE_DEPLOYMENT', 'o3-mini-2'),
        max_completion_tokens=100000,
    ) 