import asyncio
import logging
import os
import time
from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Optional

import discord
import httpx
import yaml


def setup_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="[%(asctime)s] [%(levelname)s] %(name)s: %(message)s",
    )


@dataclass
class RepoConfig:
    owner: str
    name: str
    branch: str = "main"
    channel_id: Optional[int] = None

    @property
    def slug(self) -> str:
        return f"{self.owner}/{self.name}@{self.branch}"


@dataclass
class BotConfig:
    discord_token: str
    channel_id: int
    poll_interval: int = 300
    github_token: str = ""
    repos: List[RepoConfig] = field(default_factory=list)


class ConfigError(Exception):
    pass


def load_config(path: str) -> BotConfig:
    if not os.path.exists(path):
        raise ConfigError(f"Config file not found at {path}.")

    with open(path, "r", encoding="utf-8") as file:
        raw = yaml.safe_load(file) or {}

    try:
        repos = [
            RepoConfig(
                owner=item["owner"],
                name=item["name"],
                branch=item.get("branch", "main"),
                channel_id=int(item["channel_id"]) if "channel_id" in item else None,
            )
            for item in raw.get("repos", [])
        ]
        return BotConfig(
            discord_token=raw["discord_token"],
            channel_id=int(raw["channel_id"]),
            poll_interval=int(raw.get("poll_interval", 300)),
            github_token=raw.get("github_token", ""),
            repos=repos,
        )
    except KeyError as exc:
        raise ConfigError(f"Missing required config value: {exc}") from exc


