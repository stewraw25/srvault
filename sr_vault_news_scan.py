#!/usr/bin/env python3
"""
SR VAULT — Locked whitelist news engine (schedule + forecast/previous/actual)

Phase 1–3:
  1. Frozen whitelist — only events we trade on (GBPJPY / funded rules)
  2. Event model includes forecast / previous / actual + vs consensus
  3. Live actuals from TradingView economic calendar (free, no key);
     schedule + forecast also filled from the same feed when available.
     Forex Factory this-week JSON is a secondary fallback (forecast/previous).

Output: sr_vault_assets/news/myfxbook_news.json  (panel source of truth)

Run:
  python sr_vault_news_scan.py --auto
"""

from __future__ import annotations

import json
import os
import re
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

import requests

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
NEWS_DIR = os.path.join(SCRIPT_DIR, "sr_vault_assets", "news")
NEWS_CACHE_PATH = os.path.join(NEWS_DIR, "myfxbook_news.json")
FULL_CALENDAR_PATH = os.path.join(NEWS_DIR, "economic_calendar.json")
os.makedirs(NEWS_DIR, exist_ok=True)

# =============================================================================
# PHASE 1 — FROZEN WHITELIST (only these ever appear on SR Vault)
# =============================================================================
# day_color drives the panel bar: yellow | orange | red (red is mostly calendar EOM/EOQ)
# "election" is NOT a day colour. Major elections are a no-trade restriction that
# outranks GREEN / YELLOW / ORANGE / RED. The colours keep their own meaning.
# aliases are matched case-insensitively against provider titles.
# currency must match event currency (USD/GBP).

# Stewart, 2 Nov 2026. Shown in the legend; copied onto each election event.
ELECTION_RULE = (
    "Major elections (US midterms, US presidential, UK general election): "
    "NO TRADES from when the first polls close until the full result is in, "
    "then stay out for at least 24 hours after the full result."
)

