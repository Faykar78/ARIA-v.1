
import os
import sys
import time
import json
import pyautogui
import argparse
from datetime import datetime

# Add src to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../')))

from src.brain import LocalBrain
from src.bridges.whatsapp_bridge import WhatsAppBridge

class ActionPlanner:
    def __init__(self):
        print("[*] Initializing Action Planner (Llama 3.1 + OmniParser)...")
        # Disable LLaVA since we use OmniParser internally in Brain
        # Provide the same VRAM-optimized settings
        self.brain = LocalBrain(vision_model="omniparser", gpu_layers=35) 
        # self.parser removed - Brain owns it now.
        self.screenshot_dir = "screenshots"
        os.makedirs(self.screenshot_dir, exist_ok=True)
        
        # Tools
        self.whatsapp = None
        
    def capture_screen(self, label="screen"):
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = os.path.join(self.screenshot_dir, f"{label}_{timestamp}.png")
        # Use pyautogui or scrot
        pyautogui.screenshot(filename)
        self.last_screen_path = filename
        return filename

    def execute_action(self, decision, parsed_items):
        action = decision.get("action")
        if not action:
            print(f"    [!] Error: Brain returned no action. Decision: {decision}")
            return False
            
        reason = decision.get("reason", "No reason provided")
        print(f"  [Planner] Executing: {action.upper()} ({reason})")
        
        if action == "click":
            bbox = None
            
            # Robustness: Handle Llama hallucinations (e.g. nested 'target' object)
            if "target" in decision and isinstance(decision["target"], dict):
                decision["selected_id"] = decision["target"].get("id")
                # If there's a bbox in the nested target (unlikely from brain but possible), use it
                if "box_2d" in decision["target"]:
                     bbox = decision["target"]["box_2d"]

            item_id = decision.get("selected_id")
            description = decision.get("target_description")
            
            # Check if bbox was provided by Brain (VLM mode)
            if "bbox" in decision:
                bbox = decision["bbox"]
                
            # Fallback: Use ID if no bbox yet
            elif item_id is not None:
                target = next((item for item in parsed_items if item["id"] == item_id), None)
                if target:
                    bbox = target["box_2d"]
            
            # Grounding is now handled by Brain.process()
            # If bbox is still None, we can't act.
            
            if bbox:
                # Clamp to avoid PyAutoGUI Failsafe (0,0 trigger)
                # ... existing click logic ...
                center_x = (bbox[0] + bbox[2]) // 2
                center_y = (bbox[1] + bbox[3]) // 2
                
                print(f"    [Debug] Coords: BBox={bbox} -> Center=({center_x}, {center_y})")

                center_x = max(1, center_x)
                center_y = max(1, center_y)
                
                print(f"    -> Clicking '{description or item_id}' at ({center_x}, {center_y})")
                pyautogui.moveTo(center_x, center_y)
                time.sleep(0.5)
                pyautogui.click()
                return True
            else:
                print(f"    [!] Error: Item {item_id}/{description} not found.")
                return False

        elif action == "type":
            text = decision.get("text", "")
            print(f"    -> Typing: '{text}'")
            pyautogui.write(text, interval=0.05)
            return True

        elif action == "hotkey":
            keys = decision.get("keys", [])
            print(f"    -> Hotkey: {keys}")
            pyautogui.hotkey(*keys)
            return True
            
        elif action == "wait":
            print("    -> Waiting 2s...")
            time.sleep(2)
            return True

        elif action == "done":
            print("    [Planner] Task Completed.")
            return "DONE"

        # Specialized Skills (Delegate to Brain's knowledge/Workflows)
        elif action == "send_whatsapp":
            contact = decision.get("contact")
            message = decision.get("message")
            print(f"    -> WhatsApp Bridge: Sending '{message}' to '{contact}'")
            
            if not self.whatsapp:
                self.whatsapp = WhatsAppBridge()
                if not self.whatsapp.connect():
                    print("    [!] Bridge failed to connect.")
                    return False
            
            if self.whatsapp.select_chat(contact):
                time.sleep(1)
                self.whatsapp.send_message(message)
                return True
            else:
                print(f"    [!] Could not find chat: {contact}")
                return False

        elif action == "shell":
            cmd = decision.get("command")
            print(f"    -> Shell: {cmd}")
            os.system(cmd)
            return True
            
        elif action in ["read_whatsapp", "execute_whatsapp_js", "wallpaper"]:
             # Future implementation or similar bridge usage
             print(f"    [!] Specialized skill '{action}' triggered (pending implementation).")
             return True

        else:
            print(f"    [!] Unknown action: {action}")
            return False

    def run_goal(self, user_goal):
        print(f"\n[*] STARTING GOAL: {user_goal}")
        history = []
        
        step = 0
        MAX_STEPS = 15
        
        while step < MAX_STEPS:
            print(f"\n--- STEP {step+1} ---")
            
            # 1. Capture
            screen_path = self.capture_screen(f"step_{step}_before")
            
            # 2. Brain (VLM Mode) - See & Think
            # The Brain now handles Vision (OmniParser) internally
            decision = self.brain.process(
                user_goal=user_goal,
                image_path=screen_path,
                history=history,
                active_window="Desktop"
            )
            
            if not decision:
                print("    [!] Brain returned None. Stopping.")
                break

            # 3. Execute
            # Pass empty parsed_items because Brain now handles resolution internally
            # We might need parsed_items for 'type' or validation, but click handles itself via bbox
            parsed_items = self.brain.last_detected_items or []
            
            result = self.execute_action(decision, parsed_items)
            
            if result == "DONE":
                break
            
            # 4. Verify
            # Add to history
            history.append(f"Step {step}: Action {decision.get('action')} - {decision.get('reason')}")
            step += 1
            time.sleep(1) # Settling time

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("goal", nargs="?", help="Goal to execute")
    args = parser.parse_args()
    
    planner = ActionPlanner()
    
    if args.goal:
        planner.run_goal(args.goal)
    else:
        while True:
            try:
                goal = input("\nEnter Goal (or 'exit'): ")
                if goal.lower() in ["exit", "quit"]: break
                planner.run_goal(goal)
            except KeyboardInterrupt:
                break

if __name__ == "__main__":
    main()
