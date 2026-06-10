#!/usr/bin/env python3
"""
SR VAULT — Weekly News Scan (Grok Global Search)

Completely independent of MyFXBook.

RECOMMENDED WEEKLY PROCESS:
1. In this chat, tell Grok: "do the weekly news scan" (or add a date range)
2. Grok performs a global web search and populates accurate high-impact events
   for your exact criteria (NFP, BOE, GBP inflation/GDP, YEN GDP/CPI, US CPI/FOMC/rates, tariffs).
3. Run: python sr_vault_news_scan.py
4. Refresh the Daily Trading Panel

The script applies the researched events (from the RESEARCHED_EVENTS list at the top
of this file + any auto sources), filters them, writes the cache the panel uses,
and prints a clean preview with your preferred date formatting.

Cache (internal filename): sr_vault_assets/news/myfxbook_news.json (or your local path when not in CI)
"""

import json
from datetime import datetime, timedelta, timezone
import os
import requests
import time

# =============================================================================
# CONFIG — same as the trading panel
# =============================================================================
# Path is relative to this script so it works whether you run from the srvault folder,
# from GitHub Actions (cwd = repo root), or double-click the script. No hard-coded usernames.
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
NEWS_CACHE_PATH = os.path.join(SCRIPT_DIR, "sr_vault_assets", "news", "myfxbook_news.json")

os.makedirs(os.path.dirname(NEWS_CACHE_PATH), exist_ok=True)

# =============================================================================
# STRICT USER WHITELIST — ONLY THESE EVENTS WILL EVER APPEAR IN THE PANEL
# =============================================================================
# These are the *only* news events you have mentioned as relevant for your GBPJPY trading.
# Everything else (even if high impact or in USD/GBP/JPY) is filtered as completely irrelevant.
#
# To update: 
#   1. Ask me "list the news events I want" or paste the exact titles from Forex Factory.
#   2. I will update this list.
#   3. Re-run the script or let the GitHub Action do it.
#
# Event titles should be as close as possible to the official Forex Factory title (case-insensitive match).

STRICT_WHITELIST_EVENTS = [
    # US CPI variants (high impact for risk / USD)
    "CPI (MoM)",
    "Core CPI (MoM)",
    "CPI (YoY)",
    "Core CPI (YoY)",
    # GBP GDP (key for GBPJPY)
    "GDP (MoM)",
    "GDP q/q",
    # Add any others you have specifically mentioned below (exact titles only)
    # "BOE Rate Decision",
    # "FOMC Statement",
    # "Non-Farm Payrolls",
]

RELEVANT_CURRENCIES = {"USD", "GBP", "JPY", "JAPAN", "UK", "UNITED KINGDOM"}

def is_gbpjpy_relevant(event: str, currency: str) -> bool:
    if not event or not currency:
        return False
    if currency.upper() not in RELEVANT_CURRENCIES:
        return False
    text = event.upper()
    # Strict whitelist only — no broad keywords anymore
    return any(wh.upper() in text for wh in STRICT_WHITELIST_EVENTS)

def country_to_currency(country: str) -> str:
    c = (country or "").upper()
    if "UNITED STATES" in c or c in ("US", "USA"):
        return "USD"
    if "UNITED KINGDOM" in c or "UK" in c or "BRITAIN" in c:
        return "GBP"
    if "JAPAN" in c:
        return "JPY"
    if "EURO" in c or "GERMANY" in c or "EUROZONE" in c:
        return "EUR"
    return country  # keep original for filtering

def fetch_forex_factory_this_week(max_retries: int = 2) -> list:
    """
    Fetch the public no-login Forex Factory this-week calendar JSON.
    This is currently one of the best free, structured sources for forex economic events.
    Returns list of events in our internal format (or [] on failure).
    """
    url = "https://nfs.faireconomy.media/ff_calendar_thisweek.json"
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
        "Accept": "application/json",
    }

    for attempt in range(max_retries):
        try:
            print(f"  Fetching Forex Factory public calendar (attempt {attempt+1})...")
            resp = requests.get(url, headers=headers, timeout=20)
            if resp.status_code == 200:
                raw = resp.json()
                events = []
                for item in raw:
                    if not isinstance(item, dict):
                        continue
                    title = item.get("title", "").strip()
                    country = item.get("country", "").strip()
                    date_str = item.get("date", "")
                    impact_raw = (item.get("impact") or "").strip().lower()

                    if not title or not date_str:
                        continue

                    # Parse the ISO date with offset (e.g. 2026-06-10T12:30:00-04:00)
                    try:
                        dt = datetime.fromisoformat(date_str)
                    except Exception:
                        continue

                    # Convert to UTC for consistent time_utc
                    if dt.tzinfo is not None:
                        utc_dt = dt.astimezone(timezone.utc)
                    else:
                        utc_dt = dt  # assume already utc if no tz (fallback)

                    date = utc_dt.strftime("%Y-%m-%d")
                    time_utc = utc_dt.strftime("%H:%M")

                    imp = "HIGH" if "high" in impact_raw else ("MEDIUM" if "medium" in impact_raw else "LOW")
                    currency = country_to_currency(country)

                    events.append({
                        "date": date,
                        "time_utc": time_utc,
                        "event": title,
                        "currency": currency,
                        "impact": imp,
                        "source": "Forex Factory"
                    })
                print(f"  Retrieved {len(events)} raw events from Forex Factory.")
                return events
            else:
                print(f"  HTTP {resp.status_code}")
        except Exception as e:
            print(f"  Fetch error: {e}")
        time.sleep(1.5 * (attempt + 1))  # be nice to rate limits

    print("  Forex Factory fetch failed after retries.")
    return []

