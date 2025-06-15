
import os 
import requests
from bs4 import BeautifulSoup
from langchain_openai import AzureChatOpenAI
from langchain.agents import initialize_agent, AgentType, Tool, AgentExecutor
import json # Import json
from langchain_community.tools import DuckDuckGoSearchRun
from dotenv import load_dotenv
import warnings
from pydantic import BaseModel, Field, ValidationError # Import Pydantic
from typing import List, Optional, Dict, Any # Import typing helpers

load_dotenv()

warnings.filterwarnings('ignore')

# --- Define Pydantic Models ---
class OpenAIModelFee(BaseModel):
    model_name: str = Field(..., description="Name of the OpenAI model.")
    input_fee: str = Field(..., description="Fee for input token for the OpenAI model.")
    output_fee: str = Field(..., description="Fee for output token for the OpenAI model.")

class ExtractedData(BaseModel):
     extracted_fees: List[OpenAIModelFee] = Field(..., description="List of extracted model fees.")

class EnchanceWebScraperTool:
    def __init__(self, llm: AzureChatOpenAI): # Accept LLM client
        self.name = "WebScraperExtractor" # Changed name slightly
        self.description = "Fetches content from a website URL, extracts OpenAI model pricing information (model_name, input_fee, output_fee), and returns it as structured JSON data. Input must be a valid URL."
        self.llm = llm # Store LLM client

    def run(self, url: str) -> str: # Return type is string (JSON or error message)
        # Check if the URL is valid
        if not url.startswith("http://") and not url.startswith("https://"):
            return json.dumps({"error": "Invalid URL. Please provide a valid URL starting with http:// or https://."})

        try:
            # 1. Fetch HTML
            headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3"}
            response = requests.get(headers=headers, url=url, timeout=30) # Increased timeout
            response.raise_for_status()
            html_content = response.text

            # 2. Parse HTML and Extract Text
            soup = BeautifulSoup(html_content, 'html.parser')
            main_content = soup.find('main') or soup.find('article') or soup.find('body')
            text_content = main_content.get_text(separator=' ', strip=True) if main_content else soup.get_text(separator=' ', strip=True)

            if not text_content:
                 return json.dumps({"error": "Could not extract text content from the page."})

            print(f"Tool: Extracted text length: {len(text_content)}. Sending to LLM for extraction...")

            # 3. Prepare Prompt for LLM Extraction
            extraction_prompt = f"""Analyze the following text content extracted from {url}.
Identify all mentions of OpenAI model names along with their pricing for input and output tokens.
Extract this information and format it strictly as a JSON object matching the following Pydantic schema:

```json
{ExtractedData.model_json_schema(indent=2)}
```

Ensure the output is a single, valid JSON object containing a key 'extracted_fees' which holds a list of objects, each matching the 'OpenAIModelFee' schema.
If no model pricing information is found, return a JSON object with an empty list: {{"extracted_fees": []}}.

Text Content:
--- START TEXT ---
{text_content[:20000]}
--- END TEXT ---

JSON Output:
"""
            # Limit text size further if needed

            # 4. Call LLM
            llm_response = self.llm.invoke(extraction_prompt) # Use the passed LLM client
            response_content = llm_response.content

            # 5. Parse and Validate Response
            try:
                # Clean the response text
                cleaned_response_text = response_content.strip().strip('```json').strip('```').strip()
                parsed_json = json.loads(cleaned_response_text)
                # Validate against Pydantic schema
                validated_data = ExtractedData(**parsed_json)
                print("Tool: LLM extraction successful and validated.")
                # Return the validated data as a JSON string
                print(validated_data.model_dump_json(indent=2))
                return validated_data.model_dump_json(indent=2)
            except json.JSONDecodeError as e:
                error_msg = f"Tool Error: Failed to parse LLM response as JSON: {e}. Response text: {response_content[:500]}"
                print(error_msg)
                return json.dumps({"error": error_msg})
            except ValidationError as e:
                error_msg = f"Tool Error: LLM response failed Pydantic validation: {e}. Response text: {response_content[:500]}"
                print(error_msg)
                return json.dumps({"error": error_msg, "raw_response": parsed_json if 'parsed_json' in locals() else cleaned_response_text})
            except Exception as e:
                 error_msg = f"Tool Error: Error processing LLM response: {e}. Response text: {response_content[:500]}"
                 print(error_msg)
                 return json.dumps({"error": error_msg})

        except requests.exceptions.RequestException as e:
            return json.dumps({"error": f"Error fetching the URL: {e}"})
        except Exception as e:
            return json.dumps({"error": f"An unexpected error occurred in the tool: {e}"})

def initialize_web_agent(temp, max_iteration, modal_name):


    llm_client =  AzureChatOpenAI(
        azure_endpoint=os.getenv('ENDPOINT_URL'),
        api_key=os.getenv('AZURE_OPENAI_API_KEY'),
        api_version='2024-12-01-preview',
        azure_deployment="gpt-4.1-mini",
        # azure_deployment=os.getenv("AZURE_DEPLOYMENT", "gpt-4.1-mini"), # Use env var or default
        # max_completion_tokens=32768, # Setting temperature might be more relevant for agent
        temperature=temp if temp is not None else 0.7 # Use passed temp or default
    )

    agent_type = AgentType.ZERO_SHOT_REACT_DESCRIPTION # Or potentially STRUCTURED_CHAT_ZERO_SHOT_REACT_DESCRIPTION

    search_tool = DuckDuckGoSearchRun()

    # Initialize the tool, passing the LLM client
    web_scrape_tool = EnchanceWebScraperTool(llm=llm_client)

    # Define tools list
    tools = [
        Tool(name="Search", func=search_tool.run, description="Search the web for general information or recent events. Input is a search query."),
        # Updated tool description and name to match the class
        Tool(name=web_scrape_tool.name, func=web_scrape_tool.run, description=web_scrape_tool.description),
    ]

    # Initialize the agent executor
    # Note: structure_output=True might not be needed or supported depending on agent type/version
    agent_executor = initialize_agent(
        tools=tools,
        llm=llm_client,
        agent=agent_type, # Use agent= instead of agent_type=
        verbose=True,
        max_iterations=max_iteration if max_iteration is not None else 3, # Use passed max_iteration
        return_intermediate_steps=True,
        handle_parsing_errors=True,
        early_stopping_method="generate",
    )
    return agent_executor # Return the initialized agent executor

if __name__ == "__main__":
    # Example usage: Initialize and run the agent
    # Note: The initialize_web_agent function needs parameters passed or defaults set
    # Using placeholder values for demonstration
    agent_executor = initialize_web_agent(temp=0.7, max_iteration=3, modal_name="gpt-4.1-mini")

    # Example query for the agent
    query = " help me resolve this Error: error in crawl4ai 'charmap' codec can't decode byte 0x81 in position 1980: character maps to <undefined>"
    print(f"Running agent with query: {query}")

    try:
        # Run the agent
        # Note: Langchain's agent execution might be synchronous or asynchronous depending on version/setup
        # Using agent_executor.run for simplicity, adjust if using agent_executor.arun
        result = agent_executor.invoke(query)
        print("\nAgent Result:")
        print(result)
    except Exception as e:
        print(f"Agent execution failed: {e}")

    # --- Original tool test code (commented out) ---
    # url = "https://openai.com/api/pricing/"
    # web_scraper = EnchanceWebScraperTool()
    # result = web_scraper.run(url)
    # print(result)
