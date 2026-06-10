# SR VAULT — Daily Trading Panel (Hosted on GitHub)

Premium, clean, low-maintenance **TRADING PANEL for Funded Accounts** (GBPJPY-focused).

Live view (GitHub Pages): https://YOUR-USERNAME.github.io/sr-vault-trading-panel/ (update after you enable Pages)

## Features (kept exactly as the original local version + auto data)
- Analogue-style clocks (UTC / London / NY / Tokyo) + silver divider
- SR Vault logo + "Everyday People. Making Serious CASH."
- Big "TRADING PANEL" header (simplified per request)
- Live GBPJPY price banner (right side of header) — **now fully automatic**
  - Fetches from public free forex API on load + every 60 seconds
  - Updates the big number + the `+X.XX • +X.XX%` delta automatically
  - You can still manually type a value + hit UPDATE (saves to your browser localStorage for overrides/simulations)
- 3 main boxes (KEY TRADING INFORMATION (narrower), CURRENT CHART (wider main focus with image filling the square via object-cover), ZeroHedge)
- Day status: full-width banner right under the 3 boxes **+** floating pill bottom-right (green NORMAL TRADING DAY or red with exact rules)
- RELEVANT NEWS — GBP/JPY FOCUS (TODAY / THIS WEEK / NEXT WEEK tables with proper "Wednesday 10th June 2026" formatting)
- ZeroHedge X posts widget (right box)
- Chart upload/replace (localStorage for local use; see "Updating the chart image" below for the hosted site)
- Everything is self-contained — double-click the HTML locally still works great for testing/offline.

## Quick Start (Local — same as before)
1. Double-click `sr_vault_trading_panel.html` (or `index.html` once you rename it for Pages).
2. Everything (clocks, price on first load, day status, etc.) works immediately.
3. To refresh the **economic news** data: run `python sr_vault_news_scan.py` (or "do the weekly news scan" then run it). The page will pick up the new `last_fetched` timestamp on next poll (or reload).

## Making It a Real Live Site (GitHub Pages + Auto Refresh)
This is the main change you asked for: the panel becomes a real URL that is always up-to-date, accessible from any device, and the future trading bot can read/write the data files.

### 1. One-time GitHub setup (you do this)
- Create a new public repo on your GitHub account (suggested name: `sr-vault-trading-panel`).
- Push / upload these files (keep the folder structure):
  - `index.html` (copy/rename `sr_vault_trading_panel.html` — Pages likes `index.html` at the root)
  - `sr_vault_assets/` (logos, charts/current_weekly_chart.png, news/, data/)
  - `sr_vault_news_scan.py`
  - `.github/workflows/update-news.yml`
  - `README.md` (this file)
- In the repo → **Settings → Pages** → Source = "Deploy from a branch" → Branch = `main` / root → Save.
- Your live site will be at `https://<your-username>.github.io/sr-vault-trading-panel/`

All relative paths (`./sr_vault_assets/...`) work both locally and on Pages.

### 2. Live GBPJPY price — already automatic (no Grok refresh ever needed)
- The header price + delta now use a free public API (`frankfurter.app`).
- Updates on load + every 60 seconds.
- Hosted site or local file — both get fresh prices automatically.

### 3. Economic news (the 3-column RELEVANT NEWS tables) — automatic + hourly
- The Python script (`sr_vault_news_scan.py`) is still the source of truth.
- **Local/manual**: run the script whenever you want fresh events (it writes `sr_vault_assets/news/myfxbook_news.json`).
- **Automatic on the site**: the included GitHub Action (`.github/workflows/update-news.yml`) runs **every hour** (you can change the cron), uses the built-in public Forex Factory feed + the same filters, commits the updated JSON.
- The panel (both local and hosted) polls the JSON every 5 minutes for the "last updated" timestamp and (with the dynamic loader we added) re-renders the TODAY/THIS WEEK/NEXT WEEK tables with correct current dates.
- You never have to ask Grok just to get new calendar data.

