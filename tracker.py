import gspread
from oauth2client.service_account import ServiceAccountCredentials
import os
import json
from datetime import datetime
from playwright.sync_api import sync_playwright
import time

# Config
GOOGLE_CREDS = json.loads(os.environ["GOOGLE_CREDS"])
SHEET_NAME = "Ad Tracker"

COMPETITORS = {
    "LegalZoom": "96270063170",
}

def fetch_ads(page_id, page_name):
    results = []
    seen_ids = set()

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        url = f"https://www.facebook.com/ads/library/?active_status=active&ad_type=all&country=US&is_targeted_country=false&media_type=all&search_type=page&view_all_page_id={page_id}"
        print(f"Loading {url}")
        page.goto(url, wait_until="networkidle", timeout=60000)
        time.sleep(3)

        with open("page_dump.html", "w") as f:
            f.write(page.content())
        print("Page dumped")

        # Scroll to load ads
        for _ in range(10):
            page.keyboard.press("End")
            time.sleep(2)

        # Extract ad cards
        ad_cards = page.query_selector_all("div[data-testid='ad-archive-preview-card']")
        if not ad_cards:
            ad_cards = page.query_selector_all("div._7jyg")
        if not ad_cards:
            ad_cards = page.query_selector_all("div[class*='_8n_p']")
        print(f"Found {len(ad_cards)} ad cards")

        for card in ad_cards:
            # Dump HTML of first card to inspect structure
            if ad_cards:
                print("FIRST CARD HTML:")
                print(ad_cards[0].inner_html()[:3000])

        browser.close()

    print(f"Total unique ads: {len(results)}")
    return results

def write_to_sheet(rows):
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(GOOGLE_CREDS, scope)
    client = gspread.authorize(creds)
    sheet = client.open(SHEET_NAME).sheet1

    existing = set(sheet.col_values(1))

    new_rows = []
    for row in rows:
        if row["ad_id"] not in existing:
            new_rows.append([
                row["ad_id"],
                row["competitor"],
                row["date_seen"],
                row["ad_text"],
                row["title"],
                row["cta"],
                row["link_url"],
                row["started"],
            ])

    if new_rows:
        sheet.append_rows(new_rows, value_input_option="RAW")

    print(f"Added {len(new_rows)} new ads.")

if __name__ == "__main__":
    all_ads = []
    for name, page_id in COMPETITORS.items():
        print(f"Fetching {name}...")
        ads = fetch_ads(page_id, name)
        all_ads.extend(ads)
    write_to_sheet(all_ads)
