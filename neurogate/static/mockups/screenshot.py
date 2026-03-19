from playwright.sync_api import sync_playwright
import os

MOCKUPS_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.dirname(MOCKUPS_DIR)

pages = [
    ("mockup-dashboard.html", "screen-dashboard.png"),
    ("mockup-security.html", "screen-security.png"),
    ("mockup-onboarding.html", "screen-onboarding.png"),
]

with sync_playwright() as p:
    browser = p.chromium.launch()
    for html_file, png_file in pages:
        page = browser.new_page(viewport={"width": 1280, "height": 800})
        page.goto(f"file://{os.path.join(MOCKUPS_DIR, html_file)}")
        page.wait_for_timeout(1000)  # wait for fonts to load
        page.screenshot(path=os.path.join(STATIC_DIR, png_file), full_page=False)
        print(f"Saved {png_file}")
        page.close()
    browser.close()

print("All screenshots done!")