WHITELIST: list[dict[str, Any]] = [
    # --- ORANGE: NFP ---
    {
        "id": "us_nfp",
        "display": "Non-Farm Payrolls (NFP)",
        "currency": "USD",
        "day_color": "orange",
        "aliases": [
            "non farm payrolls",
            "non-farm payrolls",
            "nonfarm payrolls",
            "nfp",
            "us nonfarm payrolls",
        ],
    },
    # --- ORANGE: BOE rate ---
    {
        "id": "boe_rate",
        "display": "BOE Interest Rate Decision",
        "currency": "GBP",
        "day_color": "orange",
        "aliases": [
            "boe interest rate decision",
            "bank of england interest rate decision",
            "bank of england mpc rate decision",
            "boe rate decision",
            "mpc rate decision",
        ],
        # Exclude vote tallies / minutes noise
        "exclude_if": [
            "vote",
            "minutes",
            "report",
            "consumer credit",
            "speech",
            "speak",
        ],
    },
    # --- YELLOW: US CPI ---
    {
        "id": "us_cpi_yoy",
        "display": "CPI y/y",
        "currency": "USD",
        "day_color": "yellow",
        "aliases": [
            "inflation rate yoy",
            "cpi y/y",
            "cpi (yoy)",
            "cpi yoy",
            "consumer price index yoy",
        ],
        "exclude_if": ["core", "median", "trimmed", "common", "national"],
    },
    {
        "id": "us_core_cpi_yoy",
        "display": "Core CPI y/y",
        "currency": "USD",
        "day_color": "yellow",
        "aliases": [
            "core inflation rate yoy",
            "core cpi y/y",
            "core cpi (yoy)",
            "core cpi yoy",
        ],
    },
    {
        "id": "us_cpi_mom",
        "display": "CPI m/m",
        "currency": "USD",
        "day_color": "yellow",
        "aliases": [
            "inflation rate mom",
            "cpi m/m",
            "cpi (mom)",
            "cpi mom",
        ],
        "exclude_if": ["core", "median", "trimmed", "common"],
    },
    {
        "id": "us_core_cpi_mom",
        "display": "Core CPI m/m",
        "currency": "USD",
        "day_color": "yellow",
        "aliases": [
            "core inflation rate mom",
            "core cpi m/m",
            "core cpi (mom)",
            "core cpi mom",
        ],
    },
    # --- YELLOW: UK inflation ---
    {
        "id": "uk_inflation_yoy",
        "display": "UK Inflation Rate",
        "currency": "GBP",
        "day_color": "yellow",
        "aliases": [
            "inflation rate yoy",
            "uk inflation rate",
            "cpi y/y",
            "cpi (yoy)",
            "cpi yoy",
        ],
        "exclude_if": ["core", "rpi", "ppi", "producer"],
    },
    {
        "id": "uk_core_cpi_yoy",
        "display": "Core CPI y/y",
        "currency": "GBP",
        "day_color": "yellow",
        "aliases": [
            "core inflation rate yoy",
            "core cpi y/y",
            "core cpi (yoy)",
            "core cpi yoy",
        ],
    },
    # --- YELLOW: FOMC rate (panel colour rules) ---
    {
        "id": "fed_rate",
        "display": "FOMC Interest Rate Decision",
        "currency": "USD",
        "day_color": "yellow",
        "aliases": [
            "fed interest rate decision",
            "fomc interest rate decision",
            "federal funds rate",
            "fed rate decision",
        ],
        "exclude_if": ["minutes", "speech", "speak", "press conference"],
    },
    # --- ELECTION (no-trade restriction, not a day colour) ---
    # Reusable kinds. A future election is a new ELECTION_WINDOWS row
    # (and a new kind here only if it is not one of these three).
    {
        "id": "us_midterms",
        "display": "US Midterms",
        "currency": "USD",
        "day_color": "",
        "event_type": "election",
        "election_kind": "us_midterms",
        "restriction": "no_trade",
        "hold_hours_after_result": 24,
        "aliases": [
            "us midterms",
            "us midterm elections",
            "us midterm election",
            "midterm elections",
            "midterm election",
        ],
        "exclude_if": ["presidential", "primary", "runoff"],
    },
    {
        "id": "us_presidential",
        "display": "US Presidential Election",
        "currency": "USD",
        "day_color": "",
        "event_type": "election",
        "election_kind": "us_presidential",
        "restriction": "no_trade",
        "hold_hours_after_result": 24,
        "aliases": [
            "us presidential election",
            "us presidential",
            "presidential election",
        ],
        "exclude_if": ["midterm", "primary"],
    },
    {
        "id": "uk_general_election",
        "display": "UK General Election",
        "currency": "GBP",
        "day_color": "",
        "event_type": "election",
        "election_kind": "uk_general",
        "restriction": "no_trade",
        "hold_hours_after_result": 24,
        "aliases": [
            "uk general election",
            "general election",
        ],
        "exclude_if": ["midterm", "presidential", "local", "primary"],
    },
]

