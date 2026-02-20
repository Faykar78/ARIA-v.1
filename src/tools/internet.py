
try:
    from src.tools.google_browser import search_google_browser
except ImportError:
    try:
        from google_browser import search_google_browser
    except ImportError:
        # Fallback for when running directly inside src/tools
        import sys
        import os
        sys.path.append(os.path.dirname(__file__))
        from google_browser import search_google_browser

def search_web(query, max_results=5):
    """
    Performs a web search using the persistent headless browser to bypass CAPTCHAs.
    """
    return search_google_browser(query, max_results=max_results)

if __name__ == "__main__":
    print(search_web("current time in india"))
