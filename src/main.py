from playwright.sync_api import sync_playwright


def main():
    print("Starting Playwright test...")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        page.goto("https://example.com")
        title = page.title()

        print("Page title:", title)

        browser.close()

    print("Playwright test completed.")


if __name__ == "__main__":
    main()
