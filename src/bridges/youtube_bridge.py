"""
YouTube Automation Bridge
=========================
Uses Playwright to search and play YouTube videos.
Can connect to existing Chrome browser via CDP or launch a new one.
"""

from playwright.sync_api import sync_playwright, Page
import time
import re


class YouTubeBridge:
    """Bridge to automate YouTube search and playback"""
    
    def __init__(self, cdp_port: int = 9222):
        self.cdp_url = f"http://localhost:{cdp_port}"
        self.playwright = None
        self.browser = None
        self.page = None
    
    def connect(self) -> bool:
        """Connect to existing Chrome browser via CDP"""
        print(f"[*] [YouTube] Connecting to Chrome on {self.cdp_url}...")
        self.playwright = sync_playwright().start()
        
        try:
            self.browser = self.playwright.chromium.connect_over_cdp(self.cdp_url)
            ctx = self.browser.contexts[0]
            
            # Find existing YouTube page or create new
            youtube_page = None
            for p in ctx.pages:
                if "youtube.com" in p.url:
                    youtube_page = p
                    break
            
            if youtube_page:
                self.page = youtube_page
                print(f"[+] [YouTube] Found existing YouTube page")
            else:
                self.page = ctx.new_page()
                print(f"[+] [YouTube] Created new page")
            
            return True
            
        except Exception as e:
            print(f"[-] [YouTube] Connection failed: {e}")
            return False
    
    def launch(self, headless: bool = False) -> bool:
        """Launch a new browser instance"""
        print(f"[*] [YouTube] Launching browser...")
        self.playwright = sync_playwright().start()
        
        try:
            self.browser = self.playwright.chromium.launch(
                headless=headless,
                args=["--start-maximized"]
            )
            self.page = self.browser.new_page()
            print(f"[+] [YouTube] Browser launched")
            return True
        except Exception as e:
            print(f"[-] [YouTube] Launch failed: {e}")
            return False
    
    def close(self):
        """Close the browser"""
        if self.browser:
            self.browser.close()
        if self.playwright:
            self.playwright.stop()
    
    def search(self, query: str) -> bool:
        """Search for videos on YouTube"""
        if not self.page:
            return False
        
        print(f"[*] [YouTube] Searching for: {query}")
        
        try:
            # Navigate to YouTube if not already there
            if "youtube.com" not in self.page.url:
                self.page.goto("https://www.youtube.com", wait_until="domcontentloaded")
                time.sleep(2)
            
            # Find and click search box
            search_box = self.page.locator('input#search')
            search_box.click()
            time.sleep(0.5)
            
            # Clear and type search query
            search_box.fill(query)
            time.sleep(0.3)
            
            # Click search button or press Enter
            self.page.keyboard.press("Enter")
            time.sleep(2)
            
            print(f"[+] [YouTube] Search completed for: {query}")
            return True
            
        except Exception as e:
            print(f"[-] [YouTube] Search failed: {e}")
            return False
    
    def play_first_video(self) -> dict:
        """Click on the first video in search results"""
        if not self.page:
            return {"success": False, "error": "No page"}
        
        print(f"[*] [YouTube] Playing first video...")
        
        try:
            # Wait for search results
            time.sleep(1)
            
            # Find first video in results (multiple selectors for different layouts)
            selectors = [
                'ytd-video-renderer a#video-title',
                'ytd-video-renderer a#thumbnail',
                'a.ytd-video-renderer',
                '#contents ytd-video-renderer:first-child a#thumbnail',
                'ytd-video-renderer:first-child #video-title'
            ]
            
            video_link = None
            for selector in selectors:
                try:
                    element = self.page.locator(selector).first
                    if element.is_visible():
                        video_link = element
                        break
                except:
                    continue
            
            if not video_link:
                return {"success": False, "error": "No video found in results"}
            
            # Get video title before clicking
            title = ""
            try:
                title_el = self.page.locator('ytd-video-renderer #video-title').first
                title = title_el.get_attribute("title") or title_el.inner_text()
            except:
                pass
            
            # Click to play
            video_link.click()
            time.sleep(2)
            
            print(f"[+] [YouTube] Playing: {title[:50]}...")
            return {"success": True, "title": title, "url": self.page.url}
            
        except Exception as e:
            print(f"[-] [YouTube] Play failed: {e}")
            return {"success": False, "error": str(e)}
    
    def search_and_play(self, query: str) -> dict:
        """Search for a video and play the first result"""
        if not self.search(query):
            return {"success": False, "error": "Search failed"}
        
        return self.play_first_video()
    
    def pause(self) -> bool:
        """Pause the current video"""
        if not self.page:
            return False
        
        try:
            # Press K to toggle play/pause (YouTube shortcut)
            self.page.keyboard.press("k")
            return True
        except:
            return False
    
    def skip_forward(self, seconds: int = 10) -> bool:
        """Skip forward in the video"""
        if not self.page:
            return False
        
        try:
            # Press L to skip forward 10 seconds (YouTube shortcut)
            for _ in range(seconds // 10):
                self.page.keyboard.press("l")
                time.sleep(0.1)
            return True
        except:
            return False
    
    def skip_backward(self, seconds: int = 10) -> bool:
        """Skip backward in the video"""
        if not self.page:
            return False
        
        try:
            # Press J to skip backward 10 seconds (YouTube shortcut)
            for _ in range(seconds // 10):
                self.page.keyboard.press("j")
                time.sleep(0.1)
            return True
        except:
            return False
    
    def fullscreen(self) -> bool:
        """Toggle fullscreen mode"""
        if not self.page:
            return False
        
        try:
            self.page.keyboard.press("f")
            return True
        except:
            return False
    
    def mute(self) -> bool:
        """Toggle mute"""
        if not self.page:
            return False
        
        try:
            self.page.keyboard.press("m")
            return True
        except:
            return False
    
    def get_video_info(self) -> dict:
        """Get info about the currently playing video"""
        if not self.page:
            return {}
        
        try:
            info = self.page.evaluate("""
                () => {
                    const video = document.querySelector('video');
                    const title = document.querySelector('h1.ytd-video-primary-info-renderer, h1.ytd-watch-metadata');
                    return {
                        title: title ? title.innerText : '',
                        duration: video ? video.duration : 0,
                        currentTime: video ? video.currentTime : 0,
                        paused: video ? video.paused : true,
                        url: window.location.href
                    };
                }
            """)
            return info
        except:
            return {}


def search_and_play_youtube(query: str, use_cdp: bool = True, cdp_port: int = 9222) -> dict:
    """
    Standalone function to search and play a YouTube video.
    
    Args:
        query: Search query for YouTube
        use_cdp: If True, connect to existing Chrome; if False, launch new browser
        cdp_port: CDP port for existing Chrome
    
    Returns:
        dict with success status, title, and url
    """
    bridge = YouTubeBridge(cdp_port=cdp_port)
    
    try:
        if use_cdp:
            if not bridge.connect():
                # Try launching new browser if CDP fails
                if not bridge.launch():
                    return {"success": False, "error": "Could not connect to or launch browser"}
        else:
            if not bridge.launch():
                return {"success": False, "error": "Could not launch browser"}
        
        result = bridge.search_and_play(query)
        # Don't close if using CDP - keep connected
        if not use_cdp:
            # Keep browser open for playback
            pass
        
        return result
        
    except Exception as e:
        return {"success": False, "error": str(e)}


# Test
if __name__ == "__main__":
    import sys
    
    query = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else "lofi hip hop music"
    print(f"\n🎵 Searching YouTube for: {query}\n")
    
    result = search_and_play_youtube(query, use_cdp=False)
    
    if result.get("success"):
        print(f"\n✅ Now playing: {result.get('title', 'Unknown')}")
        print(f"   URL: {result.get('url', '')}")
        print("\n   Controls: K=pause, L=forward, J=back, F=fullscreen, M=mute")
    else:
        print(f"\n❌ Failed: {result.get('error')}")
