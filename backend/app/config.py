import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class Env:
    client_id: str
    client_secret: str
    refresh_token: str
    redirect_uri: str
    database_path: Path
    frontend_dist: Path
    scheduler_poll_seconds: int


env = Env(
    client_id=os.getenv("SPOTIFY_CLIENT_ID", ""),
    client_secret=os.getenv("SPOTIFY_CLIENT_SECRET", ""),
    refresh_token=os.getenv("SPOTIFY_REFRESH_TOKEN", ""),
    redirect_uri=os.getenv("SPOTIFY_REDIRECT_URI", "http://127.0.0.1:8000/api/auth/callback"),
    database_path=Path(os.getenv("DATABASE_PATH", "data/spotify.db")),
    frontend_dist=Path(os.getenv("FRONTEND_DIST", "../frontend/dist")),
    scheduler_poll_seconds=int(os.getenv("SCHEDULER_POLL_SECONDS", "600")),
)
