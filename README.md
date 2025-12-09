# GitHub Discord Bot

A lightweight Discord bot that announces new GitHub commits in your Discord server. Point it at one or more repositories and it will periodically poll GitHub, detect new commits, and post concise summaries with direct links.

## Why this bot?
- **Multi-repo aware:** Watch many repositories/branches from a single YAML config.
- **Respectful of limits:** Optional GitHub tokens, retry logic, and clearer rate-limit logging.
- **Discord-friendly messages:** Automatically splits long updates to stay under Discord's 2000-character limit.
- **Simple to run:** One script, a virtual environment, and a small config file.

## Prerequisites
- Python 3.9+ (the setup script uses your default `python` unless overridden)
- A Discord bot token with permission to send messages
- (Optional) A GitHub personal access token for higher rate limits

## Quick start
1. **Set up the environment**
   ```bash
   ./setup.sh
   ```
   This creates `.venv`, installs dependencies, and copies `config.example.yml` to `config.yml` if it is missing. You can override defaults with environment variables:
   - `PYTHON` – alternative Python executable
   - `VENV_DIR` – destination for the virtual environment
   - `CONFIG_FILE` – alternate path for the generated config file

2. **Configure the bot**
   Open `config.yml` and provide:
   - `discord_token`: your Discord bot token
   - `channel_id`: default Discord channel ID for announcements
   - `repos`: list of repositories (owner/name/branch) to monitor
   - `github_token` (optional): GitHub token to raise rate limits
   You can also set a `channel_id` per repository entry to route updates to specific channels.

3. **Run the bot**
   ```bash
   source .venv/bin/activate  # or your custom VENV_DIR
   python bot.py
   ```
   By default the bot reads `config.yml` in the project root. To specify another path, set `DISCORD_BOT_CONFIG=/path/to/config.yml` when running the script.

## Configuration reference
```yaml
discord_token: "YOUR_DISCORD_BOT_TOKEN"
channel_id: 123456789012345678 # default channel for all repos
github_token: ""                # optional for higher rate limits
poll_interval: 300              # seconds between checks
repos:
  - owner: octocat
    name: Hello-World
    branch: main
    # Optional: override the default channel for this repo only.
    # channel_id: 111111111111111111
```

Add as many repositories as you like under `repos`. Each entry can target a different branch and channel.

## How it works
- On startup, the bot records the latest commit per repository to avoid reposting history.
- Every `poll_interval` seconds, it queries the GitHub API for recent commits on each branch.
- Newly discovered commits are posted in order with a short summary and direct links.

## Troubleshooting
- Ensure the bot has permission to post in the configured channel.
- If you see rate-limit warnings, add a `github_token` to the config.
- Increase log verbosity by setting `DEBUG` in `setup_logging()` inside `bot.py`.
