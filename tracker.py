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
    print(f"Raw response: {json.dumps(data, indent=2)[:2000]}")
    ads = data.get("ads", [])
    results = []
    for ad in ads:
        results.append({
            "competitor": page_name,
            "ad_id": ad.get("id", ""),
            "date_seen": datetime.today().strftime("%Y-%m-%d"),
            "platforms": ", ".join(ad.get("publisher_platforms", [])),
            "ad_text": ad.get("ad_snapshot_url", "")[:200] if ad.get("body", {}).get("text") else "",
            "snapshot_url": ad.get("ad_snapshot_url", ""),
            "started": ad.get("ad_delivery_start_time", ""),
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
                row["platforms"],
                row["ad_text"],
                row["snapshot_url"],
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
