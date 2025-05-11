"""
Node: analyze_manim_error
=========================

Analyzes a Manim rendering error message by:
1. Searching the web (DuckDuckGo) for relevant pages.
2. Fetching content from top results.
3. Using an LLM to analyze the error and fetched content.
4. Returning a structured analysis of the likely cause and solution.
"""

import os
import json
import sys
import requests
from bs4 import BeautifulSoup
from langchain_openai import AzureChatOpenAI
from duckduckgo_search import DDGS
from dotenv import load_dotenv
import warnings
from pydantic import BaseModel, Field, ValidationError
from typing import List, Optional, Dict, Any

# Assuming state schema is defined in ../state.py
# from ..state import ManimWorkflowState # Adjust import path if needed

# Load environment variables
load_dotenv()
warnings.filterwarnings('ignore')

# --- Pydantic Schema for Structured Solution ---
class ManimSolution(BaseModel):
    likely_cause: str = Field(..., description="The most likely cause of the Manim error based on the provided context.")
    recommended_solution: str = Field(..., description="The recommended steps or explanation to fix the error.")
    code_fix: Optional[str] = Field(None, description="A specific code snippet suggestion, if applicable.")
    source_urls: List[str] = Field(..., description="List of URLs where relevant information was found.")
    confidence: str = Field("Medium", description="Confidence level in the solution (e.g., High, Medium, Low).")

# --- Helper for Fetching and Parsing Web Content ---
def _fetch_and_parse(url: str) -> Dict[str, Any]:
    """Fetches URL content and returns text or error."""
    print(f"Fetching: {url}...")
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3"}
    try:
        response = requests.get(url, headers=headers, timeout=20)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'html.parser')
        content_area = soup.find('article') or soup.find('main') or soup.find(role='main') or soup.find('body')
        text = content_area.get_text(separator=' ', strip=True) if content_area else ""
        print(f"Fetched {len(text)} characters.")
        return {"url": url, "text": text, "error": None}
    except requests.RequestException as e:
        print(f"Error fetching {url}: {e}")
        return {"url": url, "text": None, "error": str(e)}
    except Exception as e:
        print(f"Error parsing {url}: {e}")
        return {"url": url, "text": None, "error": f"Parsing error: {e}"}

