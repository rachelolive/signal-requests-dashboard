name: Sync Slack Data

on:
  schedule:
    - cron: '0 7 * * *'   # 7am UTC every day
  workflow_dispatch:       # lets you trigger manually from GitHub UI

permissions:
  contents: write

jobs:
  sync:
    runs-on: ubuntu-latest

    steps:
      - name: Checkout repo
        uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: pip install slack-sdk

      - name: Run Slack sync
        env:
          SLACK_BOT_TOKEN: ${{ secrets.SLACK_BOT_TOKEN }}
        run: python scripts/sync_slack.py

      - name: Commit updated data
        run: |
          git config user.name "github-actions[bot]"
          git config user.email "github-actions[bot]@users.noreply.github.com"
          git add data/requests.json data/feedback.json
          git diff --cached --quiet || git commit -m "chore: sync Slack data $(date -u +%Y-%m-%d)"
          git push
