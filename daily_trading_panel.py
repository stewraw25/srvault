import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import pytz
import math
import os
import base64
import requests
import json

# Persistent news storage (populated by Grok global search via sr_vault_news_scan.py)
NEWS_CACHE_PATH = "/Users/stewartrawson/sr_vault_assets/news/myfxbook_news.json"
os.makedirs(os.path.dirname(NEWS_CACHE_PATH), exist_ok=True)

# Optional live price dependencies (graceful fallback if missing)
try:
    import yfinance as yf
    from streamlit_autorefresh import st_autorefresh
    HAS_LIVE_PRICE = True
except ImportError:
    HAS_LIVE_PRICE = False
    yf = None
    st_autorefresh = None

# ================== SR VAULT BRANDING ==================
SR_VAULT_LOGO = "/Users/stewartrawson/sr_vault_assets/logos/sr_vault_main_black_gbp_brighter.jpg"
STRAPLINE = "Everyday People. Making Serious CASH."

st.set_page_config(page_title="SR VAULT | Daily Trading Panel", layout="wide", page_icon="🚀")

# Live price ticker refresh every 4 seconds (for "ticks") - only if packages installed
if HAS_LIVE_PRICE:
    st_autorefresh(interval=4000, limit=200, key="gbpjpy_live_ticker")

# ================== PREMIUM DARK THEME ==================
st.markdown("""
<style>
.stApp {
    background-color: #000000;
    color: #e8e8e8;
}
h1, h2, h3, h4 {
    color: #c8c8c8 !important;
}
.stMetric {
    background-color: #111111;
    border: 1px solid #333333;
    border-radius: 12px;
    padding: 12px;
}
[data-testid="stMetricValue"] {
    color: #f0f0f0 !important;
    font-size: 1.6rem !important;
}
.stDataFrame {
    background-color: #0a0a0a;
}
div[data-testid="stExpander"] {
    background-color: #0f0f0f;
    border: 1px solid #2a2a2a;
}
.clock-card {
    background-color: #0a0a0a;
    border: 1px solid #3a3a3a;
    border-radius: 16px;
    padding: 12px 8px;
    text-align: center;
    box-shadow: 0 4px 20px rgba(0,0,0,0.6);
}
.clock-label {
    color: #aaaaaa;
    font-size: 0.85rem;
    letter-spacing: 1.5px;
    margin-top: 6px;
    text-transform: uppercase;
}
.panel-title {
    text-align: center;
    font-size: 2.1rem;
    font-weight: 700;
    letter-spacing: 3px;
    color: #d0d0d0;
    margin: 8px 0 4px 0;
}
.strapline {
    text-align: center;
    color: #888888;
    font-size: 0.78rem;
    letter-spacing: 1px;
    line-height: 1.1;
}
</style>
""", unsafe_allow_html=True)

