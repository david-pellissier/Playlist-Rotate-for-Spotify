import asyncio
import re
import time
from collections.abc import AsyncIterator
from datetime import date
from urllib.parse import urlencode

import httpx

from .config import env

API_URL = "https://api.spotify.com/v1"
AUTHORIZE_URL = "https://accounts.spotify.com/authorize"
TOKEN_URL = "https://accounts.spotify.com/api/token"
SCOPES = "playlist-read-private playlist-modify-public playlist-modify-private"
ALBUM_GROUPS = ("album", "single")
PLAYLIST_ID = re.compile(r"(?:playlist[/:])([A-Za-z0-9]{22})|^([A-Za-z0-9]{22})$")
MAX_RETRIES = 5
MAX_CONCURRENCY = 8
PLAYLIST_CHUNK = 100


class SpotifyError(Exception):
    pass


def parse_release_date(value: str) -> date:
    parts = [int(part) for part in value.split("-")] + [1, 1]
    return date(*parts[:3])


class Spotify:
    def __init__(self) -> None:
        self._http = httpx.AsyncClient(base_url=API_URL, timeout=30)
        self._token = ""
        self._token_expires_at = 0.0
        self._token_lock = asyncio.Lock()
        self._slots = asyncio.Semaphore(MAX_CONCURRENCY)

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
        response = await self._http.post(
            TOKEN_URL,
            data={"grant_type": "authorization_code", "code": code, "redirect_uri": env.redirect_uri},
            auth=(env.client_id, env.client_secret),
        )
        if response.is_error:
            raise SpotifyError(f"Authorization failed: {response.text}")
        return response.json()["refresh_token"]

    async def _access_token(self) -> str:
        async with self._token_lock:
            if time.monotonic() < self._token_expires_at:
                return self._token
            if not (env.client_id and env.client_secret and env.refresh_token):
                raise SpotifyError("Spotify credentials are missing from the environment")
            response = await self._http.post(
                TOKEN_URL,
                data={"grant_type": "refresh_token", "refresh_token": env.refresh_token},
                auth=(env.client_id, env.client_secret),
            )
            if response.is_error:
                raise SpotifyError(f"Token refresh failed: {response.text}")
            payload = response.json()
            self._token = payload["access_token"]
            self._token_expires_at = time.monotonic() + payload["expires_in"] - 60
            return self._token

    async def request(self, method: str, url: str, **kwargs) -> dict | None:
        async with self._slots:
            for _ in range(MAX_RETRIES):
                headers = {"Authorization": f"Bearer {await self._access_token()}"}
                response = await self._http.request(method, url, headers=headers, **kwargs)
                if response.status_code == 429:
                    await asyncio.sleep(int(response.headers.get("Retry-After", "1")) + 1)
                    continue
                if response.status_code == 401:
                    self._token_expires_at = 0
                    continue
                if response.is_error:
                    raise SpotifyError(f"{method} {url} failed ({response.status_code}): {response.text}")
                return response.json() if response.content else None
        raise SpotifyError(f"{method} {url} failed after {MAX_RETRIES} attempts")

    async def paginate(self, url: str, params: dict | None = None) -> AsyncIterator[list[dict]]:
        next_url: str | None = url
        while next_url:
            page = await self.request("GET", next_url, params=params)
            params = None
            yield page["items"]
            next_url = page["next"]

    async def find_artist(self, name: str) -> dict | None:
        result = await self.request("GET", "/search", params={"q": name, "type": "artist", "limit": 10})
        wanted = name.casefold()
        return next((artist for artist in result["artists"]["items"] if artist["name"].casefold() == wanted), None)

    async def artist_albums(self, artist_id: str, released_after: date | None) -> list[dict]:
        async def fetch_group(group: str) -> list[dict]:
            albums = []
            async for page in self.paginate(f"/artists/{artist_id}/albums", {"include_groups": group, "limit": 10}):
                albums.extend(page)
                if released_after and all(parse_release_date(album["release_date"]) < released_after for album in page):
                    break
            return albums

        groups = await asyncio.gather(*(fetch_group(group) for group in ALBUM_GROUPS))
        return [album for group in groups for album in group]

    async def album_tracks(self, album_id: str) -> list[dict]:
        tracks = []
        async for page in self.paginate(f"/albums/{album_id}/tracks", {"limit": 50}):
            tracks.extend(page)
        return tracks

    async def resolve_playlist(self, target: str) -> str:
        if match := PLAYLIST_ID.search(target.split("?")[0].strip()):
            return match.group(1) or match.group(2)
        async for page in self.paginate("/me/playlists"):
            for playlist in page:
                if playlist and playlist["name"] == target:
                    return playlist["id"]
        created = await self.request("POST", "/me/playlists", json={"name": target, "public": False})
        return created["id"]

    async def replace_playlist_items(self, playlist_id: str, uris: list[str]) -> None:
        url = f"/playlists/{playlist_id}/items"
        await self.request("PUT", url, json={"uris": uris[:PLAYLIST_CHUNK]})
        for start in range(PLAYLIST_CHUNK, len(uris), PLAYLIST_CHUNK):
            await self.request("POST", url, json={"uris": uris[start:start + PLAYLIST_CHUNK]})


spotify = Spotify()
