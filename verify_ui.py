from playwright.sync_api import sync_playwright, expect
import time

def test_ui_changes(page):
    # Navigate to the frontend
    print("Navigating to frontend...")
    page.goto("http://localhost:5173/static/dist/")

    # Wait for the input area to be visible
    print("Waiting for input area...")
    page.wait_for_selector(".input-area textarea", timeout=10000)

    # --- Test 1: Enter Key Behavior ---
    print("Testing Enter key behavior...")
    textarea = page.locator(".input-area textarea")
    textarea.fill("Hello")
    textarea.press("Enter")

    # Expect the textarea to contain "Hello\n"
    # Wait a bit for potential react state update
    time.sleep(0.5)

    # If it sent, it would be empty. If it inserted newline, it would be "Hello\n" (or trimmed?)
    # InputArea.tsx: if input.trim(), handleSend().
    # If Enter is prevented, handleSend() is NOT called.
    # Default behavior of textarea is newline.
    # So value should be "Hello\n"

    expect(textarea).not_to_be_empty()
    input_value = textarea.input_value()
    # Note: textarea value might not strictly contain \n if React controls it weirdly, but usually yes.
    # Or at least length > 5.
    if "\n" in input_value or len(input_value) > 5:
        print("PASS: Enter key inserted newline (or didn't send).")
    else:
        print(f"FAIL: Enter key didn't insert newline? Value: {repr(input_value)}")
        # If it sent, it would be empty.

    # --- Test 2: Ctrl+Enter Behavior ---
    print("Testing Ctrl+Enter behavior...")
    textarea.fill("Hello World")
    # Using Control+Enter.
    textarea.press("Control+Enter")

    # Expect the textarea to be cleared (message sent)
    expect(textarea).to_be_empty()
    print("PASS: Textarea cleared after Ctrl+Enter.")

    # Expect the message to appear in the chat history
    print("Waiting for message to appear...")
    # Wait for user message bubble
    user_message = page.locator(".message-row.user .message-bubble").filter(has_text="Hello World").last
    expect(user_message).to_be_visible()
    print("PASS: Message appeared in chat.")

    # --- Test 3: Copy Button Visibility (Hover) ---
    print("Testing Copy Button Visibility (Hover)...")
    # Hover over the message bubble
    user_message.hover()

    # Wait for transition
    time.sleep(0.5)

    # Take screenshot of hover state
    page.screenshot(path="verify_hover.png")
    print("Screenshot taken: verify_hover.png")

    # --- Test 4: Copy Button Visibility (Mobile) ---
    print("Testing Copy Button Visibility (Mobile)...")
    # Emulate mobile viewport (iPhone X size)
    page.set_viewport_size({"width": 375, "height": 812})

    # Move mouse away to ensure no hover (though mobile doesn't have hover, but just in case)
    page.mouse.move(0, 0)

    # Wait for transition
    time.sleep(0.5)

    # Take screenshot of mobile state
    page.screenshot(path="verify_mobile.png")
    print("Screenshot taken: verify_mobile.png")

if __name__ == "__main__":
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        try:
            test_ui_changes(page)
        except Exception as e:
            print(f"Test failed: {e}")
            page.screenshot(path="verify_failure.png")
        finally:
            browser.close()