def format_date_nice(date_str: str) -> str:
    """Thursday 11th June 2026 style (exactly as the panel uses)."""
    dt = datetime.strptime(date_str, "%Y-%m-%d")
    weekday = dt.strftime("%A")
    day = dt.day
    if 10 <= day % 100 <= 20:
        suffix = "th"
    else:
        suffix = {1: "st", 2: "nd", 3: "rd"}.get(day % 10, "th")
    month = dt.strftime("%B")
    year = dt.year
    return f"{weekday} {day}{suffix} {month} {year}"

def get_week_start(d: datetime) -> datetime:
    return d - timedelta(days=d.weekday())

# =============================================================================
# === GROK-RESEARCHED EVENTS ===
# This list is populated by Grok when you ask for a weekly news scan.
# Format must be exactly:
#   {"date": "YYYY-MM-DD", "time_utc": "HH:MM", "event": "Exact Event Title", "currency": "USD", "impact": "HIGH"}
#
# Only include events that match the filter above and are high-impact.
# Times should be in UTC (most calendars show ET or local — convert if needed: ET is UTC-4 or UTC-5).
#
# Grok will replace the list below during each scan.
# =============================================================================
RESEARCHED_EVENTS = [
    # Refreshed 2026-06-10 via sr_vault_news_scan.py (cross-checked against live Forex Factory public calendar)
    # Sources: FF + prior Grok global search for June 2026 high-impact (only NFP/BOE/GBP inflation+GDP / YEN GDP+CPI / US CPI+FOMC/rates / tariffs)
    {"date": "2026-06-10", "time_utc": "12:30", "event": "CPI (MoM)", "currency": "USD", "impact": "HIGH"},
    {"date": "2026-06-10", "time_utc": "12:30", "event": "Core CPI (MoM)", "currency": "USD", "impact": "HIGH"},
    {"date": "2026-06-10", "time_utc": "12:30", "event": "CPI (YoY)", "currency": "USD", "impact": "HIGH"},
    {"date": "2026-06-12", "time_utc": "06:00", "event": "GDP (MoM)", "currency": "GBP", "impact": "HIGH"},
    # Next week candidates (FOMC / BoE MPC around 17-18 Jun) — will be confirmed in next scan
]

# =============================================================================
# CORE LOGIC
# =============================================================================

def get_relevant_events_for_weeks(events):
    """Filter + attach week info for display."""
    today = datetime.now().date()
    today_str = today.strftime("%Y-%m-%d")

    this_monday = get_week_start(datetime.now())
    this_monday_str = this_monday.strftime("%Y-%m-%d")
    this_week_end_str = (this_monday + timedelta(days=6)).strftime("%Y-%m-%d")

    next_monday = this_monday + timedelta(days=7)
    next_monday_str = next_monday.strftime("%Y-%m-%d")
    next_week_end_str = (next_monday + timedelta(days=6)).strftime("%Y-%m-%d")

    filtered = []
    for e in events:
        if not is_gbpjpy_relevant(e.get("event", ""), e.get("currency", "")):
            continue
        filtered.append(e)

    # Categorize
    today_events = [e for e in filtered if e["date"] == today_str]
    this_week_events = [e for e in filtered 
                        if this_monday_str <= e["date"] <= this_week_end_str and e["date"] != today_str]
    next_week_events = [e for e in filtered 
                        if next_monday_str <= e["date"] <= next_week_end_str]

    return {
        "today_str": today_str,
        "this_monday_str": this_monday_str,
        "next_monday_str": next_monday_str,
        "today_events": sorted(today_events, key=lambda x: x["time_utc"]),
        "this_week_events": sorted(this_week_events, key=lambda x: (x["date"], x["time_utc"])),
        "next_week_events": sorted(next_week_events, key=lambda x: (x["date"], x["time_utc"])),
    }

