import asyncio
import contextlib
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from .api import playlists, settings, transfer
from .models import init_db
from .scheduler import run_scheduler
from .rotation import RotationError
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
app.include_router(transfer.router)
app.include_router(playlists.router)


@app.exception_handler(SpotifyError)
async def spotify_error(_: Request, error: SpotifyError):
    return JSONResponse({"detail": str(error)}, status_code=502)


@app.exception_handler(RotationError)
async def rotation_error(_: Request, error: RotationError):
    return JSONResponse({"detail": str(error)}, status_code=400)