# Official long-range schedule (authoritative dates from BLS / ONS / BOE / Fed calendars).
# Live feed overwrites forecast/previous/actual and can refine times; it must not invent
# non-whitelist event types.
AUTHORITATIVE_SCHEDULE: list[dict[str, Any]] = [
    # Past (kept briefly so "recent" results can still show)
    {
        "date": "2026-07-14",
        "time_utc": "12:30",
        "whitelist_id": "us_cpi_yoy",
        "source_url": "https://www.bls.gov/schedule/news_release/cpi.htm",
    },
    {
        "date": "2026-07-14",
        "time_utc": "12:30",
        "whitelist_id": "us_core_cpi_yoy",
        "source_url": "https://www.bls.gov/schedule/news_release/cpi.htm",
    },
    {
        "date": "2026-07-14",
        "time_utc": "12:30",
        "whitelist_id": "us_cpi_mom",
        "source_url": "https://www.bls.gov/schedule/news_release/cpi.htm",
    },
    {
        "date": "2026-07-14",
        "time_utc": "12:30",
        "whitelist_id": "us_core_cpi_mom",
        "source_url": "https://www.bls.gov/schedule/news_release/cpi.htm",
    },
    # Upcoming verified
    {
        "date": "2026-07-22",
        "time_utc": "06:00",
        "whitelist_id": "uk_inflation_yoy",
        "source_url": "https://www.ons.gov.uk/economy/inflationandpriceindices",
    },
    {
        "date": "2026-07-22",
        "time_utc": "06:00",
        "whitelist_id": "uk_core_cpi_yoy",
        "source_url": "https://www.ons.gov.uk/economy/inflationandpriceindices",
    },
    {
        "date": "2026-07-29",
        "time_utc": "18:00",
        "whitelist_id": "fed_rate",
        "source_url": "https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm",
    },
    {
        "date": "2026-07-30",
        "time_utc": "11:00",
        "whitelist_id": "boe_rate",
        "source_url": "https://www.bankofengland.co.uk/monetary-policy/upcoming-mpc-dates",
    },
    {
        "date": "2026-08-07",
        "time_utc": "12:30",
        "whitelist_id": "us_nfp",
        "source_url": "https://www.bls.gov/schedule/news_release/empsit.htm",
    },
    {
        "date": "2026-08-12",
        "time_utc": "12:30",
        "whitelist_id": "us_cpi_yoy",
        "source_url": "https://www.bls.gov/schedule/news_release/cpi.htm",
    },
    {
        "date": "2026-08-12",
        "time_utc": "12:30",
        "whitelist_id": "us_core_cpi_yoy",
        "source_url": "https://www.bls.gov/schedule/news_release/cpi.htm",
    },
    {
        "date": "2026-08-12",
        "time_utc": "12:30",
        "whitelist_id": "us_cpi_mom",
        "source_url": "https://www.bls.gov/schedule/news_release/cpi.htm",
    },
    {
        "date": "2026-08-12",
        "time_utc": "12:30",
        "whitelist_id": "us_core_cpi_mom",
        "source_url": "https://www.bls.gov/schedule/news_release/cpi.htm",
    },
    {
        "date": "2026-08-19",
        "time_utc": "06:00",
        "whitelist_id": "uk_inflation_yoy",
        "source_url": "https://www.ons.gov.uk/economy/inflationandpriceindices",
    },
    {
        "date": "2026-08-19",
        "time_utc": "06:00",
        "whitelist_id": "uk_core_cpi_yoy",
        "source_url": "https://www.ons.gov.uk/economy/inflationandpriceindices",
    },
]

# Major-election no-trade windows. One row per election.
# no_trade_dates must cover every calendar day from the first polls close
# through at least hold_hours_after_result after the expected full result.
# If the result slips (late Senate races, a hung parliament), extend
# no_trade_dates — the panel follows this list, it does not guess.
ELECTION_WINDOWS: list[dict[str, Any]] = [
    {
        "id": "us_midterms_2026",
        "whitelist_id": "us_midterms",
        # First US polls close ~23:00 GMT on Tuesday. The rest of Tuesday
        # before that is not yet a no-trade window.
        "polls_close_utc": "2026-11-03T23:00:00Z",
        "result_expected": "2026-11-04",
        "result_may_slip": True,
        "hold_hours_after_result": 24,
        # Tue from 23:00, all of Wed (expected result), all of Thu (24h after).
        # Fri NFP is intentionally outside this window.
        "no_trade_dates": ["2026-11-03", "2026-11-04", "2026-11-05"],
        "note": (
            "US midterms. NO TRADES from 23:00 GMT Tue 3 Nov 2026, when the first "
            "polls close, until the full result is in, then at least 24 hours after. "
            "The full result is expected Wed 4 Nov and may slip if Senate races are late. "
            "Marked no-trade: Tue 3 Nov from 23:00 GMT, Wed 4 Nov, Thu 5 Nov. "
            "Extends past Thu 5 if the full result is later than Wednesday."
        ),
        "source": "SR Vault election calendar",
        "source_url": "https://www.fec.gov/introduction-campaign-finance/election-results-and-voting-information/",
    },
]

# Fields copied verbatim when election rows merge. Empty day_color is deliberate.
ELECTION_FIELDS = (
    "event_type",
    "election_kind",
    "restriction",
    "no_trade_from_utc",
    "no_trade_dates",
    "result_expected",
    "result_may_slip",
    "hold_hours_after_result",
    "note",
    "rule",
)

WL_BY_ID = {w["id"]: w for w in WHITELIST}


def _norm(s: str) -> str:
    s = (s or "").lower()
    s = s.replace("–", "-").replace("—", "-")
    s = re.sub(r"\s+", " ", s).strip()
    return s


