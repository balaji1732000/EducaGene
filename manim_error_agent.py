"""
manim_error_agent.py
====================

An agent designed to find the best solution for Manim Python errors:
1. Accepts a Manim error message.
2. Searches DuckDuckGo, prioritizing relevant sources.
3. Fetches content from top results using requests/BeautifulSoup.
4. Uses an LLM to analyze the error and fetched content to find the best solution.
5. Returns a structured analysis.

───────────────────────────────────────────────────────────────────────────────
Setup
-----
pip install requests beautifulsoup4 langchain-openai langchain-community python-dotenv pydantic duckduckgo-search
# Ensure AZURE_OPENAI_API_KEY, ENDPOINT_URL, AZURE_DEPLOYMENT are set in .env
───────────────────────────────────────────────────────────────────────────────
Usage
-----
python manim_error_agent.py "Your Manim Error Message Here"
# or run `python manim_error_agent.py` and paste the error when prompted
"""

import os
import json
import sys
import requests
from bs4 import BeautifulSoup
from langchain_openai import AzureChatOpenAI
# Removed DuckDuckGoSearchRun tool import, will use the library directly
# from langchain_community.tools import DuckDuckGoSearchRun
from duckduckgo_search import DDGS # Ensure DDGS is imported
from dotenv import load_dotenv
import warnings
from pydantic import BaseModel, Field, ValidationError
from typing import List, Optional, Dict, Any

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

# --- Tool for Fetching and Parsing Web Content ---
def fetch_and_parse(url: str) -> Dict[str, Any]:
    """Fetches URL content and returns text or error."""
    print(f"Fetching: {url}...")
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3"}
    try:
        response = requests.get(url, headers=headers, timeout=20)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'html.parser')
        # Focus on potentially relevant parts, fallback to body
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

# --- Core Agent Logic ---
def find_manim_solution(error_message: str) -> Dict[str, Any]:
    """
    Searches, fetches, and analyzes content to find a solution for a Manim error.
    """
    final_result = {"error_message": error_message, "analysis": None, "error": None}

    try:
        # 1. Initialize LLM
        llm_client = AzureChatOpenAI(
            azure_endpoint=os.getenv('ENDPOINT_URL'),
            api_key=os.getenv('AZURE_OPENAI_API_KEY'),
            api_version=os.getenv('AZURE_API_VERSION', '2024-02-01'), # Use env var or default
            azure_deployment="gpt-4.1-mini", # Use env var or default gpt-4o
            temperature=0.1, # Low temp for factual extraction
            max_tokens=32000 # Removed duplicate line
        )

        # 2. Search directly using duckduckgo-search library
        print("Searching for relevant pages using DDGS...")
        search_results = []
        urls_to_fetch = []
        try:
            # Extract a concise query for the search engine
            error_lines = [line.strip() for line in error_message.strip().split('\n') if line.strip()]
            # Try to find the main error line, otherwise use the first few lines
            concise_error = next((line for line in error_lines if 'Error:' in line or 'Exception:' in line), None)
            if not concise_error:
                concise_error = " ".join(error_lines[:3]) # Use first 3 lines as fallback
            
            search_query = f"manim python error {concise_error}" # Use the concise version for search
            print(f"Using concise search query: {search_query}")

            with DDGS(timeout=20) as ddgs: # Added timeout
                # Use .text() method with the concise query
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
            for url in urls_to_fetch[:3]: # Fetch top 3
                 fetched_contents.append(fetch_and_parse(url))
        else:
            print("No URLs found from search to fetch.")


        # 4. Analyze with LLM
        print("Analyzing content with LLM...")
        context_str = f"Original Manim Error:\n```\n{error_message}\n```\n\n"
        if fetched_contents:
            context_str += "Relevant Content Found Online:\n"
            for i, content in enumerate(fetched_contents):
                if content["text"]:
                    context_str += f"\n--- Source {i+1} ({content['url']}) ---\n"
                    context_str += content["text"][:5000] # Limit context per source
                    context_str += "\n--- End Source {i+1} ---\n"
                elif content["error"]:
                     context_str += f"\n--- Source {i+1} ({content['url']}) ---\n"
                     context_str += f"Error fetching content: {content['error']}"
                     context_str += "\n--- End Source {i+1} ---\n"
        # Removed fallback condition referencing undefined 'search_results_str'
        # elif search_results_str: ...

        analysis_prompt = f"""You are an expert Manim Python developer tasked with diagnosing and solving an error.
Analyze the provided 'Original Manim Error' and the 'Relevant Content Found Online' (if any).
Based *only* on the provided information, determine the most likely cause of the error and recommend the best solution or code fix.
Format your response strictly as a JSON object matching the following Pydantic schema:

```json
{ManimSolution.model_json_schema()}
```
Provide specific code examples in the 'code_fix' field if applicable. If multiple solutions seem possible, choose the most likely one. If the provided content is insufficient or irrelevant, state that in the 'recommended_solution' and set confidence to 'Low'.

{context_str[:25000]} 

JSON Output:
"""
        # Limit total context size

        llm_response = llm_client.invoke(analysis_prompt)
        response_content = llm_response.content

        # 5. Parse and Validate LLM Analysis
        try:
            cleaned_response_text = response_content.strip().strip('```json').strip('```').strip()
            parsed_json = json.loads(cleaned_response_text)
            validated_data = ManimSolution(**parsed_json)
            final_result["analysis"] = validated_data.model_dump()
            print("LLM analysis successful.")
        except (json.JSONDecodeError, ValidationError) as e:
            final_result["error"] = f"Failed to parse or validate LLM analysis: {e}. Response: {response_content[:500]}"
            print(final_result["error"])
        except Exception as e:
            final_result["error"] = f"Unexpected error processing LLM analysis: {e}. Response: {response_content[:500]}"
            print(final_result["error"])

    except Exception as e:
        final_result["error"] = f"An unexpected error occurred in the agent: {e}"
        print(final_result["error"])

    return final_result

# ──────────────────────────────────────────────────────────────────────────────
# Command‑line entry‑point
# ──────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    error_input = ""
    if len(sys.argv) > 1:
        error_input = " ".join(sys.argv[1:]).strip()

    if not error_input:
        error_input = """
`from manim import *

class HelloLaTeX(Scene):
def construct(self):
tex = Tex(r"\LaTeX", font_size=144)
self.add(tex)`

this is the error:
ValueError: latex error converting to dvi. See log output above or the log
file: media\Tex\07fd8c4c1d6550a5.log
[6700] Execution returned code=1 in 74.809 seconds returned signal null
"""


    if not error_input:
        print("Error: No error message provided.")
        sys.exit(1)

    # Run the analysis
    solution_result = find_manim_solution(error_input)

    # Print the final result
    print("\n--- Manim Error Analysis Result ---")
    print(json.dumps(solution_result, indent=2, ensure_ascii=False))
