
from googlesearch import search
import time

def test_google():
    print("[*] Testing googlesearch-python with pause...")
    try:
        # standard call
        results = search("current time in london", num_results=5, advanced=True, sleep_interval=2)
        count = 0
        for r in results:
            print(f"Title: {r.title}")
            print(f"Desc: {r.description}")
            print(f"URL: {r.url}")
            print("-" * 20)
            count += 1
            
        print(f"Total: {count}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_google()
