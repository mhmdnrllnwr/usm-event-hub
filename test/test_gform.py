import httpx
from bs4 import BeautifulSoup
import sys
import asyncio

async def get_gform_title(url: str):
    # We use a User-Agent that looks like a social media crawler
    headers = {
        "User-Agent": "Mozilla/5.0 (compatible; Twitterbot/1.1; +https://dev.twitter.com/cards/optimize)"
    }
    
    print(f"\n--- Fetching: {url} ---")
    
    try:
        async with httpx.AsyncClient(follow_redirects=True) as client:
            response = await client.get(url, headers=headers, timeout=10.0)
            
            if response.status_code != 200:
                return f"Error: Received status code {response.status_code}"

            soup = BeautifulSoup(response.text, 'html.parser')
            
            # 1. Try Open Graph Title (Most reliable for Google Forms)
            og_title = soup.find("meta", property="og:title")
            if og_title and og_title.get("content"):
                return f"Success (OG): {og_title['content']}"

            # 2. Try Standard HTML Title (Backup)
            if soup.title:
                return f"Success (HTML): {soup.title.string}"

            return "Failed: No title found in metadata."

    except Exception as e:
        return f"Error: {str(e)}"

if __name__ == "__main__":
    print("--- Google Form Scraper ---")
    print("Press Ctrl+C to exit.")
    
    try:
        while True:
            # Get input inside the loop
            test_url = input("\nPaste your Google Form URL: ").strip()
            
            if not test_url:
                continue
                
            # Run the async function
            result = asyncio.run(get_gform_title(test_url))
            
            print("="*30)
            print(result)
            print("="*30)

    except KeyboardInterrupt:
        # Catch Ctrl+C to exit cleanly without a messy error dump
        print("\n\nExiting... Goodbye!")
        sys.exit(0)