# --- LangGraph Node Function ---
# def analyze_error_node(state: ManimWorkflowState) -> Dict[str, Any]: # Use this signature when integrated
def analyze_error_node(state: dict) -> Dict[str, Any]: # Using dict for now
    """
    LangGraph node to search for and analyze Manim errors.
    """
    print("--- Node: analyze_manim_error ---")
    error_message = state.get("render_error", "") # Get error from state
    if not error_message:
        print("No render error found in state.")
        return {"error_analysis": None, "analyze_error_error": "No error message provided in state."}

    final_result = {"original_error": error_message, "analysis": None, "error": None}

    try:
        # 1. Initialize LLM
        # TODO: Ideally, reuse the llm_client instance from the main graph state or config
        llm_client = AzureChatOpenAI(
            azure_endpoint=os.getenv('ENDPOINT_URL'),
            api_key=os.getenv('AZURE_OPENAI_API_KEY'),
            api_version=os.getenv('AZURE_API_VERSION', '2024-02-01'),
            azure_deployment=os.getenv("AZURE_DEPLOYMENT", "gpt-4o"),
            temperature=0.1,
            max_tokens=4000
        )

        # 2. Search directly using duckduckgo-search library
        print("Searching for relevant pages using DDGS...")
        search_results = []
        urls_to_fetch = []
        try:
            # Extract a concise query for the search engine
            error_lines = [line.strip() for line in error_message.strip().split('\n') if line.strip()]
            concise_error = next((line for line in error_lines if 'Error:' in line or 'Exception:' in line), None)
            if not concise_error:
                concise_error = " ".join(error_lines[:3])

            search_query = f"manim python error {concise_error}"
            print(f"Using concise search query: {search_query}")

            with DDGS(timeout=20) as ddgs:
                search_results = list(ddgs.text(search_query, max_results=5, region='wt-wt', safesearch='off', timelimit='y'))
                urls_to_fetch = [r['href'] for r in search_results if r.get('href')]
                print(f"Found {len(search_results)} results. Top URLs: {urls_to_fetch[:3]}")
        except Exception as e:
            print(f"DDGS search failed: {e}")
            final_result["error"] = f"DDGS search failed: {e}"
            # Continue without fetched content if search fails

        # 3. Fetch content from top URLs
        fetched_contents = []
        if urls_to_fetch:
            print(f"Fetching content from top {min(len(urls_to_fetch), 3)} URLs...")
            for url in urls_to_fetch[:3]:
                 fetched_contents.append(_fetch_and_parse(url)) # Use helper function
        else:
            print("No URLs found from search to fetch.")

        # 4. Analyze with LLM
        print("Analyzing content with LLM...")
        context_str = f"Original Manim Error:\n```\n{error_message}\n```\n\n"

        # Include search result snippets for context
        if search_results:
             context_str += "Relevant Search Results (Snippets):\n"
             for i, res in enumerate(search_results[:3]): # Use top 3 results
                 context_str += f"\n--- Search Result {i+1} ({res.get('href', 'N/A')}) ---\n"
                 context_str += f"Title: {res.get('title', 'N/A')}\n"
                 context_str += f"Snippet: {res.get('body', 'N/A')}\n" # 'body' usually holds snippet
                 context_str += "--- End Search Result {i+1} ---\n"

        # Include fetched full content if available
        if fetched_contents:
            context_str += "\nFetched Full Content from URLs:\n"
            for i, content in enumerate(fetched_contents):
                if content["text"]:
                    context_str += f"\n--- Fetched Source {i+1} ({content['url']}) ---\n"
                    context_str += content["text"][:5000]
                    context_str += "\n--- End Fetched Source {i+1} ---\n"
                elif content["error"]:
                     context_str += f"\n--- Fetched Source {i+1} ({content['url']}) ---\n"
                     context_str += f"Error fetching content: {content['error']}"
                     context_str += "\n--- End Fetched Source {i+1} ---\n"

        if not search_results and not fetched_contents:
             context_str += "\nNo relevant online content or search results were available for analysis.\n"

        analysis_prompt = f"""You are an expert Manim Python developer tasked with diagnosing and solving an error.
Analyze the provided 'Original Manim Error' and any 'Relevant Search Results' or 'Fetched Full Content'.
Based *only* on the provided information, determine the most likely cause of the error and recommend the best solution or code fix.
Format your response strictly as a JSON object matching the following Pydantic schema:

```json
{ManimSolution.model_json_schema(indent=2)}
```

Provide specific code examples in the 'code_fix' field if applicable. If multiple solutions seem possible, choose the most likely one. If the provided content is insufficient or irrelevant, state that in the 'recommended_solution' and set confidence to 'Low'. Include the source URLs you primarily used for your analysis in the 'source_urls' field.

Context:
{context_str[:25000]}

JSON Output:
"""
        llm_response = llm_client.invoke(analysis_prompt)
        response_content = llm_response.content

        # 5. Parse and Validate LLM Analysis
        try:
            cleaned_response_text = response_content.strip().strip('```json').strip('```').strip()
            parsed_json = json.loads(cleaned_response_text)
            validated_data = ManimSolution(**parsed_json)
            # Add source URLs used for analysis to the validated data before returning
            validated_data_dict = validated_data.model_dump()
            validated_data_dict["source_urls"] = urls_to_fetch[:len(fetched_contents)] # Add URLs actually fetched
            final_result["analysis"] = validated_data_dict
            print("LLM analysis successful.")
        except (json.JSONDecodeError, ValidationError) as e:
            final_result["error"] = f"Failed to parse or validate LLM analysis: {e}. Response: {response_content[:500]}"
            print(final_result["error"])
        except Exception as e:
            final_result["error"] = f"Unexpected error processing LLM analysis: {e}. Response: {response_content[:500]}"
            print(final_result["error"])

    except Exception as e:
        final_result["error"] = f"An unexpected error occurred in the node: {e}"
        print(final_result["error"])

    # Return dictionary to update the state
    return {"error_analysis": final_result}

# Note: Removed the __main__ block as this is intended to be imported as a node.
