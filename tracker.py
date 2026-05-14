import requests
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import os
import json
from datetime import datetime

# Config
SEARCHAPI_KEY = os.environ["SEARCHAPI_KEY"]
GOOGLE_CREDS = json.loads(os.environ["GOOGLE_CREDS"])

COMPETITORS = {
    "LegalZoom": "96270063170",
}

SHEET_NAME = "Ad Tracker"

def fetch_ads(page_id, page_name):
    url = "https://www.searchapi.io/api/v1/search"
    params = {
        "engine": "meta_ad_library",
        "page_id": page_id,
        "ad_type": "all",
        "active_status": "active",
        "country": "US",
        "api_key": SEARCHAPI_KEY,
    }
    response = requests.get(url, params=params)
    data = response.json()
    ads = data.get("ads", [])
    results = []
    for ad in ads:
        snapshot = ad.get("snapshot", {})
        cards = snapshot.get("cards", [])
        ad_text = cards[0].get("body", "") if cards else ""
        title = cards[0].get("title", "") if cards else ""
        link_url = cards[0].get("link_url", "") if cards else ""
        cta = snapshot.get("cta_text", "")
        results.append({
            "ad_id": ad.get("ad_archive_id", ""),
            "competitor": page_name,
            "date_seen": datetime.today().strftime("%Y-%m-%d"),
            "ad_text": ad_text[:300],
            "title": title,
            "cta": cta,
            "link_url": link_url,
            "started": ad.get("start_date", ""),
        })
    return results

def write_to_sheet(rows):
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(GOOGLE_CREDS, scope)
    client = gspread.authorize(creds)
    sheet = client.open(SHEET_NAME).sheet1

    existing = sheet.col_values(1)  # ad_id column

    new_rows = 0
    for row in rows:
        if row["ad_id"] not in existing:
            sheet.append_row([
                row["ad_id"],
                row["competitor"],
                row["date_seen"],
                row["ad_text"],
                row["title"],
                row["cta"],
                row["link_url"],
                row["started"],
            ])
            new_rows += 1

    print(f"Added {new_rows} new ads.")

if __name__ == "__main__":
    all_ads = []
    for name, page_id in COMPETITORS.items():
        print(f"Fetching {name}...")
        ads = fetch_ads(page_id, name)
        print(f"Found {len(ads)} active ads.")
        all_ads.extend(ads)
    write_to_sheet(all_ads)