def match_whitelist(title: str, currency: str) -> Optional[dict[str, Any]]:
    """Return the whitelist entry if title+currency match, else None."""
    t = _norm(title)
    cur = (currency or "").upper()
    if cur in ("GB", "UK", "UNITED KINGDOM"):
        cur = "GBP"
    if cur in ("US", "USA", "UNITED STATES"):
        cur = "USD"

    candidates = []
    for w in WHITELIST:
        if w["currency"] != cur:
            continue
        excludes = [_norm(x) for x in w.get("exclude_if", [])]
        if any(x and x in t for x in excludes):
            continue
        # Core events must say core; non-core must not
        wants_core = "core" in w["id"] or any("core" in _norm(a) for a in w["aliases"])
        has_core = "core" in t
        if wants_core and not has_core:
            continue
        if (not wants_core) and has_core:
            continue
        for alias in w["aliases"]:
            a = _norm(alias)
            # Exact or alias contained in title — never title-contained-in-alias
            # (that made "Inflation Rate YoY" match "Core Inflation Rate YoY")
            if a == t or a in t:
                candidates.append((len(a), w))
                break
    if not candidates:
        return None
    candidates.sort(key=lambda x: -x[0])
    return candidates[0][1]


def fmt_num(val: Any, unit: str = "") -> str:
    if val is None or val == "":
        return ""
    if isinstance(val, (int, float)):
        # keep meaningful decimals
        if abs(val) >= 100:
            s = f"{val:.0f}" if float(val).is_integer() else f"{val:.1f}"
        else:
            s = f"{val:g}"
        if unit == "%":
            return f"{s}%"
        if unit and unit not in s:
            return f"{s}{unit}" if unit in ("K", "M", "B") else f"{s} {unit}".strip()
        return s
    return str(val).strip()


def parse_numeric(val: Any) -> Optional[float]:
    if val is None or val == "":
        return None
    if isinstance(val, (int, float)):
        return float(val)
    s = str(val).strip().replace(",", "")
    mult = 1.0
    if s.endswith("%"):
        s = s[:-1]
    if s.upper().endswith("K"):
        mult = 1_000
        s = s[:-1]
    elif s.upper().endswith("M"):
        mult = 1_000_000
        s = s[:-1]
    elif s.upper().endswith("B"):
        mult = 1_000_000_000
        s = s[:-1]
    try:
        return float(s) * mult
    except ValueError:
        return None


def vs_consensus(actual: Any, forecast: Any) -> dict[str, Any]:
    """Compute beat/miss/inline vs forecast."""
    a = parse_numeric(actual)
    f = parse_numeric(forecast)
    if a is None or f is None:
        return {
            "delta": None,
            "delta_display": "",
            "result": "",  # beat | miss | inline | ""
        }
    delta = a - f
    # tolerance for near-equal percentages
    if abs(delta) < 1e-9 or (abs(f) > 0 and abs(delta / max(abs(f), 1e-9)) < 1e-6):
        return {"delta": 0.0, "delta_display": "in line", "result": "inline"}
    # Display delta in same style as inputs when possible
    if isinstance(actual, str) and actual.endswith("%") or isinstance(forecast, str) and str(forecast).endswith("%"):
        d_disp = f"{delta:+.2f}%".replace("+", "+")
    elif abs(delta) >= 1000:
        d_disp = f"{delta:+,.0f}"
    else:
        d_disp = f"{delta:+g}"
    return {
        "delta": delta,
        "delta_display": d_disp,
        "result": "beat" if delta > 0 else "miss",
    }


def empty_event(wl: dict, date: str, time_utc: str, **extra) -> dict[str, Any]:
    return {
        "id": f"{wl['id']}_{date}",
        "whitelist_id": wl["id"],
        "date": date,
        "time_utc": time_utc,
        "event": wl["display"],
        "currency": wl["currency"],
        "impact": "HIGH",
        "day_color": wl["day_color"],
        "forecast": "",
        "previous": "",
        "actual": "",
        "delta": None,
        "delta_display": "",
        "result": "",
        "unit": "",
        "verified": True if extra.get("verified") else False,
        "source": extra.get("source", "SR Vault whitelist"),
        "source_url": extra.get("source_url", ""),
    }


def event_key(e: dict) -> tuple:
    return (e.get("date", ""), e.get("whitelist_id") or e.get("event", "").upper(), e.get("currency", ""))


# =============================================================================
# LIVE SOURCES
# =============================================================================

