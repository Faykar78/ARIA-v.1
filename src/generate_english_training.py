#!/usr/bin/env python3
"""
Generate English training examples for OmniParser format.
Creates synthetic examples that match how brain.py formats UI elements.
"""

import json
import os

OUTPUT_FILE = "training_data/osworld_training.jsonl"

# Comprehensive synthetic training examples in OmniParser format
TRAINING_EXAMPLES = [
    # === CLICK ACTIONS ===
    {
        "instruction": "Click the Submit button",
        "input": 'Active Window: Form. Visible Elements: [{"id": 0, "type": "text_input", "text": "Name", "center": "(300,200)"}, {"id": 1, "type": "text_input", "text": "Email", "center": "(300,250)"}, {"id": 2, "type": "button", "text": "Submit", "center": "(350,320)"}, {"id": 3, "type": "button", "text": "Cancel", "center": "(450,320)"}]',
        "output": '{"action": "click", "target_id": 2, "x": 350, "y": 320, "reason": "Submit button matches user goal"}'
    },
    {
        "instruction": "Click on Cancel",
        "input": 'Active Window: Dialog. Visible Elements: [{"id": 0, "type": "button", "text": "OK", "center": "(400,300)"}, {"id": 1, "type": "button", "text": "Cancel", "center": "(500,300)"}]',
        "output": '{"action": "click", "target_id": 1, "x": 500, "y": 300, "reason": "Cancel button to dismiss dialog"}'
    },
    {
        "instruction": "Open Chrome browser", 
        "input": 'Active Window: Ubuntu Desktop. Visible Elements: [{"id": 0, "type": "icon", "text": "Files", "center": "(50,100)"}, {"id": 1, "type": "icon", "text": "Chrome", "center": "(50,150)"}, {"id": 2, "type": "icon", "text": "Terminal", "center": "(50,200)"}]',
        "output": '{"action": "click", "target_id": 1, "x": 50, "y": 150, "reason": "Chrome icon to open browser"}'
    },
    {
        "instruction": "Click the search box",
        "input": 'Active Window: Google Chrome. Visible Elements: [{"id": 0, "type": "text_input", "text": "Search or type a URL", "center": "(500,60)"}, {"id": 1, "type": "button", "text": "Google Search", "center": "(500,120)"}]',
        "output": '{"action": "click", "target_id": 0, "x": 500, "y": 60, "reason": "Focus search box for typing"}'
    },
    {
        "instruction": "Close the popup",
        "input": 'Active Window: Popup Dialog. Visible Elements: [{"id": 0, "type": "button", "text": "X", "center": "(700,100)"}, {"id": 1, "type": "text", "text": "Subscribe to newsletter", "center": "(500,200)"}, {"id": 2, "type": "button", "text": "Subscribe", "center": "(500,300)"}]',
        "output": '{"action": "click", "target_id": 0, "x": 700, "y": 100, "reason": "X button closes popup"}'
    },
    {
        "instruction": "Click Format menu",
        "input": 'Active Window: LibreOffice Writer. Visible Elements: [{"id": 0, "type": "menu", "text": "File", "center": "(40,30)"}, {"id": 1, "type": "menu", "text": "Edit", "center": "(80,30)"}, {"id": 2, "type": "menu", "text": "View", "center": "(120,30)"}, {"id": 3, "type": "menu", "text": "Format", "center": "(170,30)"}]',
        "output": '{"action": "click", "target_id": 3, "x": 170, "y": 30, "reason": "Open Format menu"}'
    },
    {
        "instruction": "Click File menu",
        "input": 'Active Window: Text Editor. Visible Elements: [{"id": 0, "type": "menu", "text": "File", "center": "(30,25)"}, {"id": 1, "type": "menu", "text": "Edit", "center": "(70,25)"}, {"id": 2, "type": "menu", "text": "Help", "center": "(110,25)"}]',
        "output": '{"action": "click", "target_id": 0, "x": 30, "y": 25, "reason": "Open File menu"}'
    },
    {
        "instruction": "Click the login button",
        "input": 'Active Window: Login Page. Visible Elements: [{"id": 0, "type": "text_input", "text": "Username", "center": "(400,200)"}, {"id": 1, "type": "text_input", "text": "Password", "center": "(400,250)"}, {"id": 2, "type": "button", "text": "Login", "center": "(400,300)"}, {"id": 3, "type": "link", "text": "Forgot password?", "center": "(400,340)"}]',
        "output": '{"action": "click", "target_id": 2, "x": 400, "y": 300, "reason": "Login button to submit credentials"}'
    },
    {
        "instruction": "Open Terminal",
        "input": 'Active Window: Ubuntu Desktop. Visible Elements: [{"id": 0, "type": "icon", "text": "Files", "center": "(50,100)"}, {"id": 1, "type": "icon", "text": "Firefox", "center": "(50,150)"}, {"id": 2, "type": "icon", "text": "Terminal", "center": "(50,200)"}, {"id": 3, "type": "icon", "text": "Settings", "center": "(50,250)"}]',
        "output": '{"action": "click", "target_id": 2, "x": 50, "y": 200, "reason": "Terminal icon"}'
    },
    {
        "instruction": "Click the next button",
        "input": 'Active Window: Wizard. Visible Elements: [{"id": 0, "type": "button", "text": "Back", "center": "(300,400)"}, {"id": 1, "type": "button", "text": "Next", "center": "(400,400)"}, {"id": 2, "type": "button", "text": "Cancel", "center": "(500,400)"}]',
        "output": '{"action": "click", "target_id": 1, "x": 400, "y": 400, "reason": "Next button to proceed"}'
    },
    
    # === TYPE ACTIONS ===
    {
        "instruction": "Type hello world",
        "input": 'Active Window: Text Editor. Visible Elements: [{"id": 0, "type": "text_area", "text": "", "center": "(400,300)"}]',
        "output": '{"action": "type", "text": "hello world", "reason": "Type the requested text"}'
    },
    {
        "instruction": "Enter my email address test@example.com",
        "input": 'Active Window: Form. Visible Elements: [{"id": 0, "type": "text_input", "text": "Email", "center": "(400,200)"}, {"id": 1, "type": "button", "text": "Submit", "center": "(400,250)"}]',
        "output": '{"action": "type", "text": "test@example.com", "reason": "Enter email in form"}'
    },
    {
        "instruction": "Search for python tutorial",
        "input": 'Active Window: Google. Visible Elements: [{"id": 0, "type": "text_input", "text": "Search", "center": "(500,300)"}, {"id": 1, "type": "button", "text": "Google Search", "center": "(450,400)"}]',
        "output": '{"action": "type", "text": "python tutorial", "reason": "Type search query"}'
    },
    {
        "instruction": "Type the filename report.pdf",
        "input": 'Active Window: Save As Dialog. Visible Elements: [{"id": 0, "type": "text_input", "text": "File name:", "center": "(400,300)"}, {"id": 1, "type": "button", "text": "Save", "center": "(500,400)"}]',
        "output": '{"action": "type", "text": "report.pdf", "reason": "Enter filename"}'
    },
    
    # === HOTKEY ACTIONS ===
    {
        "instruction": "Select all text",
        "input": 'Active Window: Text Editor. Visible Elements: [{"id": 0, "type": "text_area", "text": "Document content here...", "center": "(400,300)"}]',
        "output": '{"action": "hotkey", "key": "ctrl+a", "reason": "Select all text with keyboard shortcut"}'
    },
    {
        "instruction": "Save the document",
        "input": 'Active Window: Document Editor. Visible Elements: [{"id": 0, "type": "menu", "text": "File", "center": "(40,30)"}, {"id": 1, "type": "toolbar_button", "text": "Save", "center": "(60,70)"}]',
        "output": '{"action": "hotkey", "key": "ctrl+s", "reason": "Save with keyboard shortcut"}'
    },
    {
        "instruction": "Copy the selected text",
        "input": 'Active Window: Editor. Visible Elements: [{"id": 0, "type": "text_area", "text": "Selected text here", "center": "(400,300)"}]',
        "output": '{"action": "hotkey", "key": "ctrl+c", "reason": "Copy selected text"}'
    },
    {
        "instruction": "Paste",
        "input": 'Active Window: Editor. Visible Elements: [{"id": 0, "type": "text_area", "text": "", "center": "(400,300)"}]',
        "output": '{"action": "hotkey", "key": "ctrl+v", "reason": "Paste from clipboard"}'
    },
    {
        "instruction": "Undo the last action",
        "input": 'Active Window: Editor. Visible Elements: [{"id": 0, "type": "text_area", "text": "Content", "center": "(400,300)"}]',
        "output": '{"action": "hotkey", "key": "ctrl+z", "reason": "Undo last action"}'
    },
    {
        "instruction": "Close this window",
        "input": 'Active Window: Application. Visible Elements: [{"id": 0, "type": "button", "text": "X", "center": "(1900,10)"}]',
        "output": '{"action": "hotkey", "key": "alt+f4", "reason": "Close window with keyboard"}'
    },
    {
        "instruction": "Open new tab",
        "input": 'Active Window: Chrome. Visible Elements: [{"id": 0, "type": "tab", "text": "Google", "center": "(100,20)"}, {"id": 1, "type": "button", "text": "+", "center": "(200,20)"}]',
        "output": '{"action": "hotkey", "key": "ctrl+t", "reason": "Open new tab"}'
    },
    {
        "instruction": "Find text in page",
        "input": 'Active Window: Browser. Visible Elements: [{"id": 0, "type": "content", "text": "Article content...", "center": "(500,400)"}]',
        "output": '{"action": "hotkey", "key": "ctrl+f", "reason": "Open find dialog"}'
    },
    
    # === SCROLL ACTIONS ===
    {
        "instruction": "Scroll down to see more",
        "input": 'Active Window: Web Page. Visible Elements: [{"id": 0, "type": "text", "text": "Article content...", "center": "(500,300)"}, {"id": 1, "type": "link", "text": "Read more", "center": "(500,700)"}]',
        "output": '{"action": "scroll", "direction": "down", "amount": 300, "reason": "Scroll to see more content"}'
    },
    {
        "instruction": "Scroll up",
        "input": 'Active Window: Page. Visible Elements: [{"id": 0, "type": "text", "text": "Content at middle", "center": "(500,400)"}]',
        "output": '{"action": "scroll", "direction": "up", "amount": 200, "reason": "Scroll up"}'
    },
    {
        "instruction": "Go to top of page",
        "input": 'Active Window: Long Page. Visible Elements: [{"id": 0, "type": "text", "text": "Content at bottom", "center": "(500,600)"}]',
        "output": '{"action": "hotkey", "key": "home", "reason": "Go to top of page"}'
    },
    
    # === BROWSE/NAVIGATION ===
    {
        "instruction": "Open WhatsApp",
        "input": 'Active Window: Ubuntu Desktop. Visible Elements: [{"id": 0, "type": "taskbar", "text": "Activities", "center": "(50,10)"}, {"id": 1, "type": "dock_icon", "text": "Chrome", "center": "(50,400)"}]',
        "output": '{"action": "browse", "url": "web.whatsapp.com", "reason": "Open WhatsApp Web"}'
    },
    {
        "instruction": "Go to Google",
        "input": 'Active Window: Browser. Visible Elements: [{"id": 0, "type": "text_input", "text": "URL", "center": "(500,40)"}]',
        "output": '{"action": "browse", "url": "google.com", "reason": "Navigate to Google"}'
    },
    {
        "instruction": "Open YouTube",
        "input": 'Active Window: Desktop. Visible Elements: [{"id": 0, "type": "icon", "text": "Chrome", "center": "(50,100)"}]',
        "output": '{"action": "browse", "url": "youtube.com", "reason": "Open YouTube"}'
    },
    
    # === WHATSAPP SPECIFIC ===
    {
        "instruction": "Send message hi to John",
        "input": 'Active Window: WhatsApp Web. Visible Elements: [{"id": 0, "type": "chat", "text": "John", "center": "(150,200)"}, {"id": 1, "type": "text_input", "text": "Type a message", "center": "(500,700)"}]',
        "output": '{"action": "send_message", "message": "hi", "recipient": "John", "reason": "Send WhatsApp message"}'
    },
    {
        "instruction": "Send hello to Mom on WhatsApp",
        "input": 'Active Window: WhatsApp. Visible Elements: [{"id": 0, "type": "chat_list", "text": "Chats", "center": "(100,300)"}, {"id": 1, "type": "input", "text": "Search", "center": "(100,50)"}]',
        "output": '{"action": "send_message", "message": "hello", "recipient": "Mom", "reason": "Send message to Mom"}'
    },
    {
        "instruction": "Read messages from Team",
        "input": 'Active Window: WhatsApp Web. Visible Elements: [{"id": 0, "type": "chat", "text": "Team", "center": "(150,250)"}, {"id": 1, "type": "chat", "text": "John", "center": "(150,200)"}]',
        "output": '{"action": "read_whatsapp", "contact": "Team", "reason": "Read messages from Team chat"}'
    },
    
    # === DONE/COMPLETE ===
    {
        "instruction": "Task is complete",
        "input": 'Active Window: Application. Visible Elements: [{"id": 0, "type": "dialog", "text": "Success", "center": "(500,300)"}]',
        "output": '{"action": "done", "reason": "Task completed successfully"}'
    },
    {
        "instruction": "Finished",
        "input": 'Active Window: Desktop. Visible Elements: []',
        "output": '{"action": "done", "reason": "No more actions needed"}'
    },
    
    # === COMPLEX MULTI-STEP SCENARIOS ===
    {
        "instruction": "I want to search for weather on Google",
        "input": 'Active Window: Chrome - New Tab. Visible Elements: [{"id": 0, "type": "text_input", "text": "Search Google or type a URL", "center": "(700,350)"}, {"id": 1, "type": "icon", "text": "Gmail", "center": "(500,500)"}]',
        "output": '{"action": "click", "target_id": 0, "x": 700, "y": 350, "reason": "Click search box first to focus it"}'
    },
    {
        "instruction": "Open Settings app",
        "input": 'Active Window: Ubuntu Desktop. Visible Elements: [{"id": 0, "type": "icon", "text": "Files", "center": "(50,100)"}, {"id": 1, "type": "icon", "text": "Settings", "center": "(50,250)"}, {"id": 2, "type": "icon", "text": "Software", "center": "(50,300)"}]',
        "output": '{"action": "click", "target_id": 1, "x": 50, "y": 250, "reason": "Settings icon"}'
    },
    {
        "instruction": "Click Save button in LibreOffice",
        "input": 'Active Window: LibreOffice Writer. Visible Elements: [{"id": 0, "type": "toolbar_button", "text": "Save", "center": "(45,75)"}, {"id": 1, "type": "toolbar_button", "text": "Undo", "center": "(75,75)"}, {"id": 2, "type": "toolbar_button", "text": "Redo", "center": "(100,75)"}]',
        "output": '{"action": "click", "target_id": 0, "x": 45, "y": 75, "reason": "Save button in toolbar"}'
    },
    {
        "instruction": "Click Accept on cookie popup",
        "input": 'Active Window: Website. Visible Elements: [{"id": 0, "type": "dialog", "text": "We use cookies", "center": "(500,600)"}, {"id": 1, "type": "button", "text": "Accept All", "center": "(450,650)"}, {"id": 2, "type": "button", "text": "Reject", "center": "(550,650)"}]',
        "output": '{"action": "click", "target_id": 1, "x": 450, "y": 650, "reason": "Accept cookies"}'
    },
    {
        "instruction": "Maximize this window",
        "input": 'Active Window: Application. Visible Elements: [{"id": 0, "type": "button", "text": "Minimize", "center": "(1820,10)"}, {"id": 1, "type": "button", "text": "Maximize", "center": "(1850,10)"}, {"id": 2, "type": "button", "text": "Close", "center": "(1890,10)"}]',
        "output": '{"action": "click", "target_id": 1, "x": 1850, "y": 10, "reason": "Maximize window button"}'
    },
    {
        "instruction": "Open the document named report.docx",
        "input": 'Active Window: File Manager. Visible Elements: [{"id": 0, "type": "file", "text": "notes.txt", "center": "(200,150)"}, {"id": 1, "type": "file", "text": "report.docx", "center": "(200,200)"}, {"id": 2, "type": "file", "text": "image.png", "center": "(200,250)"}]',
        "output": '{"action": "double_click", "target_id": 1, "x": 200, "y": 200, "reason": "Double-click to open report.docx"}'
    },
    {
        "instruction": "Right click on the file",
        "input": 'Active Window: File Manager. Visible Elements: [{"id": 0, "type": "file", "text": "document.pdf", "center": "(300,200)"}, {"id": 1, "type": "file", "text": "folder", "center": "(300,250)"}]',
        "output": '{"action": "right_click", "target_id": 0, "x": 300, "y": 200, "reason": "Right-click for context menu"}'
    },
    {
        "instruction": "Press Enter to confirm",
        "input": 'Active Window: Dialog. Visible Elements: [{"id": 0, "type": "button", "text": "OK", "center": "(500,350)"}]',
        "output": '{"action": "hotkey", "key": "enter", "reason": "Confirm action with Enter"}'
    },
    {
        "instruction": "Press Escape to cancel",
        "input": 'Active Window: Popup. Visible Elements: [{"id": 0, "type": "dialog", "text": "Are you sure?", "center": "(500,300)"}]',
        "output": '{"action": "hotkey", "key": "escape", "reason": "Cancel with Escape"}'
    },
]

def main():
    print("=" * 60)
    print("Generating English Training Data for OmniParser")
    print("=" * 60)
    
    os.makedirs("training_data", exist_ok=True)
    
    with open(OUTPUT_FILE, 'w') as f:
        for ex in TRAINING_EXAMPLES:
            f.write(json.dumps(ex) + "\n")
    
    print(f"\n[+] Generated {len(TRAINING_EXAMPLES)} English training examples")
    print(f"[+] Saved to {OUTPUT_FILE}")
    
    # Show samples
    print("\n[*] Sample examples:")
    for i, ex in enumerate(TRAINING_EXAMPLES[:3]):
        print(f"\n  {i+1}. {ex['instruction']}")
        print(f"     Output: {ex['output'][:60]}...")

if __name__ == "__main__":
    main()
