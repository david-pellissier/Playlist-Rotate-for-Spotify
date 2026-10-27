import asyncio
import json
import logging
import re
import time
from collections.abc import AsyncIterator, Awaitable, Iterable
from datetime import UTC, date, datetime, timedelta
from urllib.parse import urlencode

import httpx

from .config import env

API_URL = "https://api.spotify.com/v1"
AUTHORIZE_URL = "https://accounts.spotify.com/authorize"
TOKEN_URL = "https://accounts.spotify.com/api/token"
TOKEN_FILE = env.database_path.parent / "spotify_token.json"
SCOPES = "playlist-read-private playlist-modify-public playlist-modify-private"
ALBUM_GROUPS = ("album", "single")
PLAYLIST_ID = re.compile(r"(?:playlist[/:])([A-Za-z0-9]{22})|^([A-Za-z0-9]{22})$")
IDEMPOTENT_METHODS = {"GET", "PUT", "DELETE"}
MAX_ATTEMPTS = 5
MAX_CONCURRENCY = 4
REQUEST_INTERVAL = 0.2
MAX_RATE_LIMIT_WAIT = 60
PLAYLIST_CHUNK = 100

log = logging.getLogger(__name__)


class SpotifyError(Exception):
    pass


class RateLimitError(SpotifyError):
    def __init__(self, retry_at: datetime) -> None:
        self.retry_at = retry_at
        local_time = retry_at.replace(tzinfo=UTC).astimezone(env.timezone)
        super().__init__(f"Spotify rate limit reached, retry after {local_time:%Y-%m-%d %H:%M}")


async def gather_all[T](awaitables: Iterable[Awaitable[T]]) -> list[T]:
    tasks = [asyncio.ensure_future(awaitable) for awaitable in awaitables]
    try:
        return await asyncio.gather(*tasks)
    except BaseException:
        for task in tasks:
            task.cancel()
        raise


def parse_release_date(value: str) -> date:
    year, month, day = ([int(part) for part in value.split("-")] + [1, 1])[:3]
    return date(max(year, 1), max(month, 1), max(day, 1))


def load_refresh_token() -> str:
    try:
        saved = json.loads(TOKEN_FILE.read_text())
    except (OSError, ValueError):
        return env.refresh_token
    return saved["token"] if saved.get("configured") == env.refresh_token else env.refresh_token


def save_refresh_token(token: str) -> None:
    TOKEN_FILE.write_text(json.dumps({"configured": env.refresh_token, "token": token}))