def fetch_tradingview(days_back: int = 5, days_forward: int = 50) -> list[dict]:
    """TradingView economic calendar — includes actual/forecast/previous when released."""
    now = datetime.now(timezone.utc)
    frm = (now - timedelta(days=days_back)).strftime("%Y-%m-%dT00:00:00.000Z")
    to = (now + timedelta(days=days_forward)).strftime("%Y-%m-%dT23:59:59.000Z")
    url = (
        "https://economic-calendar.tradingview.com/events"
        f"?from={frm}&to={to}&countries=US,GB&minImportance=0"
    )
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
        "Origin": "https://www.tradingview.com",
        "Referer": "https://www.tradingview.com/",
        "Accept": "application/json",
    }
    print(f"  Fetching TradingView calendar {frm[:10]} → {to[:10]} ...")
    try:
        resp = requests.get(url, headers=headers, timeout=25)
        if resp.status_code != 200:
            print(f"  TradingView HTTP {resp.status_code}")
            return []
        data = resp.json()
        raw = data.get("result") or []
        print(f"  TradingView returned {len(raw)} raw events")
        out = []
        for item in raw:
            title = (item.get("title") or item.get("indicator") or "").strip()
            country = (item.get("country") or item.get("currency") or "").strip()
            # map country codes
            if country in ("GB", "UK"):
                currency = "GBP"
            elif country in ("US",):
                currency = "USD"
            else:
                currency = country_to_currency(country)

            wl = match_whitelist(title, currency)
            if not wl:
                continue

            date_raw = item.get("date") or ""
            try:
                dt = datetime.fromisoformat(date_raw.replace("Z", "+00:00"))
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                utc = dt.astimezone(timezone.utc)
            except Exception:
                continue

            unit = item.get("unit") or ""
            actual = fmt_num(item.get("actual"), unit if item.get("actual") is not None else "")
            forecast = fmt_num(item.get("forecast"), unit if item.get("forecast") is not None else "")
            previous = fmt_num(item.get("previous"), unit if item.get("previous") is not None else "")
            # If raw already had % in unit, fmt_num handled it; if values are strings keep them
            if item.get("actual") is not None and not actual:
                actual = str(item.get("actual"))
            if item.get("forecast") is not None and not forecast:
                forecast = str(item.get("forecast"))
            if item.get("previous") is not None and not previous:
                previous = str(item.get("previous"))

            vs = vs_consensus(item.get("actual"), item.get("forecast"))
            if not vs["result"] and actual and forecast:
                vs = vs_consensus(actual, forecast)

            ev = empty_event(
                wl,
                utc.strftime("%Y-%m-%d"),
                utc.strftime("%H:%M"),
                source="TradingView economic calendar",
                source_url=item.get("source_url") or "",
                verified=True,
            )
            ev["actual"] = actual
            ev["forecast"] = forecast
            ev["previous"] = previous
            ev["unit"] = unit or ""
            ev["delta"] = vs["delta"]
            ev["delta_display"] = vs["delta_display"]
            ev["result"] = vs["result"]
            ev["provider_title"] = title
            out.append(ev)
        print(f"  Whitelist-matched from TradingView: {len(out)}")
        return out
    except Exception as e:
        print(f"  TradingView fetch error: {e}")
        return []


def country_to_currency(country: str) -> str:
    c = (country or "").upper()
    if "UNITED STATES" in c or c in ("US", "USA"):
        return "USD"
    if "UNITED KINGDOM" in c or c in ("UK", "GB", "GBP"):
        return "GBP"
    if "JAPAN" in c or c in ("JP", "JPY"):
        return "JPY"
    return c


