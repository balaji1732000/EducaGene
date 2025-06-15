from duckduckgo_search import ddg  # DuckDuckGo search library

def search_error(state: dict) -> dict:
    """Searches DuckDuckGo for the error message in the state and stores results."""
    query = state.get("error_message") # Use .get for safety
    if not query:
        app.logger.warning("search_error_node: No error_message found in state to search for.")
        state["search_results"] = []
        return state

    app.logger.info(f"Searching web for error: {query[:100]}...") # Log truncated query

    try:
        # Perform DuckDuckGo search (max_results=5 for brevity)
        results = ddg(query, max_results=5)

        if not results:
            app.logger.info("No search results found.")
            state["search_results"] = []  # No results found
            return state

        # Optional: prioritize official docs and StackOverflow in results
        preferred_domains = ["stackoverflow.com", "learn.microsoft.com", "docs.", "github.com", "manim.community"] # Added manim docs
        def priority_score(url: str) -> int:
            # Check if url is not None before checking domain
            return 1 if url and any(domain in url for domain in preferred_domains) else 0

        # Sort results so that preferred domains come first
        # Filter out results with None href before sorting
        valid_results = [r for r in results if r.get("href")]
        valid_results.sort(key=lambda r: priority_score(r.get("href")), reverse=True)

        # Store the top results in state (title, URL, snippet)
        state["search_results"] = [
            {"title": res.get("title"), "url": res.get("href"), "snippet": res.get("body")}
            for res in valid_results # Use sorted and filtered results
        ]
        app.logger.info(f"Found {len(state['search_results'])} search results.")

    except Exception as e:
        app.logger.error(f"Error during DuckDuckGo search: {e}", exc_info=True)
        state["search_results"] = [] # Ensure search_results is empty on error
        # Optionally, store the search error itself
        state["search_error_message"] = f"Failed to perform web search: {e}"

    return state

# Example usage (for testing purposes)
if __name__ == '__main__':
    import logging
    # Configure basic logging for testing
    logging.basicConfig(level=logging.INFO)
    app = logging.getLogger(__name__) # Mock app logger for testing

    test_state_success = {"error_message": "manim TypeError: Expected all inputs for parameter mobjects to be a Mobjects"}
    result_state_success = search_error(test_state_success)
    print("--- Search Results (Success Case) ---")
    if result_state_success.get("search_results"):
        for i, res in enumerate(result_state_success["search_results"]):
            print(f"{i+1}. {res.get('title')}\n   {res.get('url')}\n   {res.get('snippet')[:100]}...")
    else:
        print("No results found or search failed.")
        if result_state_success.get("search_error_message"):
            print(f"Search Error: {result_state_success['search_error_message']}")

    print("\n--- Search Results (No Error Message Case) ---")
    test_state_no_error = {"some_other_key": "value"}
    result_state_no_error = search_error(test_state_no_error)
    if not result_state_no_error.get("search_results"):
         print("No search performed (as expected).")

    print("\n--- Search Results (Empty Error Message Case) ---")
    test_state_empty_error = {"error_message": ""}
    result_state_empty_error = search_error(test_state_empty_error)
    if not result_state_empty_error.get("search_results"):
         print("No search performed (as expected).")
