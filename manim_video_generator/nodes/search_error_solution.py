import json
from typing import Dict, Any, List

from manim_video_generator.config import app
from manim_video_generator.state import WorkflowState

# This node will be responsible for calling the Tavily search tool
# We need to define the function signature expected by LangGraph
# It takes the current state and should return a dictionary with updates to the state.

def search_error_solution_node(state: WorkflowState) -> Dict[str, Any]:
    """
    Uses Tavily search to find potential solutions for a Manim render error.
    Stores the formatted search results in the state.
    """
    app.logger.info("--- search_error_solution_node ---")
    render_error = state.rendering_error

    if not render_error:
        app.logger.warning("No render error found in state to search for.")
        return {"error_search_context": None} # No error, nothing to search

    # Extract a concise query from the error message (e.g., the error type and key details)
    # This might need refinement based on typical Manim error formats
    error_lines = render_error.strip().split('\n')
    last_line = error_lines[-1] if error_lines else "" # Often contains the specific error type
    query = f"Manim Community v0.19.0 error fix: {last_line}"
    # Limit query length if necessary
    query = query[:500] # Tavily might have query limits

    app.logger.info(f"Constructed Tavily search query: {query}")

    # NOTE: This node *cannot* directly call the tool.
    # It needs to return the *request* to call the tool.
    # The actual tool call and result handling will happen outside this node function
    # by the LangGraph framework or the orchestrator based on the MCP protocol.
    # For now, we'll simulate returning the search context as if the tool was called.
    # In a real MCP integration, this node would likely just return the query or tool call request.

    # --- Placeholder for Tool Call ---
    # In a real scenario, the orchestrator would see this node wants to use Tavily,
    # execute the search, and the result would be fed back into the state before
    # the next node runs. We simulate this by setting a placeholder context.
    # Replace this simulation when MCP tool integration is fully implemented.

    simulated_search_results = [
        {"title": "Manim ImportError Fix", "url": "https://example.com/manim-import-fix", "content": "Make sure to import directly from 'manim' for common classes like ParametricSurface..."},
        {"title": "Debugging NameError in Manim", "url": "https://example.com/manim-nameerror", "content": "Check spelling and ensure the object is defined before use..."},
        {"title": "Manim Community Docs - Imports", "url": "https://docs.manim.community/en/stable/reference/manim.html", "content": "Manim Community v0.19.0 ... common classes are available directly..."}
    ]
    formatted_context = "Web Search Results for Error:\n\n"
    for i, result in enumerate(simulated_search_results[:3]): # Limit to top 3 results
        formatted_context += f"{i+1}. Title: {result.get('title', 'N/A')}\n"
        formatted_context += f"   URL: {result.get('url', 'N/A')}\n"
        formatted_context += f"   Snippet: {result.get('content', 'N/A')[:150]}...\n\n" # Limit snippet length

    app.logger.info("Simulated Tavily search and formatted results.")
    # --- End Placeholder ---

    # Return the formatted context to be stored in the state
    # In a real MCP setup, the state update might happen differently based on tool result handling
    return {"error_search_context": formatted_context.strip()}