def fetch_forex_factory() -> list[dict]:
    """Secondary source — schedule + forecast/previous (no actual in public feed)."""
    url = "https://nfs.faireconomy.media/ff_calendar_thisweek.json"
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
        "Accept": "application/json",
    }
    for attempt in range(2):
        try:
            print(f"  Fetching Forex Factory (attempt {attempt + 1})...")
            resp = requests.get(url, headers=headers, timeout=20)
            if resp.status_code != 200:
                print(f"  FF HTTP {resp.status_code}")
                time.sleep(1.5)
                continue
            raw = resp.json()
            out = []
            for item in raw:
                if not isinstance(item, dict):
                    continue
                title = (item.get("title") or "").strip()
                country = (item.get("country") or "").strip()
                currency = country_to_currency(country)
                # FF uses currency codes as country field (USD/GBP)
                if country in ("USD", "GBP", "JPY"):
                    currency = country
                wl = match_whitelist(title, currency)
                if not wl:
                    continue
                date_str = item.get("date") or ""
                try:
                    dt = datetime.fromisoformat(date_str)
                    if dt.tzinfo is not None:
                        utc = dt.astimezone(timezone.utc)
                    else:
                        utc = dt.replace(tzinfo=timezone.utc)
                except Exception:
                    continue
                forecast = (item.get("forecast") or "").strip()
                previous = (item.get("previous") or "").strip()
                actual = (item.get("actual") or "").strip()  # usually empty on this feed
                vs = vs_consensus(actual, forecast) if actual and forecast else {
                    "delta": None, "delta_display": "", "result": ""
                }
                ev = empty_event(
                    wl,
                    utc.strftime("%Y-%m-%d"),
                    utc.strftime("%H:%M"),
                    source="Forex Factory",
                    verified=True,
                )
                ev["forecast"] = forecast
                ev["previous"] = previous
                ev["actual"] = actual
                ev["delta"] = vs["delta"]
                ev["delta_display"] = vs["delta_display"]
                ev["result"] = vs["result"]
                ev["provider_title"] = title
                out.append(ev)
            print(f"  Whitelist-matched from FF: {len(out)}")
            return out
        except Exception as e:
            print(f"  FF error: {e}")
            time.sleep(1.5)
    return []


def load_previous_cache() -> list[dict]:
    if not os.path.exists(NEWS_CACHE_PATH):
        return []
    try:
        with open(NEWS_CACHE_PATH) as f:
            data = json.load(f)
        return data.get("events") or []
    except Exception:
        return []


def schedule_events() -> list[dict]:
    out = []
    for row in AUTHORITATIVE_SCHEDULE:
        wl = WL_BY_ID.get(row["whitelist_id"])
        if not wl:
            continue
        ev = empty_event(
            wl,
            row["date"],
            row["time_utc"],
            source=row.get("source") or "Official schedule (BLS/ONS/BOE/Fed)",
            source_url=row.get("source_url", ""),
            verified=True,
        )
        out.append(ev)
    return out


def _parse_utc(iso: str) -> datetime:
    dt = datetime.fromisoformat((iso or "").replace("Z", "+00:00"))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _dates_inclusive(start, end) -> list[str]:
    out = []
    day = start
    while day <= end:
        out.append(day.isoformat())
        day += timedelta(days=1)
    return out


def minimum_no_trade_dates(polls_close_utc: str, result_expected: str, hold_hours: int) -> list[str]:
    """Calendar days from first polls close through hold_hours after the expected result.

    The expected full result is treated as the end of result_expected (UTC).
    24 hours after the end of Wednesday is still Thursday, which is the
    minimum stay-out day.
    """
    start = _parse_utc(polls_close_utc).date()
    result_day = datetime.strptime(result_expected, "%Y-%m-%d").date()
    result_end = datetime(
        result_day.year, result_day.month, result_day.day, 23, 59, tzinfo=timezone.utc
    )
    until = (result_end + timedelta(hours=hold_hours)).date()
    if until < start:
        until = start
    return _dates_inclusive(start, until)


