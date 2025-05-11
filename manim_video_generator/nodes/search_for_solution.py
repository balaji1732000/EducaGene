"""
Node: search_for_solution
=========================

Searches the web for potential solutions to a Manim rendering error.
1. Takes a render error message from the state.
2. Searches DuckDuckGo using a concise query derived from the error.
3. Fetches content from the top relevant URLs.
4. Compiles search snippets and fetched text into 'solution_hints'.
5. Updates the state with these hints for the script generation node.
"""

import os
import json
import sys
import requests
from bs4 import BeautifulSoup
from duckduckgo_search import DDGS
from dotenv import load_dotenv
import warnings
from typing import List, Optional, Dict, Any

# Assuming state schema is defined in ../state.py
# from ..state import ManimWorkflowState # Adjust import path if needed

# Load environment variables
load_dotenv()
warnings.filterwarnings('ignore')

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
# def search_for_solution_node(state: ManimWorkflowState) -> Dict[str, Any]: # Use this signature when integrated
def search_for_solution_node(state: dict) -> Dict[str, Any]: # Using dict for now
    """
    LangGraph node to search web for solutions to a Manim render error.
    """
    print("--- Node: search_for_solution ---")
    # Access state attributes directly using dot notation
    error_message = state.render_error if hasattr(state, 'render_error') else ""
    if not error_message or not isinstance(error_message, str):
        print("No valid render error message found in state.")
        # Use the correct key for the return dictionary
        return {"error_search_context": None, "search_error": "No valid error message provided in state."}

    search_error = None
    solution_hints = "No specific solution hints found from web search." # Default message

    try:
        # 1. Search directly using duckduckgo-search library
        print("Searching for relevant pages using DDGS...")
        search_results = []
        urls_to_fetch = []
        try:
            # Extract a concise query for the search engine
            error_lines = [line.strip() for line in error_message.strip().split('\n') if line.strip()]
            concise_error = next((line for line in error_lines if 'Error:' in line or 'Exception:' in line), None)
            if not concise_error:
                concise_error = " ".join(error_lines[:3]) # Use first 3 lines

            search_query = f"manim python error {concise_error}"
            print(f"Using concise search query: {search_query}")

            with DDGS(timeout=20) as ddgs:
                search_results = list(ddgs.text(search_query, max_results=5, region='wt-wt', safesearch='off', timelimit='y'))
                urls_to_fetch = [r['href'] for r in search_results if r.get('href')]
                print(f"Found {len(search_results)} results. Top URLs: {urls_to_fetch[:3]}")
        except Exception as e:
            print(f"DDGS search failed: {e}")
            search_error = f"DDGS search failed: {e}"
            # Continue without fetched content if search fails

        # 2. Fetch content from top URLs
        fetched_contents = []
        if urls_to_fetch:
            print(f"Fetching content from top {min(len(urls_to_fetch), 3)} URLs...")
            for url in urls_to_fetch[:3]:
                 fetched_contents.append(_fetch_and_parse(url))
        else:
            print("No URLs found from search to fetch.")

        # 3. Compile Solution Hints
        hints_str = ""
        # Include search result snippets first
        if search_results:
             hints_str += "Relevant Search Results (Snippets):\n"
             for i, res in enumerate(search_results[:3]):
                 hints_str += f"\n--- Search Result {i+1} ({res.get('href', 'N/A')}) ---\n"
                 hints_str += f"Title: {res.get('title', 'N/A')}\n"
                 hints_str += f"Snippet: {res.get('body', 'N/A')}\n"
                 hints_str += "--- End Search Result {i+1} ---\n"

        # Include fetched full content if available
        if fetched_contents:
            hints_str += "\nFetched Full Content from URLs:\n"
            for i, content in enumerate(fetched_contents):
                if content["text"]:
                    hints_str += f"\n--- Fetched Source {i+1} ({content['url']}) ---\n"
                    hints_str += content["text"][:15000] # Limit context per source
                    hints_str += "\n--- End Fetched Source {i+1} ---\n"
                elif content["error"]:
                     hints_str += f"\n--- Fetched Source {i+1} ({content['url']}) ---\n"
                     hints_str += f"Error fetching content: {content['error']}"
                     hints_str += "\n--- End Fetched Source {i+1} ---\n"

        if hints_str:
            solution_hints = hints_str.strip()
        elif search_error: # If search failed, report that
             solution_hints = f"Search failed: {search_error}. Unable to provide web context."

    except Exception as e:
        print(f"An unexpected error occurred in search_for_solution node: {e}")
        search_error = f"An unexpected error occurred: {e}"
        solution_hints = f"Failed to get solution hints due to error: {e}"

    # Return dictionary to update the state using the correct key
    return {"error_search_context": solution_hints, "search_error": search_error}
