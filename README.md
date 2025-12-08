# GitHub Discord Bot

A lightweight Discord bot that posts new GitHub commits to a Discord channel. Configure it with one or more repositories and the bot will periodically announce new additions.

## Features
- Monitor multiple repositories and branches using a simple YAML config file.
- Posts commit summaries with links directly in your Discord channel(s).
- Optional GitHub token support for higher API limits.

## Setup
1. **Install dependencies**
   ```bash
   python -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```
2. **Create a Discord bot token** and invite it to your server with the `Send Messages` permission.
3. **Create your config**
   - Copy `config.example.yml` to `config.yml`.
   - Fill in your `discord_token`, default `channel_id`, and the repositories you want to watch.
   - Optionally set a `channel_id` per repository to route updates to different channels.
   - Set `github_token` if you have one to increase rate limits.
4. **Run the bot**
   ```bash
   python bot.py
   ```

The bot reads from `config.yml` by default. To use a different path, set `DISCORD_BOT_CONFIG=/path/to/config.yml` when running the script.

## Configuration reference (`config.yml`)
```yaml
discord_token: "YOUR_DISCORD_BOT_TOKEN"
channel_id: 123456789012345678 # default channel for all repos
github_token: ""  # optional
poll_interval: 300 # seconds between checks
repos:
  - owner: octocat
    name: Hello-World
    branch: main
    # Optional: override the default channel for this repo only.
    # channel_id: 111111111111111111
```

Add as many repositories as you like under `repos`. Each entry can target a different branch and channel.

## How it works
- On startup, the bot records the latest commit per repository so it does not spam old commits.
- Every `poll_interval` seconds, it asks the GitHub API for recent commits on each branch.
- New commits are posted in order with a short summary and direct links.

## Troubleshooting
- Ensure the bot has permission to post in the configured channel.
- If you see rate-limit warnings, add a `github_token` to the config.
- To increase verbosity, edit `setup_logging()` in `bot.py` to use `DEBUG` level logging.
