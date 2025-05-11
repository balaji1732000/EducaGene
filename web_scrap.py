import asyncio  
from crawl4ai import AsyncWebCrawler, LLMConfig, CacheMode  
from crawl4ai.async_configs import BrowserConfig, CrawlerRunConfig  
from crawl4ai.extraction_strategy import LLMExtractionStrategy  
from pydantic import BaseModel, Field  
from crawl4ai.utils import sanitize_input_encode
class OpenAIModelFee(BaseModel):  
    model_name: str = Field(..., description="Name of the OpenAI model.")  
    input_fee: str = Field(..., description="Fee for input token for the OpenAI model.")  
    output_fee: str = Field(..., description="Fee for output token for the OpenAI model.")  
  
async def main():  
    # Create proper LLMConfig object  
    llm_config = LLMConfig(  
        provider="gemini/gemini-2.0-flash",  
        api_token="AIzaSyAnpn1jOiPeu-Cuq-FRLknKEUjnMVrWPeY"  
    )  
      
    # Create extraction strategy with proper LLMConfig and encoding handling  
    extraction_strategy = LLMExtractionStrategy(  
        llm_config=llm_config,  
        schema=OpenAIModelFee.model_json_schema(),  
        extraction_type="schema",  
        instruction=r"""From the crawled content, extract all mentioned model names along with their fees for input and output tokens.   
        Do not miss any models in the entire content. One extracted model JSON format should look like this:   
        {"model_name": "GPT-4", "input_fee": "US$10.00 / 1M tokens", "output_fee": "US$30.00 / 1M tokens"}.""",  
        # Add these parameters to handle encoding issues  
         input_format="html",  # Use markdown instead of HTML to reduce encoding issues  
        apply_chunking=True,
        chunk_token_threshold=800,    # Smaller chunks for better handling  
        overlap_rate=0.1,      # Enable chunking to process content in smaller pieces  
        verbose=True              # Enable verbose logging to see what's happening  
    )  
      
    # Create a proper CrawlerRunConfig with encoding considerations  
    run_config = CrawlerRunConfig(  
        word_count_threshold=1, 
        parser_type="html5lib" , 
        extraction_strategy=extraction_strategy,  
        cache_mode=CacheMode.BYPASS,  
        # Add these parameters to help with encoding issues        # Force UTF-8 encoding  
        remove_overlay_elements=True,  # Remove potential problematic overlay elements  
        # charset="utf-8",  
    )  
      
    # Create browser config  
    browser_config = BrowserConfig(
        headless=True,  
        # default_navigation_timeout=30000  
    )  
      
    try:  
        # Use the context manager with proper configs  
        async with AsyncWebCrawler(config=browser_config) as crawler:  
            result = await crawler.arun(  
                url="https://openai.com/api/pricing/",  
                config=run_config  
            )
            
              
            if result.success:  
                print("Extraction successful!") 
                print(result) 
                print(result.extracted_content)  
                # Save the HTML content with UTF-8 encoding  
                html_file_path = "example_com.html"  
                with open(html_file_path, 'w', encoding='utf-8') as f:  
                    f.write(result.html)  
            
                print(f"Saved HTML content to {result.html}")  
            else:  
                print(f"Extraction failed: {result.error_message}")  
    except Exception as e:  
        print(f"Error during crawling: {str(e)}")  
  
if __name__ == "__main__":  
    asyncio.run(main())