class RepoMonitor:
    def __init__(self, client: discord.Client, config: BotConfig) -> None:
        self.client = client
        self.config = config
        self.log = logging.getLogger(self.__class__.__name__)
        self.last_seen: Dict[str, str] = {}
        self.http_client: Optional[httpx.AsyncClient] = None

    async def _get_http_client(self) -> httpx.AsyncClient:
        if self.http_client is None:
            headers = {"Accept": "application/vnd.github+json"}
            if self.config.github_token:
                headers["Authorization"] = f"Bearer {self.config.github_token}"
            self.http_client = httpx.AsyncClient(headers=headers, timeout=15)
        return self.http_client

    async def initialize(self) -> None:
        """Prime last_seen state so the bot does not spam on first run."""
        for repo in self.config.repos:
            sha = await self._latest_commit_sha(repo)
            if sha:
                self.last_seen[repo.slug] = sha
                self.log.info("Initialized %s with %s", repo.slug, sha)

    async def _latest_commit_sha(self, repo: RepoConfig) -> Optional[str]:
        commits = await self._fetch_commits(repo)
        return commits[0]["sha"] if commits else None

    async def _fetch_commits(self, repo: RepoConfig) -> List[dict]:
        client = await self._get_http_client()
        url = f"https://api.github.com/repos/{repo.owner}/{repo.name}/commits"
        params = {"sha": repo.branch, "per_page": 10}
        backoff = 1.0

        for attempt in range(3):
            try:
                response = await client.get(url, params=params)
            except httpx.HTTPError as exc:
                self.log.warning(
                    "Network error fetching %s (attempt %s/3): %s", repo.slug, attempt + 1, exc
                )
                await asyncio.sleep(backoff)
                backoff *= 2
                continue

            if response.status_code == 200:
                return response.json()

            if response.status_code in {500, 502, 503, 504}:
                self.log.warning(
                    "GitHub error %s for %s, retrying (attempt %s/3)",
                    response.status_code,
                    repo.slug,
                    attempt + 1,
                )
                await asyncio.sleep(backoff)
                backoff *= 2
                continue

            if response.status_code == 403 and response.headers.get("X-RateLimit-Remaining") == "0":
                reset_ts = response.headers.get("X-RateLimit-Reset")
                reset_in = int(reset_ts) - int(time.time()) if reset_ts else None
                if reset_in and reset_in > 0:
                    self.log.error(
                        "GitHub rate limit hit for %s. Resets in %s seconds.", repo.slug, reset_in
                    )
                else:
                    self.log.error("GitHub rate limit hit for %s.", repo.slug)
            else:
                self.log.warning(
                    "Failed to fetch commits for %s: %s %s", repo.slug, response.status_code, response.text
                )
            return []

        self.log.error("Exhausted retries fetching commits for %s", repo.slug)
        return []

    async def run(self) -> None:
        await self.initialize()
        try:
            while not self.client.is_closed():
                await self.check_for_updates()
                await asyncio.sleep(self.config.poll_interval)
        finally:
            if self.http_client is not None:
                await self.http_client.aclose()

    async def check_for_updates(self) -> None:
        tasks = [self._check_repo_safe(repo) for repo in self.config.repos]
        if tasks:
            await asyncio.gather(*tasks)

    async def _resolve_channel(self, repo: RepoConfig) -> Optional[discord.abc.Messageable]:
        channel_id = repo.channel_id or self.config.channel_id
        channel = self.client.get_channel(channel_id)
        if channel is not None:
            return channel

        try:
            fetched = await self.client.fetch_channel(channel_id)
        except discord.HTTPException as exc:
            self.log.error("Unable to fetch Discord channel %s for %s: %s", channel_id, repo.slug, exc)
            return None

        return fetched

    async def _check_repo(self, repo: RepoConfig, channel: discord.abc.Messageable) -> None:
        commits = await self._fetch_commits(repo)
        if not commits:
            return

        last_seen = self.last_seen.get(repo.slug)
        new_commits: List[dict] = []

        for commit in commits:
            sha = commit.get("sha")
            if sha == last_seen:
                break
            new_commits.append(commit)

        if not last_seen:
            self.last_seen[repo.slug] = commits[0]["sha"]
            return

        if not new_commits:
            return

        self.last_seen[repo.slug] = new_commits[0]["sha"]
        await self._announce_commits(repo, list(reversed(new_commits)), channel)

    async def _check_repo_safe(self, repo: RepoConfig) -> None:
        channel = await self._resolve_channel(repo)
        if channel is None:
            return

        try:
            await self._check_repo(repo, channel)
        except Exception:
            self.log.exception("Unexpected error while checking %s", repo.slug)

    async def _announce_commits(
        self, repo: RepoConfig, commits: List[dict], channel: discord.abc.Messageable
    ) -> None:
        lines = [f"New commits in **{repo.owner}/{repo.name}** on `{repo.branch}`:"]
        for commit in commits:
            sha = commit.get("sha", "")[:7]
            info = commit.get("commit", {})
            message = info.get("message", "(no message)").split("\n")[0]
            author = info.get("author", {}).get("name", "Unknown")
            url = commit.get("html_url", "")
            lines.append(f"• [`{sha}`]({url}) {message} — {author}")

        content = "\n".join(lines)
        for chunk in self._chunk_message(content):
            await channel.send(chunk)

    def _chunk_message(self, content: str, limit: int = 1800) -> Iterable[str]:
        """Split long messages into Discord-safe chunks."""
        if len(content) <= limit:
            return [content]

        chunks: List[str] = []
        current: List[str] = []
        current_len = 0

        for line in content.splitlines():
            if current_len + len(line) + 1 > limit:
                chunks.append("\n".join(current))
                current = []
                current_len = 0
            current.append(line)
            current_len += len(line) + 1

        if current:
            chunks.append("\n".join(current))

        return chunks


def build_client(config: BotConfig) -> discord.Client:
    intents = discord.Intents.default()
    client = discord.Client(intents=intents)
    monitor = RepoMonitor(client, config)

    @client.event
    async def on_ready() -> None:
        logging.getLogger("discord").info("Logged in as %s", client.user)
        client.loop.create_task(monitor.run())

    return client


async def main() -> None:
    setup_logging()
    config_path = os.environ.get("DISCORD_BOT_CONFIG", "config.yml")
    try:
        config = load_config(config_path)
    except ConfigError as exc:
        logging.error("%s", exc)
        return

    client = build_client(config)
    await client.start(config.discord_token)


if __name__ == "__main__":
    asyncio.run(main())