class Spotify:
    def __init__(self) -> None:
        self._http = httpx.AsyncClient(base_url=API_URL, timeout=30)
        self._refresh_token = load_refresh_token()
        self._token = ""
        self._token_expires_at = 0.0
        self._token_lock = asyncio.Lock()
        self._slots = asyncio.Semaphore(MAX_CONCURRENCY)
        self._pace_lock = asyncio.Lock()
        self._next_request_at = 0.0
        self._blocked_until: datetime | None = None

    async def close(self) -> None:
        await self._http.aclose()

    @staticmethod
    def authorize_url() -> str:
        query = {
            "client_id": env.client_id,
            "response_type": "code",
            "redirect_uri": env.redirect_uri,
            "scope": SCOPES,
        }
        return f"{AUTHORIZE_URL}?{urlencode(query)}"

    async def exchange_code(self, code: str) -> str:
        payload = await self._token_request(
            {"grant_type": "authorization_code", "code": code, "redirect_uri": env.redirect_uri}
        )
        return payload["refresh_token"]

    async def _token_request(self, data: dict) -> dict:
        try:
            response = await self._http.post(TOKEN_URL, data=data, auth=(env.client_id, env.client_secret))
        except httpx.TransportError as error:
            raise SpotifyError(f"Could not reach Spotify: {error!r}") from error
        if response.is_error:
            raise SpotifyError(f"Spotify authorization failed: {response.text}")
        return response.json()

    async def _access_token(self) -> str:
        async with self._token_lock:
            if time.monotonic() < self._token_expires_at:
                return self._token
            if not (env.client_id and env.client_secret and self._refresh_token):
                raise SpotifyError("Spotify credentials are missing from the environment")
            payload = await self._token_request({"grant_type": "refresh_token", "refresh_token": self._refresh_token})
            if payload.get("refresh_token", self._refresh_token) != self._refresh_token:
                self._refresh_token = payload["refresh_token"]
                save_refresh_token(self._refresh_token)
                log.info("Spotify issued a new refresh token, saved to %s", TOKEN_FILE)
            self._token = payload["access_token"]
            self._token_expires_at = time.monotonic() + payload["expires_in"] - 60
            return self._token

    async def _wait_for_turn(self) -> None:
        if self._blocked_until and datetime.now(UTC).replace(tzinfo=None) < self._blocked_until:
            raise RateLimitError(self._blocked_until)
        async with self._pace_lock:
            delay = self._next_request_at - time.monotonic()
            if delay > 0:
                await asyncio.sleep(delay)
            self._next_request_at = time.monotonic() + REQUEST_INTERVAL

    def _rate_limited(self, method: str, url: str, response: httpx.Response) -> float:
        wait = float(response.headers.get("Retry-After", "1"))
        log.warning("Spotify rate limit on %s %s, Retry-After %ds", method, url, wait)
        if wait > MAX_RATE_LIMIT_WAIT:
            self._blocked_until = datetime.now(UTC).replace(tzinfo=None) + timedelta(seconds=wait)
            raise RateLimitError(self._blocked_until)
        return wait + 1

    async def request(self, method: str, url: str, **kwargs) -> dict | None:
        retryable = method in IDEMPOTENT_METHODS
        problem = ""
        async with self._slots:
            for attempt in range(MAX_ATTEMPTS):
                headers = {"Authorization": f"Bearer {await self._access_token()}"}
                await self._wait_for_turn()
                try:
                    response = await self._http.request(method, url, headers=headers, **kwargs)
                except httpx.TransportError as error:
                    if not retryable:
                        raise SpotifyError(f"{method} {url} failed: {error!r}") from error
                    problem = repr(error)
                    await asyncio.sleep(2 ** attempt)
                    continue
                if response.status_code == 429:
                    problem = "rate limited"
                    await asyncio.sleep(self._rate_limited(method, url, response))
                    continue
                if response.status_code == 401:
                    problem = "unauthorized"
                    self._token_expires_at = 0
                    continue
                if response.status_code >= 500 and retryable:
                    problem = f"status {response.status_code}"
                    await asyncio.sleep(2 ** attempt)
                    continue
                if response.is_error:
                    raise SpotifyError(f"{method} {url} failed ({response.status_code}): {response.text}")
                return response.json() if response.content else None
        raise SpotifyError(f"{method} {url} failed after {MAX_ATTEMPTS} attempts ({problem})")

    async def paginate(self, url: str, params: dict | None = None) -> AsyncIterator[list[dict]]:
        next_url: str | None = url
        while next_url:
            page = await self.request("GET", next_url, params=params)
            params = None
            yield [item for item in page["items"] if item]
            next_url = page["next"]

    async def find_artist(self, name: str) -> dict | None:
        result = await self.request("GET", "/search", params={"q": name, "type": "artist", "limit": 10})
        wanted = name.casefold()
        return next(
            (artist for artist in result["artists"]["items"] if artist and artist["name"].casefold() == wanted), None
        )

    async def artist_albums(self, artist_id: str, released_after: date | None) -> list[dict]:
        async def fetch_group(group: str) -> list[dict]:
            albums = []
            async for page in self.paginate(f"/artists/{artist_id}/albums", {"include_groups": group, "limit": 10}):
                albums.extend(page)
                if released_after and all(parse_release_date(album["release_date"]) < released_after for album in page):
                    break
            return albums

        groups = await gather_all(fetch_group(group) for group in ALBUM_GROUPS)
        return [album for group in groups for album in group]

    async def album_tracks(self, album_id: str) -> list[dict]:
        tracks = []
        async for page in self.paginate(f"/albums/{album_id}/tracks", {"limit": 50}):
            tracks.extend(page)
        return tracks

    async def resolve_playlist(self, target: str) -> str:
        if match := PLAYLIST_ID.search(target.split("?")[0].strip()):
            return match.group(1) or match.group(2)
        user_id = (await self.request("GET", "/me"))["id"]
        async for page in self.paginate("/me/playlists"):
            for playlist in page:
                if playlist["name"] == target and playlist["owner"]["id"] == user_id:
                    return playlist["id"]
        created = await self.request("POST", "/me/playlists", json={"name": target, "public": False})
        return created["id"]

    async def replace_playlist_items(self, playlist_id: str, uris: list[str]) -> None:
        url = f"/playlists/{playlist_id}/items"
        await self.request("PUT", url, json={"uris": uris[:PLAYLIST_CHUNK]})
        for start in range(PLAYLIST_CHUNK, len(uris), PLAYLIST_CHUNK):
            await self.request("POST", url, json={"uris": uris[start:start + PLAYLIST_CHUNK]})


spotify = Spotify()
