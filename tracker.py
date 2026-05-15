import gspread
from oauth2client.service_account import ServiceAccountCredentials
import os
import json
import requests
import time
from datetime import datetime

# Config
APIFY_TOKEN = os.environ["APIFY_TOKEN"]
GOOGLE_CREDS = json.loads(os.environ["GOOGLE_CREDS"])
SHEET_NAME = "Ad Tracker"

COMPETITORS = {
    "LegalZoom": "96270063170",
}

def fetch_ads(page_id, page_name):
    print(f"Starting Apify run for {page_name}...")

    run_url = "https://api.apify.com/v2/acts/api_creators~facebook-ads-library-scraper-api/runs"
    headers = {"Authorization": f"Bearer {APIFY_TOKEN}"}
    payload = {
        "start_urls": [
            {
                "url": f"https://www.facebook.com/ads/library/?active_status=active&ad_type=all&country=US&is_targeted_country=false&media_type=all&search_type=page&view_all_page_id={page_id}"
            }
        ],
        "maxResults": 150,
    }

    run_response = requests.post(run_url, json=payload, headers=headers)
    run_data = run_response.json()

    run_id = run_data.get("data", {}).get("id")
    dataset_id = run_data.get("data", {}).get("defaultDatasetId")

    if not run_id:
        print("Failed to start run.")
        return []

    print(f"Run started: {run_id}. Waiting for completion...")
    status_url = f"https://api.apify.com/v2/acts/api_creators~facebook-ads-library-scraper-api/runs/{run_id}"

    for _ in range(24):
        time.sleep(5)
        status_response = requests.get(status_url, headers=headers)
        status = status_response.json().get("data", {}).get("status")
        print(f"Status: {status}")
        if status == "SUCCEEDED":
            break
        if status in ["FAILED", "ABORTED", "TIMED-OUT"]:
            print(f"Run failed with status: {status}")
            return []

    results_url = f"https://api.apify.com/v2/datasets/{dataset_id}/items"
    results_response = requests.get(results_url, headers=headers)
    items = results_response.json()

    if not items:
        print("No items returned.")
        return []

    print(f"Raw first item: {json.dumps(items[0], indent=2)[:1000]}")

    results = []
    seen_ids = set()

    for item in items:
        ad_id = str(item.get("ad_archive_id", ""))
        if not ad_id or ad_id in seen_ids:
            continue
        seen_ids.add(ad_id)

        start_ts = item.get("start_date")
        started = datetime.utcfromtimestamp(start_ts).strftime("%Y-%m-%d") if start_ts else ""

        snapshot = item.get("snapshot", {}) or {}
        cards = snapshot.get("cards", []) or []
        ad_text = cards[0].get("body", "") if cards else ""
        title = cards[0].get("title", "") if cards else ""
        cta = snapshot.get("cta_text", "")
        link_url = cards[0].get("link_url", "") if cards else ""

        results.append({
            "ad_id": ad_id,
            "competitor": page_name,
            "date_seen": datetime.today().strftime("%Y-%m-%d"),
            "ad_text": str(ad_text)[:300],
            "title": str(title),
            "cta": str(cta),
            "link_url": str(link_url),
            "started": started,
        })

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
