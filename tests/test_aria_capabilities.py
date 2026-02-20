#!/usr/bin/env python3
"""
Comprehensive ARIA Capabilities Test
Tests: SMTP/IMAP, YouTube, WhatsApp, System (Volume/Brightness), Browser Search
"""

import sys
import os
import time
import subprocess

# Add project root
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.automation_tools import AutomationTools

# ============================================================
# Test Configuration
# ============================================================
TEST_EMAIL_TO = "harshamerugu78@gmail.com"  # Send test email to self
TEST_YOUTUBE_QUERY = "lofi hip hop radio"
TEST_BROWSER_QUERY = "ARIA AI assistant"
# ============================================================

def print_header(title):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")

def print_result(name, result):
    success = result.get("success", False)
    icon = "✅" if success else "❌"
    print(f"  {icon} {name}")
    if success:
        # Print relevant details (skip large content)
        for k, v in result.items():
            if k in ("success",): continue
            val_str = str(v)
            if len(val_str) > 80:
                val_str = val_str[:77] + "..."
            print(f"     {k}: {val_str}")
    else:
        print(f"     Error: {result.get('error', 'Unknown')}")
    return success


def test_email(tools):
    """Test SMTP send and IMAP read."""
    print_header("📧 EMAIL (SMTP/IMAP)")
    results = []

    # 1. Send email
    print("\n  [1/2] Sending test email...")
    r = tools.execute("email_send",
                      to=TEST_EMAIL_TO,
                      subject="ARIA Test Email",
                      body="This is an automated test from ARIA capabilities checker.")
    results.append(print_result("email_send", r))

    # 2. Read emails
    print("\n  [2/2] Reading recent emails...")
    r = tools.execute("email_read", limit=3, unread_only=False)
    results.append(print_result("email_read", r))

    return results


def test_youtube(tools):
    """Test YouTube search/play."""
    print_header("🎵 YOUTUBE")
    results = []

    print(f"\n  [1/1] Searching YouTube: '{TEST_YOUTUBE_QUERY}'")
    r = tools.execute("youtube_search", query=TEST_YOUTUBE_QUERY)
    results.append(print_result("youtube_search", r))

    return results


def test_whatsapp(tools):
    """Test WhatsApp bridge availability (does not actually send)."""
    print_header("💬 WHATSAPP")
    results = []

    # Check if WhatsApp bridge is reachable
    print("\n  [1/1] Checking WhatsApp bridge reachability...")
    try:
        import requests
        resp = requests.get("http://localhost:3001/status", timeout=5)
        if resp.status_code == 200:
            r = {"success": True, "status": resp.json()}
        else:
            r = {"success": False, "error": f"Bridge returned HTTP {resp.status_code}"}
    except requests.exceptions.ConnectionError:
        r = {"success": False, "error": "WhatsApp bridge not running (localhost:3000)"}
    except Exception as e:
        r = {"success": False, "error": str(e)}

    results.append(print_result("whatsapp_bridge_status", r))
    return results


def test_system_volume(tools):
    """Test volume control."""
    print_header("🔊 VOLUME CONTROL")
    results = []

    # Get current volume first
    print("\n  [1/3] Getting current volume...")
    r = tools.execute("run_command", command="pactl get-sink-volume @DEFAULT_SINK@")
    current_vol_str = r.get("stdout", "")
    print_result("get_volume", r)

    # Set volume to 50%
    print("\n  [2/3] Setting volume to 50%...")
    r = tools.execute("set_volume", level=50)
    results.append(print_result("set_volume(50)", r))

    # Verify
    print("\n  [3/3] Verifying volume...")
    time.sleep(0.5)
    r = tools.execute("run_command", command="pactl get-sink-volume @DEFAULT_SINK@")
    results.append(print_result("verify_volume", r))
    if r.get("success"):
        print(f"     Output: {r.get('stdout', '').strip()[:60]}")

    return results


def test_system_brightness(tools):
    """Test brightness control."""
    print_header("☀️  BRIGHTNESS CONTROL")
    results = []

    # Get current brightness
    print("\n  [1/3] Getting current brightness...")
    r = tools.execute("run_command", command="brightnessctl -m | head -1")
    current = r.get("stdout", "").strip()
    print_result("get_brightness", r)
    if current:
        print(f"     Current: {current[:60]}")

    # Set brightness to 70%
    print("\n  [2/3] Setting brightness to 70%...")
    r = tools.execute("set_brightness", level=70)
    results.append(print_result("set_brightness(70)", r))

    # Verify
    print("\n  [3/3] Verifying brightness...")
    time.sleep(0.5)
    r = tools.execute("run_command", command="brightnessctl -m | head -1")
    results.append(print_result("verify_brightness", r))
    if r.get("success"):
        print(f"     Current: {r.get('stdout', '').strip()[:60]}")

    return results


def test_browser_search(tools):
    """Test browser search via xdg-open."""
    print_header("🌐 BROWSER SEARCH")
    results = []

    print(f"\n  [1/1] Opening browser search: '{TEST_BROWSER_QUERY}'")
    url = f"https://www.google.com/search?q={TEST_BROWSER_QUERY.replace(' ', '+')}"
    r = tools.execute("run_command", command=f"xdg-open '{url}'")
    results.append(print_result("browser_search", r))

    return results


def test_system_info(tools):
    """Test system info gathering."""
    print_header("💻 SYSTEM INFO")
    results = []

    print("\n  [1/2] Getting system info...")
    r = tools.execute("get_system_info")
    results.append(print_result("get_system_info", r))

    print("\n  [2/2] Desktop notification...")
    r = tools.execute("notify", title="ARIA Test", message="Capabilities test running!")
    results.append(print_result("notify", r))

    return results


def main():
    print("\n" + "=" * 60)
    print("  🤖 ARIA COMPREHENSIVE CAPABILITIES TEST")
    print("=" * 60)
    print(f"  Time: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  Host: {os.uname().nodename}")
    print("=" * 60)

    tools = AutomationTools()

    all_results = []

    # 1. Email
    all_results.extend(test_email(tools))

    # 2. YouTube
    all_results.extend(test_youtube(tools))

    # 3. WhatsApp
    all_results.extend(test_whatsapp(tools))

    # 4. Volume
    all_results.extend(test_system_volume(tools))

    # 5. Brightness
    all_results.extend(test_system_brightness(tools))

    # 6. Browser Search
    all_results.extend(test_browser_search(tools))

    # 7. System Info
    all_results.extend(test_system_info(tools))

    # Summary
    passed = sum(1 for r in all_results if r)
    total = len(all_results)

    print_header(f"📊 SUMMARY: {passed}/{total} PASSED")

    categories = [
        ("Email (SMTP/IMAP)", all_results[0:2]),
        ("YouTube", all_results[2:3]),
        ("WhatsApp Bridge", all_results[3:4]),
        ("Volume Control", all_results[4:6]),
        ("Brightness Control", all_results[6:8]),
        ("Browser Search", all_results[8:9]),
        ("System Info", all_results[9:11]),
    ]

    for name, results in categories:
        cat_pass = sum(1 for r in results if r)
        cat_total = len(results)
        icon = "✅" if cat_pass == cat_total else ("⚠️" if cat_pass > 0 else "❌")
        print(f"  {icon} {name}: {cat_pass}/{cat_total}")

    print(f"\n  Overall: {passed}/{total} ({100*passed/total:.0f}%)")
    print("=" * 60)


if __name__ == "__main__":
    main()