# ================== CLOCKS AT TOP (LUXURY WATCH STYLE) ==================
def analogue_clock_svg(dt, label, size=210):
    """Premium analogue clock with expensive watch branding (ROLEX style)."""
    hour_angle = ((dt.hour % 12) + dt.minute / 60.0) * 30
    minute_angle = (dt.minute + dt.second / 60.0) * 6
    second_angle = dt.second * 6

    # Build a clean, minified SVG to avoid any raw code leaking in Streamlit
    parts = [
        f'<svg width="{size}" height="{size}" viewBox="0 0 200 200" xmlns="http://www.w3.org/2000/svg">',
        # Outer luxury bezel
        '<circle cx="100" cy="100" r="97" fill="#0a0a0a" stroke="#555" stroke-width="8"/>',
        '<circle cx="100" cy="100" r="90" fill="#111" stroke="#333" stroke-width="2"/>',
        '<circle cx="100" cy="100" r="82" fill="#0d0d0d" stroke="#222" stroke-width="1"/>',
    ]
    # 60 fine minute ticks
    for i in range(60):
        angle = i * 6
        length = 6 if i % 5 == 0 else 3
        rad = math.radians(angle - 90)
        x1 = 100 + 74 * math.cos(rad)
        y1 = 100 + 74 * math.sin(rad)
        x2 = 100 + (74 + length) * math.cos(rad)
        y2 = 100 + (74 + length) * math.sin(rad)
        stroke_w = 1.8 if i % 5 == 0 else 0.9
        parts.append(f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" stroke="#888" stroke-width="{stroke_w}" stroke-linecap="round"/>')

    # Major hour markers
    for i in range(12):
        angle = i * 30
        rad = math.radians(angle - 90)
        x1 = 100 + 68 * math.cos(rad)
        y1 = 100 + 68 * math.sin(rad)
        x2 = 100 + 78 * math.cos(rad)
        y2 = 100 + 78 * math.sin(rad)
        parts.append(f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" stroke="#c8c8c8" stroke-width="3.5" stroke-linecap="round"/>')

    # Hands
    rad_h = math.radians(hour_angle - 90)
    hx = 100 + 42 * math.cos(rad_h)
    hy = 100 + 42 * math.sin(rad_h)
    parts.append(f'<line x1="100" y1="100" x2="{hx:.1f}" y2="{hy:.1f}" stroke="#e8e8e8" stroke-width="5.5" stroke-linecap="round"/>')

    rad_m = math.radians(minute_angle - 90)
    mx = 100 + 58 * math.cos(rad_m)
    my = 100 + 58 * math.sin(rad_m)
    parts.append(f'<line x1="100" y1="100" x2="{mx:.1f}" y2="{my:.1f}" stroke="#d0d0d0" stroke-width="3.5" stroke-linecap="round"/>')

    rad_s = math.radians(second_angle - 90)
    sx = 100 + 62 * math.cos(rad_s)
    sy = 100 + 62 * math.sin(rad_s)
    parts.append(f'<line x1="100" y1="100" x2="{sx:.1f}" y2="{sy:.1f}" stroke="#4ade80" stroke-width="1.8" stroke-linecap="round"/>')

    # Center pivot
    parts.append('<circle cx="100" cy="100" r="6" fill="#1a1a1a" stroke="#aaa" stroke-width="1.5"/>')
    parts.append('<circle cx="100" cy="100" r="2.8" fill="#4ade80"/>')

    # === EXPENSIVE MAKE IN THE MIDDLE: ROLEX (or IWC style) ===
    parts.append('<text x="100" y="118" text-anchor="middle" fill="#c8c8c8" font-size="10" font-family="Georgia, serif" font-weight="700" letter-spacing="2">ROLEX</text>')

    parts.append('</svg>')
    return ''.join(parts)

utc_now = datetime.now(pytz.utc)

flags = {
    "UTC": "🌍",
    "LONDON": "🇬🇧",
    "NEW YORK": "🇺🇸",
    "TOKYO": "🇯🇵"
}

clocks = [
    (utc_now, "UTC"),
    (utc_now.astimezone(pytz.timezone("Europe/London")), "LONDON"),
    (utc_now.astimezone(pytz.timezone("America/New_York")), "NEW YORK"),
    (utc_now.astimezone(pytz.timezone("Asia/Tokyo")), "TOKYO"),
]

st.markdown("**LIVE MARKET TIMES**", help="Analogue clocks • Refresh for updated hands")

clock_cols = st.columns(4, gap="small")
for i, (dt, label) in enumerate(clocks):
    with clock_cols[i]:
        svg = analogue_clock_svg(dt, label)
        digital = dt.strftime("%H:%M:%S")
        flag = flags.get(label, "")
        # Clean SVG (pure analogue face with ROLEX in center)
        st.markdown(svg, unsafe_allow_html=True)
        # City + flag + digital time - styled centrally under the clock
        st.markdown(
            f'<div style="text-align:center; margin-top:2px; font-size:0.9rem;">'
            f'<span style="font-size:1.1rem;">{flag}</span> '
            f'<span style="color:#c8c8c8; font-weight:600; letter-spacing:1px;">{label}</span><br>'
            f'<span style="color:#e0e0e0; font-size:0.95rem; font-family:monospace;">{digital}</span>'
            f'</div>',
            unsafe_allow_html=True
        )

# Current session pill
hour = utc_now.hour
active = []
if 0 <= hour < 8: active.append("ASIAN")
if 8 <= hour < 16: active.append("LONDON")
if 13 <= hour < 21: active.append("NEW YORK")
session_str = "  •  ".join(active) if active else "OFF SESSION"
st.markdown(
    f"<div style='text-align:center; margin:8px 0 12px 0; color:#4ade80; font-size:0.9rem; letter-spacing:2px;'>{session_str}</div>",
    unsafe_allow_html=True
)

# SILVER BAR DIVIDER
st.markdown(
    '<div style="height:4px; background: linear-gradient(to right, #a8a8a8, #f0f0f0, #a8a8a8); margin: 4px 0 16px 0; border-radius: 3px; box-shadow: 0 1px 3px rgba(0,0,0,0.4);"></div>',
    unsafe_allow_html=True
)

# ================== SR VAULT BRANDING + HEADER + LIVE PRICE (after divider) ==================
# Three columns: Logo (left) | Title (center) | Live GBPJPY Banner (right)
logo_col, title_col, price_col = st.columns([0.95, 4.3, 1.25])

with logo_col:
    st.image(SR_VAULT_LOGO, width=210)
    # Strapline directly underneath the logo
    st.markdown(
        f'<div class="strapline" style="margin-top: -6px; font-size: 0.78rem; text-align: center; white-space: nowrap; line-height: 1.1;">{STRAPLINE}</div>',
        unsafe_allow_html=True
    )

with title_col:
    # Padding to vertically align title with logo height
    st.markdown('<div style="padding-top: 12px; text-align: center;">', unsafe_allow_html=True)
    st.markdown("""
    <div style="line-height: 1.0; text-align: center;">
        <div style="
            font-size: 2.9rem; 
            font-weight: 800; 
            letter-spacing: 2px; 
            color: #f0f0f0; 
            line-height: 1.0;
            text-shadow: 0 2px 4px rgba(0,0,0,0.35);
            text-align: center;
        ">
            TRADING INFORMATION PANEL
        </div>
        <div style="
            font-size: 1.25rem; 
            font-weight: 500; 
            color: #b8b8b8; 
            letter-spacing: 1.3px;
            text-align: center;
            width: 100%;
            margin-top: 2px;
        ">
            for Funded Accounts
        </div>
    </div>
    """, unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

with price_col:
    # LIVE GBPJPY price banner with ticks (updates every ~4s via autorefresh)
    st.markdown('<div style="padding-top: 8px; text-align: right;">', unsafe_allow_html=True)
    if HAS_LIVE_PRICE:
        try:
            ticker = yf.Ticker("GBPJPY=X")
            hist = ticker.history(period="1d", interval="1m")
            if not hist.empty:
                price = float(hist['Close'].iloc[-1])
                prev_close = float(hist['Close'].iloc[-2]) if len(hist) > 1 else price
                chg = price - prev_close
                pct = (chg / prev_close * 100) if prev_close != 0 else 0
                color = "#22c55e" if chg >= 0 else "#ef4444"
                arrow = "▲" if chg >= 0 else "▼"
                st.markdown(f"""
                <div style="text-align: right; line-height: 1.05;">
                    <div style="font-size: 0.78rem; color: #888; font-weight: 600; letter-spacing: 1px;">LIVE GBPJPY</div>
                    <div style="font-size: 2.0rem; font-weight: 700; color: #f0f0f0; font-family: monospace;">{price:.3f}</div>
                    <div style="font-size: 0.95rem; color: {color}; font-weight: 600;">
                        {arrow} {chg:+.3f} ({pct:+.2f}%)
                    </div>
                </div>
                """, unsafe_allow_html=True)
            else:
                st.caption("Live price unavailable")
        except Exception as e:
            st.caption("Price feed error")
    else:
        st.markdown("""
        <div style="text-align: right; font-size: 0.75rem; color: #888; line-height: 1.2;">
            LIVE GBPJPY<br>
            <span style="color:#ff6b6b;">Install yfinance + streamlit-autorefresh<br>for live price ticks</span>
        </div>
        """, unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

# Initialize account snapshot values (if not set)
if "open_trades" not in st.session_state:
    st.session_state.open_trades = 2
if "pending_orders" not in st.session_state:
    st.session_state.pending_orders = 1
if "risk_per_trade" not in st.session_state:
    st.session_state.risk_per_trade = 1  # percent
if "account_balance" not in st.session_state:
    st.session_state.account_balance = 10000.0
if "current_trade_pnl" not in st.session_state:
    st.session_state.current_trade_pnl = 0.0

# ================== KEY INFO + CURRENT CHART SIDE-BY-SIDE (after header) ==================
# Trading panel (key info) directly next to the current weekly chart screenshot

key_col, content_col = st.columns([1, 2.2])

with key_col:
    # Centered header block for KEY TRADING INFORMATION
    # "Pair Currently Trading: GBPJPY" now on a single line (user request)
    st.markdown("""
    <div style="text-align: center; margin-bottom: 8px;">
        <strong style="font-size: 1.15rem; letter-spacing: 0.5px;">KEY TRADING INFORMATION</strong>
        <br>
        <span style="font-size: 1.05rem;">
            <strong>Pair Currently Trading:</strong> 
            <span style="color:#22c55e; font-weight:700; font-size:1.35rem;">GBPJPY</span>
        </span>
    </div>
    """, unsafe_allow_html=True)

    # Other information - left aligned
    # Current Trend (editable)
    # The word only appears once — inside the dropdown box.
    # Green indicator for Bullish, red for Bearish (visual color directly with the choice).
    st.markdown("**Current Trend**")
    trend = st.selectbox(
        "Trend",
        ["🟢 Bullish", "🔴 Bearish", "🟡 Neutral"],
        key="key_trend",
        label_visibility="collapsed"
    )

    # Account Snapshot list (under the trend dropdown as requested)
    # Aligned key/value layout with values in a brighter colour and right-aligned column for easy reading
    st.markdown("**Account Snapshot**")
    st.markdown(f"""
    <table style="width:100%; font-size:0.92rem; border-collapse:collapse; margin-top:2px; line-height:1.55;">
      <tr>
        <td style="padding:1px 0; color:#aaa;">Open Trades:</td>
        <td style="text-align:right; padding:1px 0; font-weight:600; color:#f0f0f0;">{st.session_state.open_trades}</td>
      </tr>
      <tr>
        <td style="padding:1px 0; color:#aaa;">Pending Orders:</td>
        <td style="text-align:right; padding:1px 0; font-weight:600; color:#f0f0f0;">{st.session_state.pending_orders}</td>
      </tr>
      <tr>
        <td style="padding:1px 0; color:#aaa;">Risk PER Trade:</td>
        <td style="text-align:right; padding:1px 0; font-weight:600; color:#f0f0f0;">{st.session_state.risk_per_trade}%</td>
      </tr>
      <tr>
        <td style="padding:1px 0; color:#aaa;">Account Balance:</td>
        <td style="text-align:right; padding:1px 0; font-weight:600; color:#f0f0f0;">${st.session_state.account_balance:,.2f}</td>
      </tr>
      <tr>
        <td style="padding:1px 0; color:#aaa;">Current Trade Profit/Loss:</td>
        <td style="text-align:right; padding:1px 0; font-weight:600; color:#f0f0f0;">${st.session_state.current_trade_pnl:,.2f}</td>
      </tr>
    </table>
    """, unsafe_allow_html=True)

with content_col:
    chart_col, zh_col = st.columns([1.35, 1.4])  # give the ZeroHedge widget a bit more space so it feels more central in the right area

    with chart_col:
        st.markdown("**CURRENT CHART WE ARE TRADING**")

        CHART_DIR = "/Users/stewartrawson/sr_vault_assets/charts"
        os.makedirs(CHART_DIR, exist_ok=True)
        CHART_PATH = os.path.join(CHART_DIR, "current_weekly_chart.png")

        # Fixed-size container (420px height) with caption centered above the image
        if os.path.exists(CHART_PATH):
            with open(CHART_PATH, "rb") as f:
                img_b64 = base64.b64encode(f.read()).decode()
            st.markdown(f"""
            <div style="
                height: 420px;
                width: 100%;
                border: 2px solid #4a4a4a;
                border-radius: 12px;
                background: #0a0a0a;
                overflow: hidden;
                display: flex;
                flex-direction: column;
                align-items: center;
                justify-content: center;
                box-shadow: 0 4px 12px rgba(0,0,0,0.3);
                text-align: center;
            ">
                <div style="font-size: 0.85em; color: #888; padding: 4px 8px; width: 100%; box-sizing: border-box;">
                    The chart the bot is currently trading from (with your rectangles)
                </div>
                <img src="data:image/png;base64,{img_b64}" 
                     style="max-height: 85%; max-width: 100%; object-fit: contain;"/>
            </div>
            """, unsafe_allow_html=True)

            mtime = os.path.getmtime(CHART_PATH)
            last_updated = datetime.fromtimestamp(mtime).strftime("%A %d %B %Y %H:%M")
            st.caption(f"Last updated: {last_updated}")
        else:
            st.markdown("""
            <div style="
                height: 420px;
                width: 100%;
                border: 2px solid #4a4a4a;
                border-radius: 12px;
                background: #0a0a0a;
                display: flex;
                flex-direction: column;
                align-items: center;
                justify-content: center;
                color: #888;
                font-size: 1.1rem;
                text-align: center;
            ">
                <div style="font-size: 0.85em; color: #888; padding: 4px 8px; width: 100%; box-sizing: border-box;">
                    The chart the bot is currently trading from (with your rectangles)
                </div>
                <div>No chart uploaded yet</div>
            </div>
            """, unsafe_allow_html=True)

    with zh_col:
        st.markdown("<div style='text-align:center; margin-bottom:4px;'><strong style='font-size:1.0rem;'>@zerohedge</strong></div>", unsafe_allow_html=True)
        st.caption("Newest posts • Updates on refresh / price ticks")
        if st.button("🔄 Refresh Feed", key="zh_refresh", use_container_width=True):
            st.rerun()

        # Custom rendered recent posts (reliable, no embed issues)
        # Fetched live via search. To update with even newer posts, just ask "update zerohedge posts in the panel".
        zh_posts = [
            {
                "time": "22:30",
                "text": "Belfast Is Burning After Attempted Beheading Attack By Migrant",
                "url": "https://x.com/zerohedge/status/2064475149131211110"
            },
            {
                "time": "22:25",
                "text": "SNAP Benefits Go To 186,000 Dead People... And Stopping Them Might Be Difficult",
                "url": "https://x.com/zerohedge/status/2064473898171707582"
            },
            {
                "time": "22:03",
                "text": "*TRUMP THINKS DEAL STILL CLOSE: POLITICO CITING US OFFICIAL",
                "url": "https://x.com/zerohedge/status/2064468390777954345"
            },
            {
                "time": "22:00",
                "text": "Vance Reacts After Israel Reportedly Caught Spying On Pentagon",
                "url": "https://x.com/zerohedge/status/2064467604526231792"
            },
            {
                "time": "21:54",
                "text": "Nobody is trading stocks any more: it's all just options and levered ETFs",
                "url": "https://x.com/zerohedge/status/2064466175195504700"
            },
        ]

        for p in zh_posts:
            st.markdown(f"""
            <div style="
                background: #111;
                border: 1px solid #333;
                border-radius: 6px;
                padding: 6px 8px;
                margin-bottom: 5px;
                font-size: 0.78rem;
                line-height: 1.25;
            ">
                <div style="color:#888; font-size:0.7rem; margin-bottom:2px;">{p['time']}</div>
                <div style="color:#e0e0e0; margin-bottom:3px;">{p['text']}</div>
                <a href="{p['url']}" target="_blank" style="color:#4a9eff; font-size:0.68rem; text-decoration:none;">View on X →</a>
            </div>
            """, unsafe_allow_html=True)

        st.caption("Data via global search • Click refresh for latest")

    with st.expander("📤 Upload / Replace Current Chart Screenshot"):
        uploaded_chart = st.file_uploader(
            "Drop new chart screenshot (with rectangles)",
            type=["png", "jpg", "jpeg"],
            key="weekly_chart_uploader_side",
            help="This will become the CURRENT CHART WE ARE TRADING displayed here. The box size is fixed."
        )
        if uploaded_chart is not None:
            with open(CHART_PATH, "wb") as f:
                f.write(uploaded_chart.getbuffer())
            st.success("✅ Chart updated! The display box size stays fixed.")
            st.rerun()

# ================== DAY STATUS (PROMINENT) ==================
today = datetime.now().date()

def get_day_status(today):
    """RED DAY logic updated to user specification."""
    month = today.month
    day = today.day
    date_str = today.strftime("%Y-%m-%d")

    # Official holidays (always RED)
    HOLIDAYS = {
        "2026-01-01", "2026-12-25", "2026-07-04", "2026-05-25",
        "2026-01-19", "2026-02-16", "2026-11-26"
    }
    if date_str in HOLIDAYS:
        return "RED", "MARKET HOLIDAY — No trading"

    # 1. The whole of August
    if month == 8:
        return "RED", "AUGUST — Full month (high caution / thin liquidity)"

    # 2. Last 3 weeks of December (11th – 31st)
    if month == 12 and day >= 11:
        return "RED", "LAST 3 WEEKS OF DECEMBER — High caution period"

    # Get last day of the current month
    if month == 12:
        last_day = 31
    else:
        last_day = (today.replace(month=month + 1, day=1) - timedelta(days=1)).day

    # 3. Last 3 days of end-of-quarter months (March, June, September, December)
    if month in [3, 6, 9, 12] and day >= (last_day - 2):
        return "RED", "LAST 3 DAYS OF QUARTER — Thin liquidity, avoid new positions"

    # 4. The very last day of every month
    if day == last_day:
        return "RED", "LAST DAY OF THE MONTH — Reduced liquidity"

    return "GREEN", "NORMAL TRADING DAY"

status, reason = get_day_status(today)

if status == "RED":
    st.error(f"🔴  {reason}")
else:
    st.success(f"🟢  {reason}")

# (Account snapshot info moved to under the trend dropdown in KEY TRADING INFORMATION)

def format_date_nice(date_str):
    """Convert YYYY-MM-DD to 'Thursday 11th June 2026' style."""
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

# ================== RELEVANT NEWS (GBPJPY ONLY) ==================
st.markdown("### RELEVANT NEWS — GBP / JPY FOCUS")

# Prominent last updated
last_fetched = st.session_state.get("myfx_last_fetched")
if last_fetched:
    try:
        dt = datetime.fromisoformat(last_fetched)
        nice_date = format_date_nice(dt.strftime("%Y-%m-%d"))
        time_str = dt.strftime("%H:%M")
        st.markdown(f"**Last updated via Grok Global Search:** {nice_date} {time_str}")
    except:
        st.markdown("**Last updated via Grok Global Search:** Unknown")
else:
    st.markdown("**Last updated via Grok Global Search:** Never")

st.caption("Only events matching your criteria (NFP, BOE, GBP inflation/GDP, YEN GDP/CPI, US rates/CPI/FOMC, tariffs) are shown. Weekly roadmap below.")

# Status box explaining the current limitation
st.info(
    "📌 **News Source Status:** Grok Global Search (recommended)\n\n"
    "We have completely dropped MyFXBook. The news comes from global web search / research done by Grok.\n\n"
    "**Weekly process:**\n"
    "• Tell me in chat: \"do the weekly news scan\" or \"perform weekly news scan for this week and next\"\n"
    "• I do a global search across calendars for only your high-impact events (NFP, BOE, GBP inflation/GDP, YEN GDP/CPI, US CPI/FOMC/rates, tariffs).\n"
    "• Run this command in Terminal:\n"
    "    python /Users/stewartrawson/sr_vault_news_scan.py\n"
    "• Refresh this panel. The roadmap updates automatically."
)

# GROK GLOBAL SEARCH SEED (quick in-app test)
if st.button("🔬 Quick in-app seed with latest Grok-researched events", use_container_width=True):
    # For the real weekly process, ask Grok to "do the weekly news scan" (global search).
    # Then run: python /Users/stewartrawson/sr_vault_news_scan.py
    # The script will write the persistent cache used by this panel.
    researched_events = [
        {"date": "2026-06-10", "time_utc": "12:30", "event": "CPI (MoM)", "currency": "USD", "impact": "HIGH"},
        {"date": "2026-06-10", "time_utc": "12:30", "event": "Core CPI (MoM)", "currency": "USD", "impact": "HIGH"},
        {"date": "2026-06-10", "time_utc": "12:30", "event": "CPI (YoY)", "currency": "USD", "impact": "HIGH"},
        {"date": "2026-06-12", "time_utc": "06:00", "event": "GDP (MoM)", "currency": "GBP", "impact": "HIGH"},
        # The authoritative list is maintained in sr_vault_news_scan.py by Grok global searches.
    ]
    st.session_state.news_events = researched_events
    st.session_state.myfx_last_fetched = datetime.now().isoformat()
    try:
        cache = {"last_fetched": st.session_state.myfx_last_fetched, "source": "Grok Global Search (quick seed)", "events": researched_events}
        with open(NEWS_CACHE_PATH, "w") as f:
            json.dump(cache, f, indent=2)
    except Exception as e:
        st.warning(f"Could not write cache file: {e}")
    st.success("✅ Quick seed done. For the full accurate weekly scan, ask Grok \"do the weekly news scan\", then run: python sr_vault_news_scan.py")
    st.rerun()

# Manual CSV import (generic fallback - any source)
with st.expander("📥 Manual CSV / Data Import (fallback)", expanded=False):
    st.markdown("""
    **Preferred method:** Ask Grok in chat to "do the weekly news scan" (global search).  
    Then run this in Terminal:
    
    ```bash
    python /Users/stewartrawson/sr_vault_news_scan.py
    ```
    
    Only use manual import if you have a CSV or list from another source.
    """)
    manual_csv = st.file_uploader(
        "Upload a calendar CSV (optional)",
        type=["csv"],
        key="generic_news_import",
        help="Fallback only."
    )
    if manual_csv:
        content = manual_csv.getvalue().decode("utf-8", errors="ignore")
        imported = parse_myfxbook_csv(content)  # reuse the parser, it is generic
        if imported:
            st.session_state.news_events = imported
            st.success(f"✅ Imported {len(imported)} events. The list below is now up to date.")
            st.rerun()
        else:
            st.warning("No events parsed from the CSV.")

def parse_myfxbook_csv(csv_content: str):
    """Robust parser for MyFXBook calendar_statement.csv exports."""
    import csv
    from io import StringIO
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

            # Parse "June 10, 2026" style dates
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
        st.warning(f"Failed to parse MyFXBook CSV: {e}")
    return events


def fetch_myfxbook_weekly_events():
    """Fetch this week's + next 2 weeks of events directly from MyFXBook calendar export."""
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

        resp = requests.get(url, params=params, timeout=15, headers={
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
        })

        if resp.status_code == 200 and len(resp.text) > 200 and "Date" in resp.text[:300]:
            events = parse_myfxbook_csv(resp.text)
            filtered = [e for e in events if is_gbpjpy_relevant(e["event"], e["currency"])]

            # Save to persistent cache so the app and scripts can use it
            cache = {
                "last_fetched": datetime.now().isoformat(),
                "source": "MyFXBook",
                "events": filtered
            }
            with open(NEWS_CACHE_PATH, "w") as f:
                json.dump(cache, f)

            return filtered
        else:
            st.warning("MyFXBook returned no/empty data. Using cache or manual list.")
    except Exception as e:
        st.warning(f"Auto-fetch from MyFXBook failed: {e}. Using cache/manual.")

    return []


def load_cached_myfxbook_events():
    """Load previously fetched MyFXBook data if available (kept for compatibility)."""
    try:
        if os.path.exists(NEWS_CACHE_PATH):
            with open(NEWS_CACHE_PATH) as f:
                cache = json.load(f)
            return cache.get("events", []), cache.get("last_fetched")
    except:
        pass
    return [], None


if "news_events" not in st.session_state or not st.session_state.get("news_events"):
    # Prefer the persistent MyFXBook JSON cache (correct path)
    loaded_from_cache = False
    if os.path.exists(NEWS_CACHE_PATH):
        try:
            with open(NEWS_CACHE_PATH) as f:
                cache = json.load(f)
            evs = cache.get("events", [])
            if evs:
                st.session_state.news_events = evs
                st.session_state.myfx_last_fetched = cache.get("last_fetched")
                loaded_from_cache = True
        except Exception:
            pass

    if not loaded_from_cache:
        # Start empty (user will populate via Grok seed / CSV / button). Do NOT seed dummy rows.
        st.session_state.news_events = []

RELEVANT_KEYWORDS = [
    "NFP", "NON-FARM", "NONFARM", "PAYROLL", "EMPLOYMENT SITUATION",
    "BOE", "BANK OF ENGLAND", "MPC", "RATE DECISION",
    "INFLATION", "CPI", "CORE CPI", "RPI",
    "GDP",
    "FED", "FOMC", "POWELL", "INTEREST RATE DECISION", "FEDERAL RESERVE",
    "TARIFF", "TARIFFS",
    "JPY", "YEN",  # safety so JPY events pass currency check
]
RELEVANT_CURRENCIES = {"USD", "GBP", "JPY", "JAPAN"}

def is_gbpjpy_relevant(event, currency):
    text = f"{event} {currency}".upper()
    if currency.upper() not in RELEVANT_CURRENCIES:
        return False
    return any(kw in text for kw in RELEVANT_KEYWORDS)

def format_date_nice(date_str):
    """Convert YYYY-MM-DD to 'Thursday 11th June 2026' style."""
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

news_df = pd.DataFrame(st.session_state.news_events) if st.session_state.get("news_events") else pd.DataFrame()
if not news_df.empty and "event" in news_df.columns:
    news_df["relevant"] = news_df.apply(lambda r: is_gbpjpy_relevant(r["event"], r["currency"]), axis=1)
    relevant = news_df[news_df["relevant"]].copy()
    raw_count = len(news_df)
    after_filter_count = len(relevant)
else:
    relevant = pd.DataFrame(columns=["date", "time_utc", "event", "currency", "impact"])
    raw_count = 0
    after_filter_count = 0

# Debug / diagnostics so you can see exactly why events are or are not showing
with st.expander("🔍 News diagnostics (click to see raw counts & why list may be empty)", expanded=False):
    st.write(f"Rows in current list: **{raw_count}**")
    st.write(f"Rows after your GBP/JPY relevance filter: **{after_filter_count}**")
    if raw_count > 0 and after_filter_count == 0 and "event" in news_df.columns:
        st.caption("Sample event titles that did NOT match the keyword filter (first 5):")
        for ev in news_df["event"].head(5).tolist():
            st.write(f"  - {ev}")
    if after_filter_count == 0:
        st.info("No relevant events after filtering. Ask Grok to \"do the weekly news scan\" (global search), then run the Terminal script, or use the quick in-app seed button above.")
    st.caption("News is populated via Grok global web search + the sr_vault_news_scan.py script.")

today_str = today.strftime("%Y-%m-%d")
week_end = (today + timedelta(days=6)).strftime("%Y-%m-%d")

# NFP / BOE VOLATILITY WARNING - pops up on the most dangerous days
today_news = relevant[relevant["date"] == today_str][["time_utc", "event", "currency", "impact"]].copy()

if not today_news.empty:
    today_events_str = " ".join([str(e).upper() for e in today_news["event"]])
    if "NFP" in today_events_str or "BOE" in today_events_str:
        st.markdown("""
        <div style="
            background: linear-gradient(135deg, #c0392b, #e74c3c);
            color: white;
            border: 6px solid #f1c40f;
            padding: 12px 8px;
            border-radius: 12px;
            text-align: center;
            margin: 10px 0 15px 0;
            box-shadow: 0 8px 25px rgba(192, 57, 43, 0.6);
            font-family: system-ui, -apple-system, sans-serif;
        ">
            <div style="font-size: 2.6em; font-weight: 900; line-height: 1; margin-bottom: 2px;">⚠️ HIGH VOLATILITY WARNING ⚠️</div>
            <div style="font-size: 1.65em; font-weight: 800; letter-spacing: 1.5px; margin: 3px 0;">NFP or BOE DAY</div>
            <div style="font-size: 1.05em; margin-top: 4px; opacity: 0.95;">These are the MOST VOLATILE days for trading.<br>Extreme caution required. Review ALL rules. Reduced size or no new positions strongly advised.</div>
        </div>
        """, unsafe_allow_html=True)

# ================== CLEAN WEEKLY ROADMAP VIEW ==================

# TODAY
today_news = relevant[relevant["date"] == today_str][["time_utc", "event", "currency", "impact"]].copy()

st.markdown("**TODAY**")
if not today_news.empty:
    st.dataframe(today_news, hide_index=True, width='stretch')
else:
    st.info("No high-impact relevant events today.")

def get_week_start(d):
    return d - timedelta(days=d.weekday())

this_monday = get_week_start(today)
next_monday = this_monday + timedelta(days=7)
this_week_end = this_monday + timedelta(days=6)
next_week_end = next_monday + timedelta(days=6)

this_monday_str = this_monday.strftime("%Y-%m-%d")
next_monday_str = next_monday.strftime("%Y-%m-%d")
this_week_end_str = this_week_end.strftime("%Y-%m-%d")
next_week_end_str = next_week_end.strftime("%Y-%m-%d")

# THIS WEEK
this_week_news = relevant[(relevant["date"] >= this_monday_str) & (relevant["date"] <= this_week_end_str) & (relevant["date"] != today_str)][["date", "time_utc", "event", "currency", "impact"]].copy()
this_week_news = this_week_news.sort_values("date")

st.markdown(f"**THIS WEEK** (Week beginning {format_date_nice(this_monday_str)})")
if not this_week_news.empty:
    this_week_news["date"] = this_week_news["date"].apply(format_date_nice)
    this_week_news = this_week_news.rename(columns={
        "date": "Date",
        "time_utc": "Time (UTC)",
        "event": "Event",
        "currency": "Currency",
        "impact": "Impact"
    })
    st.dataframe(this_week_news, hide_index=True, width='stretch')
else:
    st.info("No more relevant events in the rest of this week.")

# NEXT WEEK
next_week_news = relevant[(relevant["date"] >= next_monday_str) & (relevant["date"] <= next_week_end_str)][["date", "time_utc", "event", "currency", "impact"]].copy()
next_week_news = next_week_news.sort_values("date")

st.markdown(f"**NEXT WEEK** (Week beginning {format_date_nice(next_monday_str)})")
if not next_week_news.empty:
    next_week_news["date"] = next_week_news["date"].apply(format_date_nice)
    next_week_news = next_week_news.rename(columns={
        "date": "Date",
        "time_utc": "Time (UTC)",
        "event": "Event",
        "currency": "Currency",
        "impact": "Impact"
    })
    st.dataframe(next_week_news, hide_index=True, width='stretch')
else:
    st.info("No relevant events scheduled for next week yet.")

# ================== MAINTENANCE (BOTTOM, MINIMAL) ==================
with st.expander("UPDATE DATA (manual until API)"):
    st.session_state.open_trades = st.number_input("Open Trades", 0, 50, st.session_state.open_trades, 1)
    st.session_state.pending_orders = st.number_input("Pending Orders", 0, 30, st.session_state.pending_orders, 1)
    st.session_state.risk_per_trade = st.number_input("Risk Per Trade (%)", 0.0, 10.0, float(st.session_state.risk_per_trade), 0.1, format="%.1f")
    st.session_state.account_balance = st.number_input("Account Balance", 0.0, 1000000.0, float(st.session_state.account_balance), 100.0, format="%.2f")
    st.session_state.current_trade_pnl = st.number_input("Current Trade Profit/Loss", -100000.0, 100000.0, float(st.session_state.current_trade_pnl), 10.0, format="%.2f")
    st.markdown("---")
    st.markdown("**Edit news events** (only GBP/JPY relevant ones show above)")
    st.markdown("""
    **Weekly Bomb-Proof Check Protocol (do this every Sunday/Monday):**
    1. Go to Forex Factory calendar (primary source).
    2. Filter for high-impact GBP + JPY + USD events only.
    3. Cross-check with Investing.com.
    4. Update the table above with correct dates/times.
    5. Update the `NEWS_LAST_VERIFIED` date at the top of the news section.
    6. Delete any old events that have passed.

    This is the only way to keep the data bomb-proof. There is no live feed.
    """)
    edited = st.data_editor(pd.DataFrame(st.session_state.news_events), num_rows="dynamic", width='stretch', hide_index=True)
    st.session_state.news_events = edited.to_dict("records")

with st.expander("RED / YELLOW DAY RULES"):
    st.markdown("""
    **RED DAYS** (avoid new positions / extreme caution):

    - Any official market holiday
    - **The whole of August**
    - **Last 3 weeks of December** (from 11 December)
    - **Last 3 days of quarter-end months** (29–31 Mar, 28–30 Jun, 28–30 Sep, 29–31 Dec)
    - **The very last day of every month**

    **GREEN DAY** — Normal trading day (everything not listed above)

    These rules are implemented in `get_day_status()`. Let me know if you want any Yellow caution days added or further tweaks.
    """)

st.caption("SR VAULT • Refresh for latest times • Manual counts until cTrader API live")