def build_election_events() -> list[dict]:
    """Expand ELECTION_WINDOWS into panel events. One event per election, reusable."""
    out = []
    for window in ELECTION_WINDOWS:
        wl = WL_BY_ID.get(window["whitelist_id"])
        if not wl or wl.get("event_type") != "election":
            raise ValueError(
                f"Election window {window.get('id')} must point at an election whitelist kind"
            )
        polls = window["polls_close_utc"]
        dt = _parse_utc(polls)
        hold = int(window.get("hold_hours_after_result") or wl.get("hold_hours_after_result") or 24)
        dates = list(window.get("no_trade_dates") or [])
        if window.get("result_expected"):
            required = minimum_no_trade_dates(polls, window["result_expected"], hold)
            missing = [d for d in required if d not in dates]
            if missing:
                raise ValueError(
                    f"{window['id']} no_trade_dates missing {missing} "
                    f"(need polls close through {hold}h after the expected result)"
                )
        if not dates:
            raise ValueError(f"{window['id']} needs no_trade_dates")
        ev = empty_event(
            wl,
            dt.strftime("%Y-%m-%d"),
            dt.strftime("%H:%M"),
            source=window.get("source") or "SR Vault election calendar",
            source_url=window.get("source_url", ""),
            verified=True,
        )
        ev["id"] = window["id"]
        # Not a day colour. Restriction is applied beside GREEN/YELLOW/ORANGE/RED.
        ev["day_color"] = ""
        ev["event_type"] = "election"
        ev["election_kind"] = wl.get("election_kind") or wl["id"]
        ev["restriction"] = "no_trade"
        ev["no_trade_from_utc"] = dt.strftime("%Y-%m-%dT%H:%M:%SZ")
        ev["no_trade_dates"] = dates
        ev["result_expected"] = window.get("result_expected") or ""
        ev["result_may_slip"] = bool(window.get("result_may_slip"))
        ev["hold_hours_after_result"] = hold
        ev["note"] = window.get("note") or ELECTION_RULE
        ev["rule"] = ELECTION_RULE
        out.append(ev)
    return out


def apply_election_fields(base: dict, src: dict) -> None:
    """Election stays a restriction. It must not be stored as a day colour."""
    if src.get("event_type") != "election":
        return
    base["event_type"] = "election"
    base["day_color"] = ""
    base["restriction"] = src.get("restriction") or "no_trade"
    base["rule"] = src.get("rule") or ELECTION_RULE
    for field in ELECTION_FIELDS:
        if field in ("event_type", "restriction", "rule"):
            continue
        val = src.get(field)
        if field == "no_trade_dates":
            if val:
                base["no_trade_dates"] = list(val)
            continue
        if field == "result_may_slip":
            if "result_may_slip" in src:
                base["result_may_slip"] = bool(src.get("result_may_slip"))
            continue
        if val not in (None, ""):
            base[field] = val


def merge_events(*lists: list[dict]) -> list[dict]:
    """
    Merge by (date, whitelist_id, currency).
    Later lists overlay earlier ones. Non-empty actual/forecast/previous from a later
    source always win (so live TradingView overwrites stale cache).
    """
    merged: dict[tuple, dict] = {}
    for lst in lists:
        for e in lst:
            # ensure whitelist_id
            if not e.get("whitelist_id"):
                wl = match_whitelist(e.get("event", ""), e.get("currency", ""))
                if not wl:
                    continue
                e = {**e, "whitelist_id": wl["id"], "event": wl["display"], "day_color": wl["day_color"]}
                if wl.get("event_type") == "election":
                    e["event_type"] = "election"
                    e["day_color"] = ""
            key = event_key(e)
            if key not in merged:
                merged[key] = dict(e)
                continue
            base = merged[key]
            for field in ("actual", "forecast", "previous", "time_utc", "source_url", "unit", "provider_title"):
                val = e.get(field)
                if val not in (None, ""):
                    # later non-empty always wins for data fields
                    base[field] = val
            if e.get("source") and (e.get("actual") or e.get("forecast") or e.get("previous") or e.get("source", "").startswith("TradingView")):
                base["source"] = e["source"]
            if e.get("verified"):
                base["verified"] = True
            # A colour overlay must not paint an election, and an election must not
            # paint a colour event. Same key means same whitelist id, so this is safe.
            if e.get("event_type") == "election" or base.get("event_type") == "election":
                apply_election_fields(base, e if e.get("event_type") == "election" else base)
            elif e.get("day_color"):
                base["day_color"] = e["day_color"]
            if e.get("event"):
                base["event"] = e["event"]
            # recompute vs consensus after overlay
            vs = vs_consensus(base.get("actual"), base.get("forecast"))
            base["delta"] = vs["delta"]
            base["delta_display"] = vs["delta_display"]
            base["result"] = vs["result"]
            merged[key] = base

    events = list(merged.values())
    # Drop very old (> 21 days) to keep panel clean.
    # An election stays while any marked no-trade day is still inside the window.
    cutoff = (datetime.now().date() - timedelta(days=21)).isoformat()

    def _still_relevant(e: dict) -> bool:
        dates = [e.get("date", "")]
        if e.get("event_type") == "election":
            dates.extend(e.get("no_trade_dates") or [])
        return any(d and d >= cutoff for d in dates)

    events = [e for e in events if _still_relevant(e)]
    events.sort(key=lambda x: (x.get("date", ""), x.get("time_utc", ""), x.get("event", "")))
    return events


