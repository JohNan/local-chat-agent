from playwright.sync_api import sync_playwright, expect
import time

def verify_chat(page):
    print("Navigating to app...")
    page.goto("http://localhost:5000")

    # Check title
    expect(page).to_have_title("Gemini Code Agent")

    # Type message
    print("Sending message...")
    page.fill("#user-input", "List files")

    # Click Send
    page.click("button.primary-btn")

    # Wait for response
    # We expect "Hello from Mock!"
    print("Waiting for response...")

    # Wait for the AI message bubble
    ai_bubble = page.locator(".message-row.ai .message-bubble").last
    expect(ai_bubble).to_be_visible(timeout=10000)

    # Wait for text content
    expect(ai_bubble).to_contain_text("Hello from Mock", timeout=10000)

    print("Taking screenshot...")
    page.screenshot(path="/home/jules/verification/sse_chat.png")

if __name__ == "__main__":
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        try:
            verify_chat(page)
            print("Verification success!")
        except Exception as e:
            print(f"Verification failed: {e}")
            page.screenshot(path="/home/jules/verification/sse_fail.png")
            raise
        finally:
            browser.close()