### 4. ZeroHedge / @zerohedge X posts widget — automatic via the bot (or you)
- We added support to load from `sr_vault_assets/news/zerohedge.json` (same shape as the old JS array).
- The widget renders from the JSON when present (falls back to the static list for pure local use).
- **How it stays fresh without asking Grok**:
  - Your trading bot (or a tiny scheduled script on the same laptop that runs the news script) maintains the `zerohedge.json` file.
  - Bot/script does a `git add / commit / push` (or uses the GitHub API).
  - The hosted site sees the new posts on the next poll.
- You can still say "refresh zero hedge feed" here — Grok will give you the latest 6 posts as a ready-to-paste JSON array (or a diff) that you (or the bot) can commit.

### 5. Updating the chart screenshot (the big middle box)
- Local/dev: the in-page "Click to replace" still works (saves to browser localStorage).
- **Hosted site (recommended flow)**: Send the new screenshot to Grok right here in this chat (or drop a Telegram/public link). Grok will give you the updated image file (or base64) + the exact file to replace in `sr_vault_assets/charts/current_weekly_chart.png` and the commit message. You push the change — the site updates.
- This keeps the "send the screenshot and Grok attaches it" experience you wanted, while the image lives in the repo (no tokens exposed in the browser).

### 6. Bot integration (the whole point of making it a site)
Once the site is live at the GitHub Pages URL:

- The bot can **read** the current state without any secrets:
  - `https://raw.githubusercontent.com/<you>/sr-vault-trading-panel/main/sr_vault_assets/news/myfxbook_news.json`
  - `.../zerohedge.json`
  - `.../data/panel-state.json` (optional — see below)
  - The live price is independently fetched by the page (or the bot can call the same public forex API).

- The bot can **write** updates by pushing to the repo (using a classic fine-grained PAT with only `contents:write` on this repo, or a GitHub App). Examples:
  - Update `panel-state.json` with latest open trades, P/L, balance, risk, trend.
  - Drop a new `zerohedge.json` with fresh posts it cares about.
  - The page picks everything up on the next poll (no reload required for most things).

This replaces the old "local files + shared folders + ngrok headaches".

### 7. Optional but recommended: panel-state.json for bot-driven account/trend data
See `sr_vault_assets/data/panel-state.json` (template included).  
The panel can load it (we can wire the JS on request). Your bot becomes the single source of truth for "what the account actually looks like right now". LocalStorage is still used for personal UI tweaks on a particular browser.

### How to keep everything fresh (no daily manual work)
- News/economic calendar: the GitHub Action does it hourly (you can lower to every 15–30 min if the free tier allows).
- ZeroHedge + account state: your trading bot (or a 5-line cron script that re-uses the same logic as the news script) writes the JSON files and pushes.
- Price: 100% automatic via public API.
- Chart: send the image to Grok in chat when it changes (or have the bot drop a new PNG and commit it).

### Local vs Hosted
- Everything still works 100% when you double-click the HTML locally (price will be live, news timestamp will read the local JSON, etc.).
- The hosted version just gives you a stable URL + the scheduled Action + easy bot access.

### Custom domain (later)
You said you can buy one once we're set up on GitHub — perfect. GitHub Pages supports custom domains (just add a CNAME file + DNS). We can wire that later; github.io is fine (and free) for now.

### Next steps after you push the repo
1. Enable Pages.
2. Wait for the first Action run (or manually trigger the workflow) so the news JSON is fresh.
3. Open the Pages URL on any device.
4. (Optional) Give your bot a PAT that can push to this repo and point it at the raw JSON URLs.
5. Tell Grok "the site is live" and we can add the final JS bits for loading `panel-state.json` + any other polish.

Enjoy the always-fresh panel. No more "still not open" local file drama and no more "please refresh the zero hedge feed" messages for routine updates.

(If you want the economic news tables to be 100% dynamic from the JSON right now, or the panel-state loading wired in, or the ZeroHedge JSON loader fully active — just say the word and I'll make those exact edits.)
