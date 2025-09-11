from playwright.sync_api import sync_playwright
import re

BASE = "https://www.livcheers.com"

def normalize_price(s: str) -> str:
    if not s:
        return ""
    m = re.search(r"(\d[\d,]*)", s)
    return f"₹{m.group(1)}" if m else s.strip()

def scrape_livcheers_via_typing(brand: str, city: str = "delhi", limit: int = 5):
    results = []
    url = f"{BASE}/{city}/search"

    with sync_playwright() as p:
        # ✅ Headless mode (no Chrome popup)
        browser = p.chromium.launch(headless=True)
        context = browser.new_context()
        page = context.new_page()

        # Open search page directly
        page.goto(url, timeout=60000)

        # ✅ Age gate
        try:
            page.wait_for_selector("button:has-text('Yes')", timeout=5000)
            page.click("button:has-text('Yes')")
            page.wait_for_timeout(1000)
        except:
            pass

        # ✅ Type into search bar
        page.wait_for_selector("input#searchString", timeout=10000)
        search_box = page.query_selector("input#searchString")
        search_box.fill(brand)
        page.keyboard.press("Enter")
        page.wait_for_timeout(5000)

        # ✅ Collect product cards
        cards = page.query_selector_all("a[href*='/liquor/']")
        for card in cards:
            name_el = card.query_selector("h2, h3, .product-title, p")
            price_el = card.query_selector("span:text-matches('₹'), div:text-matches('₹'), .text-theme-bg, .mrp, .price, .amount")

            name = name_el.inner_text().strip() if name_el else ""
            price = normalize_price(price_el.inner_text()) if price_el else ""

            if brand.lower() in name.lower():
                results.append({"name": name, "price": price})
                if len(results) >= limit:
                    break

        browser.close()

    return results

if __name__ == "__main__":
    data = scrape_livcheers_via_typing("Old Monk", "delhi")
    print("Results:", data)


'''
from playwright.sync_api import sync_playwright
import re

BASE = "https://www.livcheers.com"

def normalize_price(s: str) -> str:
    if not s:
        return ""
    m = re.search(r"(\d[\d,]*)", s)
    return f"₹{m.group(1)}" if m else s.strip()

def scrape_livcheers_via_typing(brand: str, city: str = "delhi", headless: bool = False, limit: int = 5):
    results = []
    url = f"{BASE}/{city}/search"

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless, slow_mo=250)
        context = browser.new_context()
        page = context.new_page()

        # Open search page directly
        page.goto(url, timeout=60000)

        # ✅ Age gate
        try:
            page.wait_for_selector("button:has-text('Yes')", timeout=5000)
            page.click("button:has-text('Yes')")
            print("✅ Age gate cleared")
            page.wait_for_timeout(1000)
        except:
            print("⚠️ No age gate")

        # ✅ Type into real search bar
        page.wait_for_selector("input#searchString", timeout=10000)
        search_box = page.query_selector("input#searchString")
        search_box.fill(brand)
        page.keyboard.press("Enter")
        print(f"🔍 Typed brand: {brand}")
        page.wait_for_timeout(5000)  # wait for results

        # ✅ Collect product cards
        cards = page.query_selector_all("a[href*='/liquor/']")
        for card in cards:
            name_el = card.query_selector("h2, h3, .product-title, p")
            price_el = card.query_selector("span:text-matches('₹'), div:text-matches('₹'), .text-theme-bg, .mrp, .price, .amount")

            name = name_el.inner_text().strip() if name_el else ""
            price = normalize_price(price_el.inner_text()) if price_el else ""

            if brand.lower() in name.lower():
                results.append({"name": name, "price": price})
                if len(results) >= limit:
                    break

        # Save debug files
        with open("debug_typing_fixed.html", "w", encoding="utf-8") as f:
            f.write(page.content())
        page.screenshot(path="debug_typing_fixed.png", full_page=True)

        browser.close()

    return results

if __name__ == "__main__":
    data = scrape_livcheers_via_typing("jim beam", "mumbai", headless=False)
    print("Results:", data)
'''