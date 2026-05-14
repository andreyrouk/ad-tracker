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
    all_results = []
    seen_ids = set()
    next_token = None

    while True:
        payload = {
            "engine": "meta_ad_library",
            "page_id": page_id,
            "ad_type": "all",
            "active_status": "active",
            "country": "US",
            "api_key": SEARCHAPI_KEY,
        }
        if next_token:
            payload["next_page_token"] = next_token

        response = requests.post(url, json=payload)
        data = response.json()
        
        print(f"Status code: {response.status_code}")
        print(f"Raw response: {json.dumps(data, indent=2)[:500]}")
        
        ads = data.get("ads", [])

        if not ads:
            print("No ads returned, stopping.")
            break

        new_this_page = 0
        for ad in ads:
            ad_id = ad.get("ad_archive_id", "")
            if ad_id in seen_ids:
                continue
            seen_ids.add(ad_id)
            new_this_page += 1
            snapshot = ad.get("snapshot", {})
            cards = snapshot.get("cards", [])
            ad_text = cards[0].get("body", "") if cards else ""
            title = cards[0].get("title", "") if cards else ""
            link_url = cards[0].get("link_url", "") if cards else ""
            cta = snapshot.get("cta_text", "")
            all_results.append({
                "ad_id": ad_id,
                "competitor": page_name,
                "date_seen": datetime.today().strftime("%Y-%m-%d"),
                "ad_text": ad_text[:300],
                "title": title,
                "cta": cta,
                "link_url": link_url,
                "started": ad.get("start_date", ""),
            })

        print(f"Fetched {len(ads)} ads, {new_this_page} new unique. Total: {len(all_results)}")

        if new_this_page == 0:
            print("No new unique ads, stopping.")
            break

        next_token = data.get("pagination", {}).get("next_page_token")
        if not next_token:
            print("No more pages.")
            break

    return all_results

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
        print(f"Found {len(ads)} active ads.")
        all_ads.extend(ads)
    write_to_sheet(all_ads)