def save_to_cache(events, source="Grok Weekly Scan"):
    cache = {
        "last_fetched": datetime.now().isoformat(),
        "source": source,
        "events": events
    }
    with open(NEWS_CACHE_PATH, "w") as f:
        json.dump(cache, f, indent=2)
    return cache

def print_roadmap_preview(weeks_info):
    print("\n" + "=" * 70)
    print("SR VAULT WEEKLY NEWS ROADMAP PREVIEW (what the panel will show)")
    print("=" * 70)

    print(f"\nLast updated: {datetime.now().strftime('%A %d %B %Y %H:%M')} (local)")

    # TODAY
    print(f"\n**TODAY** ({weeks_info['today_str']})")
    if weeks_info["today_events"]:
        for e in weeks_info["today_events"]:
            print(f"  {e['time_utc']} UTC | {e['currency']:4} | {e['event']}")
    else:
        print("  (no matching high-impact events today)")

    # THIS WEEK
    nice_this = format_date_nice(weeks_info["this_monday_str"])
    print(f"\n**THIS WEEK** (Week beginning {nice_this})")
    if weeks_info["this_week_events"]:
        for e in weeks_info["this_week_events"]:
            nice_d = format_date_nice(e["date"])
            print(f"  {nice_d} | {e['time_utc']} UTC | {e['currency']:4} | {e['event']}")
    else:
        print("  (no more matching events in the rest of this week)")

    # NEXT WEEK
    nice_next = format_date_nice(weeks_info["next_monday_str"])
    print(f"\n**NEXT WEEK** (Week beginning {nice_next})")
    if weeks_info["next_week_events"]:
        for e in weeks_info["next_week_events"]:
            nice_d = format_date_nice(e["date"])
            print(f"  {nice_d} | {e['time_utc']} UTC | {e['currency']:4} | {e['event']}")
    else:
        print("  (no matching events scheduled yet for next week)")

    print("\n" + "=" * 70)
    print("✅ Cache written to:", NEWS_CACHE_PATH)
    print("   Open (or refresh) the Daily Trading Panel to see the updated roadmap.")
    print("   The panel will show 'Last updated via Grok Global Search' using this timestamp.")
    print("=" * 70 + "\n")

def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--auto', action='store_true',
                        help='Use the built-in public Forex Factory feed instead of the RESEARCHED_EVENTS list. '
                             'Perfect for GitHub Actions / scheduled runs where there is no Grok to populate the list.')
    args = parser.parse_args()

    print("=== SR VAULT Weekly News Scan (Grok Global Search) ===\n")

    if args.auto:
        print("Running in --auto mode (public Forex Factory feed + filters).")
        events = fetch_forex_factory_this_week()
        clean_events = [e for e in events if is_gbpjpy_relevant(e.get("event", ""), e.get("currency", ""))]
        source = "Auto (Forex Factory + filters)"
    else:
        print("News is populated by Grok performing global web searches.")
        print("This script applies the researched events to the panel cache.\n")
        clean_events = [e for e in RESEARCHED_EVENTS if is_gbpjpy_relevant(e.get("event", ""), e.get("currency", ""))]
        source = "Grok Global Search"

    if not clean_events:
        print("No relevant events after filtering.")
        print("\nHow to update:")
        print("  • Ask Grok: \"do the weekly news scan\" (global search for your events)")
        print("  • Grok will research and edit the RESEARCHED_EVENTS list at the top of this file.")
        print("  • Or run with --auto to use the live public Forex Factory calendar.")
        print("  • Re-run: python sr_vault_news_scan.py   (or with --auto)")
        print("\nThe panel will load the updated roadmap from the cache (or the JSON you committed to the repo).")
        return

    cache = save_to_cache(clean_events, source=source)

    weeks_info = get_relevant_events_for_weeks(clean_events)
    print_roadmap_preview(weeks_info)

    print(f"Total relevant events written: {len(clean_events)}")
    for e in clean_events[:8]:
        print(f"  {e['date']} {e['time_utc']}  {e['currency']}  {e['event']}")

    print("\n" + "="*70)
    if args.auto:
        print("Scheduled / CI usage: the GitHub Action runs this with --auto on an hourly cron.")
        print("It commits the fresh JSON so the hosted panel (and your bot) always see current data.")
    else:
        print("Weekly routine:")
        print("  1. Tell Grok \"do the weekly news scan\" (global search)")
        print("  2. Grok updates RESEARCHED_EVENTS in this file with accurate dates/times")
        print("  3. Run: python sr_vault_news_scan.py")
        print("  4. Push the updated JSON (or let the GitHub Action do the heavy lifting).")
        print("  5. The panel (local or https://...github.io/...) shows the fresh roadmap.")
    print("="*70 + "\n")

if __name__ == "__main__":
    main()