def save_cache(events: list[dict], source: str) -> dict:
    whitelist_summary = []
    for w in WHITELIST:
        row = {
            "id": w["id"],
            "display": w["display"],
            "currency": w["currency"],
            "day_color": w["day_color"],
        }
        # Colour rows stay as they were. Only election kinds carry the extra type.
        if w.get("event_type") == "election":
            row["event_type"] = "election"
            row["election_kind"] = w.get("election_kind") or w["id"]
            row["restriction"] = "no_trade"
            row["rule"] = ELECTION_RULE
        whitelist_summary.append(row)
    cache = {
        "last_fetched": datetime.now().isoformat(),
        "source": source,
        "schema_version": 2,
        "whitelist": whitelist_summary,
        "events": events,
    }
    with open(NEWS_CACHE_PATH, "w") as f:
        json.dump(cache, f, indent=2)
        f.write("\n")
    with open(FULL_CALENDAR_PATH, "w") as f:
        json.dump(cache, f, indent=2)
        f.write("\n")
    return cache


def print_preview(events: list[dict]) -> None:
    today = datetime.now().date().isoformat()
    print("\n" + "=" * 72)
    print("SR VAULT NEWS PREVIEW (whitelist only)")
    print("=" * 72)
    print(f"Today: {today}  |  events: {len(events)}")
    for e in events:
        mark = ""
        if e.get("event_type") == "election":
            days = ", ".join(e.get("no_trade_dates") or [])
            mark = f"  NO-TRADE {days} from {e.get('no_trade_from_utc') or e.get('time_utc')}"
        elif e.get("actual"):
            mark = f"  ACTUAL={e['actual']}  FC={e.get('forecast') or '—'}  → {e.get('delta_display') or e.get('result') or ''}"
        elif e.get("forecast"):
            mark = f"  FC={e['forecast']}  PREV={e.get('previous') or '—'}"
        print(
            f"  {e['date']} {e.get('time_utc','')}  {e['currency']:3}  "
            f"[{e.get('day_color','?'):6}]  {e['event']}{mark}"
        )
    print("=" * 72)
    print("Wrote:", NEWS_CACHE_PATH)
    print()


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="SR Vault locked-whitelist news engine")
    parser.add_argument("--auto", action="store_true", help="Fetch live sources + merge schedule")
    args = parser.parse_args()

    print("=== SR VAULT News Engine (whitelist + actuals) ===\n")
    print(f"Whitelist size: {len(WHITELIST)} event types (frozen)")

    base = schedule_events()
    prev = load_previous_cache()
    # only keep previous if they still match whitelist
    prev_clean = []
    for e in prev:
        wl = match_whitelist(e.get("event", ""), e.get("currency", ""))
        if wl:
            e = dict(e)
            e["whitelist_id"] = wl["id"]
            e["event"] = e.get("event") or wl["display"]
            if wl.get("event_type") == "election":
                # Keep the restriction off the colour field so a rerun cannot
                # turn an election into GREEN/YELLOW/ORANGE/RED.
                e["event_type"] = "election"
                e["day_color"] = ""
                e["election_kind"] = wl.get("election_kind") or e.get("election_kind") or wl["id"]
                e["restriction"] = "no_trade"
                e["rule"] = e.get("rule") or ELECTION_RULE
            else:
                e["day_color"] = wl["day_color"]
            prev_clean.append(e)

    live_tv: list[dict] = []
    live_ff: list[dict] = []
    if args.auto:
        live_tv = fetch_tradingview()
        live_ff = fetch_forex_factory()
        source = "TradingView (actuals/forecast) + Official schedule + FF fallback"
    else:
        source = "Official schedule + previous cache (no live fetch)"

    # Elections last so the window in this file wins over a stale cache copy.
    # Merge priority: schedule → previous cache → FF → TV → election windows
    elections = build_election_events()
    events = merge_events(base, prev_clean, live_ff, live_tv, elections)

    if not events:
        print("No events after merge — check network / whitelist.")
        return

    save_cache(events, source=source)
    print_preview(events)
    print("Done. Panel loads this JSON automatically.")


if __name__ == "__main__":
    main()
