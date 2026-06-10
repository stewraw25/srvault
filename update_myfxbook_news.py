#!/usr/bin/env python3
"""
DEPRECATED.

We have completely dropped MyFXBook.

Use the Grok Global Search process instead:
    1. Tell Grok "do the weekly news scan"
    2. Run: python sr_vault_news_scan.py

See sr_vault_news_scan.py for details.
"""

import requests
import json
from datetime import datetime, timedelta
from io import StringIO
import csv
import os

# Same paths as the Streamlit app
NEWS_CACHE_PATH = "/Users/stewartrawson/sr_vault_assets/news/myfxbook_news.json"
os.makedirs(os.path.dirname(NEWS_CACHE_PATH), exist_ok=True)

RELEVANT_KEYWORDS = [
    "NFP", "NON-FARM", "NONFARM", "PAYROLL", "EMPLOYMENT SITUATION",
    "BOE", "BANK OF ENGLAND", "MPC", "RATE DECISION",
    "INFLATION", "CPI", "CORE CPI", "RPI",
    "GDP",
    "FED", "FOMC", "POWELL", "INTEREST RATE DECISION", "FEDERAL RESERVE",
    "TARIFF", "TARIFFS",
]

RELEVANT_CURRENCIES = {"USD", "GBP", "JPY", "JAPAN"}

def is_gbpjpy_relevant(event: str, currency: str) -> bool:
    text = f"{event} {currency}".upper()
    if currency.upper() not in RELEVANT_CURRENCIES:
        return False
    return any(kw in text for kw in RELEVANT_KEYWORDS)

def parse_myfxbook_csv(csv_content: str):
    events = []
    try:
        reader = csv.DictReader(StringIO(csv_content))
        for row in reader:
            date_raw = row.get("Date") or row.get("date") or ""
            time_raw = row.get("Time") or row.get("time") or ""
            currency = (row.get("Currency") or row.get("currency") or "").strip().upper()
            event = (row.get("Event") or row.get("event") or "").strip()
            impact_raw = (row.get("Impact") or row.get("impact") or "").strip().lower()

            if not event or not currency:
                continue

            dt = None
            for fmt in ("%B %d, %Y", "%b %d, %Y", "%Y-%m-%d"):
                try:
                    dt = datetime.strptime(date_raw, fmt)
                    break
                except ValueError:
                    pass
            if dt is None:
                continue
            date = dt.strftime("%Y-%m-%d")

            time_utc = time_raw[:5] if ":" in time_raw else "00:00"
            imp = "HIGH" if "high" in impact_raw else ("MEDIUM" if "medium" in impact_raw else "LOW")

            events.append({
                "date": date,
                "time_utc": time_utc,
                "event": event,
                "currency": currency,
                "impact": imp
            })
    except Exception as e:
        print(f"  Parser error: {e}")
    return events

def fetch_myfxbook_weekly_events():
    """Fetch ~15 days of events from MyFXBook."""
    try:
        today = datetime.now()
        start = (today - timedelta(days=1)).strftime("%Y-%m-%d 00:00:00.0")
        end = (today + timedelta(days=14)).strftime("%Y-%m-%d 23:59:59.0")

        url = "https://www.myfxbook.com/calendar_statement.csv"
        params = {
            "filter": "0-1-2-3_GBP-JPY-USD-EUR",
            "start": start,
            "end": end,
            "calPeriod": "10",
            "tabType": "0"
        }

        print(f"Fetching MyFXBook calendar from {start} to {end} ...")
        resp = requests.get(url, params=params, timeout=20, headers={
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
        })

        if resp.status_code == 200 and len(resp.text) > 200 and "Date" in resp.text[:300]:
            events = parse_myfxbook_csv(resp.text)
            filtered = [e for e in events if is_gbpjpy_relevant(e["event"], e["currency"])]
            return filtered
        else:
            print(f"  MyFXBook returned empty or unexpected data (status {resp.status_code}).")
    except Exception as e:
        print(f"  Fetch error: {e}")

    return []

def main():
    print("=== SR Vault Weekly MyFXBook News Updater ===\n")

    events = fetch_myfxbook_weekly_events()

    if not events:
        print("\nNo events fetched. You can still manually update via the app's CSV importer.")
        return

    cache = {
        "last_fetched": datetime.now().isoformat(),
        "source": "MyFXBook (auto)",
        "events": events
    }

    with open(NEWS_CACHE_PATH, "w") as f:
        json.dump(cache, f, indent=2)

    print(f"\n✅ Successfully saved {len(events)} relevant events to:")
    print(f"   {NEWS_CACHE_PATH}")
    print("\nNext time you open the trading panel it will load these automatically.")
    print("\nUpcoming events (filtered):")
    for e in events[:12]:  # show first 12
        print(f"  {e['date']} {e['time_utc']}  {e['currency']}  {e['event'][:60]}")

    if len(events) > 12:
        print(f"  ... and {len(events)-12} more")

if __name__ == "__main__":
    main()