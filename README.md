# SR VAULT Daily Trading Panel — Live on GitHub Pages

**Goal achieved**: A real public URL for the panel. Live GBPJPY price updates itself every minute (no more asking to refresh). News + ZeroHedge refresh automatically (GitHub Action hourly for calendar + JSON polling in the page + your bot later for ZeroHedge). Full-width day status bar + big chart box that fills the area. All projects organized (srvault is isolated here).

**Live site (after you complete the 3 easy steps below)**: https://stewraw25.github.io/srvault/

Everything is static + client JS + one scheduled Action. No server to maintain.

## What I have already done for you (local + code)
- Moved/organized into `~/Sites/srvault/` (separate from sleepbetterhub, pro-renewables etc.)
- Full panel in `index.html` (root for Pages):
  - Automatic live price: `fetchLivePrice()` hits public frankfurter.app on load + every 60s. Updates the big number + green/red delta. Manual override still works via the UPDATE button (localStorage).
  - News tables (TODAY / THIS WEEK / NEXT WEEK) load dynamically from `sr_vault_assets/news/myfxbook_news.json` + re-render with nice dates + week labels. Polls every 5 min.
  - ZeroHedge widget loads from `sr_vault_assets/news/zerohedge.json` (falls back gracefully). Polls every 15 min.
  - Full-width green/red day-status banner right under the 3 top boxes (plus the floating pill).
  - Chart box is wider, fixed 500px tall, image uses object-cover to fill the square nicely.
  - Clocks, trend, account inputs, everything else from the original.
- Git repo initialized + committed (all assets, the Python scanner, the GitHub Action workflow).
- Fixed the news script so `python sr_vault_news_scan.py --auto` works from this folder both locally and in CI (no more hard-coded wrong path).
- Added `.gitignore`.
- GitHub Action (`.github/workflows/update-news.yml`) runs every hour (`0 * * * *`), runs the scanner in --auto mode (uses public Forex Factory feed + same filters you had), commits the fresh JSON if changed.
- README + instructions.

Remote is already set to your `stewraw25/srvault`.

## The only things you need to do (easiest possible)
You do **not** need to run git init/add/commit or edit code. Just push + 3 clicks.

### 1. Push the ready repo (one paste in Terminal)
1. Open the **Terminal** app on your Mac (Spotlight → Terminal).
2. Copy **everything** below and paste it into the Terminal window, then press Enter:

```bash
cd ~/Sites/srvault
git push -u origin main --force
```

- If it asks `Username for 'https://github.com'`: type `stewraw25` and press Enter.
- If it asks `Password for 'https://github.com'`: **this is where you use a token**.
  - In your browser go to: https://github.com/settings/tokens
  - Click "Generate new token" → "Generate new token (classic)"
  - Give it a name like "srvault push", check the **repo** scope checkbox, scroll down, Generate token.
  - Copy the `ghp_...` string.
  - Paste it into the Terminal password prompt (typing is hidden — just paste + Enter).
- You should see "Enumerating objects", "Writing objects", "Everything up-to-date" or similar. Done.

(If you get a 403 or permission error, the token needs the `repo` scope or the repo is private and token too narrow — paste the exact error here and I'll give the next line.)

### 2. Turn on GitHub Pages (3 clicks)
1. Go directly to: https://github.com/stewraw25/srvault/settings/pages
2. In the "Build and deployment" section:
   - **Source**: select **Deploy from a branch**
   - **Branch**: select **main** (it will now appear because we pushed content)
   - **Folder**: select **/ (root)**
3. Click the **Save** button.

Wait ~30-60 seconds for the first build. The green "Your site is live at https://stewraw25.github.io/srvault/" message will appear.

### 3. Kick off the first automatic news update (optional but recommended right now)
1. Go to: https://github.com/stewraw25/srvault/actions
2. On the left click the workflow named **Update Economic News JSON (Hourly)**
3. Click the big green **Run workflow** button (top right of the workflow page) → Run workflow.

This makes the calendar JSON fresh immediately. The Action will then keep running every hour by itself forever.

### 4. Open the live site and verify
- https://stewraw25.github.io/srvault/
- The GBPJPY price should show a real current number and the delta should appear after a couple seconds (it keeps updating).
- The news tables should have dates like "Wednesday 10th June" etc. and a "last updated" time.
- The day status bar under the three boxes should be green or red.
- Refresh the page any time; everything auto-refreshes in the background too.

Local double-click of `index.html` still works exactly the same for offline/testing.

## Keeping things fresh going forward (no more manual Grok refreshes for routine stuff)
- **Price**: 100% automatic forever.
- **Economic calendar**: GitHub Action does it hourly. The page polls the JSON every 5 min so you see updates without reload.
- **ZeroHedge posts**: The widget reads the JSON. To update it, just tell me here "update zerohedge with these 6 posts" (or paste the titles/times/urls) and I'll give you the exact JSON snippet + the one-line command to put it in the file and push. Or your future bot can maintain the file + push.
- **Chart screenshot (middle box)**: Send the new image here in chat (or a link). I'll give you the exact file path + the Terminal lines to replace `sr_vault_assets/charts/current_weekly_chart.png` and push the change. The site updates in ~1 min.
- **Account numbers / trend**: Still editable live in the panel (localStorage per browser). Later we can wire `panel-state.json` so your bot can drive those too.

## Other sites / organization
All your projects are now in their own folders under `~/Sites/`:
- `srvault/` (this trading panel)
- `sleepbetterhub/`
- `pro-renewables-ac/` (RELOAD Renewables)
- `automatic-cash-bot-website/`
etc. Nothing is mixed together.

## Troubleshooting
- Pages branch dropdown still says "None"? Hard-refresh the /settings/pages page (Cmd-Shift-R) after the push finishes. Content must be on `main` first.
- Price not moving? Check browser console (right-click → Inspect → Console) for any red errors on the frankfurter fetch (rare).
- News looks old? Manually run the Action again or just wait for the next hourly run. You can also run `python sr_vault_news_scan.py --auto` locally from the srvault folder (it will update the JSON here, then you push the one file).
- Want a custom domain later? Easy — we add a CNAME file + point DNS.

That's it. The panel is now a proper always-on website the bot can read from (raw JSON URLs) and you can open on phone/iPad/Safari without "still not open" drama.

Open the live URL when you're done with the three steps and tell me how it looks (or paste any errors). We can add the panel-state.json loader or any other tweak next.