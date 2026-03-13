# Signal AI — Info Requests Dashboard

A self-updating dashboard that tracks information requests in `#commercial-global` and `#aes-global`, hosted on GitHub Pages.

## How it works

```
Slack channels ──► sync_slack.py ──► data/requests.json ──► index.html (GitHub Pages)
                   (runs weekly via
                    GitHub Actions)
```

- `index.html` — the dashboard, reads `data/requests.json` at runtime
- `scripts/sync_slack.py` — fetches new requests from Slack, classifies them, merges into `data/requests.json`
- `.github/workflows/sync-slack.yml` — runs the sync every Monday at 09:00 UTC and commits the updated data file

---

## Setup (one-time, ~10 minutes)

### 1 — Create a Slack app

1. Go to https://api.slack.com/apps → **Create New App** → **From scratch**
2. Name it `Info Requests Bot`, pick your Signal AI workspace
3. Under **OAuth & Permissions → Bot Token Scopes**, add:
   - `channels:history`
   - `groups:history`
   - `users:read`
4. Click **Install to Workspace**, copy the **Bot OAuth Token** (starts with `xoxb-`)
5. Invite the bot to both channels:
   ```
   /invite @Info Requests Bot
   ```
   Do this in both `#commercial-global` and `#aes-global`.

### 2 — Add the token to GitHub

1. In your GitHub repo → **Settings → Secrets and variables → Actions**
2. Click **New repository secret**
3. Name: `SLACK_BOT_TOKEN`, Value: your `xoxb-...` token

### 3 — Enable GitHub Pages

1. Repo → **Settings → Pages**
2. Source: **Deploy from a branch**, branch: `main`, folder: `/ (root)`
3. Your dashboard will be live at `https://<your-username>.github.io/<repo-name>/`

### 4 — Run a first sync to populate data

Either:
- **Manually trigger**: Repo → **Actions → Sync Slack requests → Run workflow**
- **Locally**: `export SLACK_BOT_TOKEN=xoxb-... && python scripts/sync_slack.py`

---

## Adding categories

Edit `CATEGORIES` in `scripts/sync_slack.py` to add or rename categories. Then update `SEED_DATA` in `index.html` to match the same `id` values. The sync script will create new category buckets automatically on next run.

## Changing the sync schedule

Edit the `cron` expression in `.github/workflows/sync-slack.yml`. Current: every Monday 09:00 UTC.

| Expression | Meaning |
|---|---|
| `0 9 * * 1` | Every Monday 09:00 |
| `0 9 * * *` | Every day 09:00 |
| `0 9,17 * * 1-5` | Weekdays 09:00 and 17:00 |
