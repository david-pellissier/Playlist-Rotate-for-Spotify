import asyncio
import contextlib
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from .api import playlists, settings
from .config import env
from .models import init_db
from .scheduler import run_scheduler
from .spotify import SpotifyError, spotify

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logging.getLogger("httpx").setLevel(logging.WARNING)


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    scheduler = asyncio.create_task(run_scheduler())
    yield
    scheduler.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await scheduler
    await spotify.close()


app = FastAPI(title="Spotify Playlist Rotate", lifespan=lifespan)
app.include_router(settings.router)
app.include_router(playlists.router)


@app.exception_handler(SpotifyError)
async def spotify_error(_: Request, error: SpotifyError):
    return JSONResponse({"detail": str(error)}, status_code=502)


@app.exception_handler(ValueError)
async def value_error(_: Request, error: ValueError):
    return JSONResponse({"detail": str(error)}, status_code=400)


if env.frontend_dist.is_dir():
    dist = env.frontend_dist.resolve()
    app.mount("/assets", StaticFiles(directory=dist / "assets"), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    async def spa(path: str):
        file = (dist / path).resolve()
        return FileResponse(file if file.is_file() and file.is_relative_to(dist) else dist / "index.html")
