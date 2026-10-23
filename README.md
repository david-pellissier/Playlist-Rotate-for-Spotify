# Spotify Playlist Rotate

Keeps Spotify playlists fresh by rotating songs from a list of artists. Every artist gets the same number
of songs, new releases are prioritized, and played songs go on cooldown until the artist's catalog has cycled.
It runs as two containers:

- **daemon:** runs 24/7. It owns the database, talks to Spotify, rotates playlists on schedule and serves the
  API. It publishes no port.
- **web:** an nginx container serving the manager UI and forwarding `/api` to the daemon. Start it when you
  want to change something and stop it the rest of the time. Scheduled rotations don't need it.

## How it works

1. **Catalog cache:** artists are resolved by exact name (case-insensitive) via Spotify search. Their albums
   and singles are stored in SQLite. Later refreshes only page through recent releases (catalog refresh
   lookback) and download tracks of albums not yet cached.
2. **Eligibility:** every track is kept in the database. A track is excluded from a playlist when:
   - its album or the track itself was disabled in that playlist,
   - the artist is only a guest (not the first credited artist),
   - it has featured artists and the playlist excludes featurings,
   - it is shorter or longer than the playlist duration limits,
   - its title or album title matches a keyword (whole word) or regex rule,
   - it duplicates another version of the same song. The album version is kept over singles and EPs,
     and the original release is kept over later re-releases (deluxe, anniversary...).
3. **Selection:** for each artist, up to *max new releases* songs released since the last rotation and never
   played come first, then the least-played songs that are off cooldown, picked at random. If an artist runs
   short, songs closest to the end of their cooldown fill the gap, so every artist has the same count.
4. **Cooldown:** a picked song sits out the next `max(min cooldown, eligible songs / songs per artist - 1)`
   rotations, so an artist's whole catalog cycles before a song repeats. Cooldowns are per playlist.
5. **Schedule:** an active playlist first rotates on its first rotation date at its rotation time (in `TZ`), then
   every *N* days at the same time. Rotating by hand doesn't move the schedule. A paused playlist keeps its
   schedule but only rotates when you click "Rotate now".

## Setup

1. Create an app in the [Spotify Developer Dashboard](https://developer.spotify.com/dashboard) and add
   `http://127.0.0.1:8000/api/auth/callback` as a redirect URI.
2. Copy `.env.example` to `.env` and fill in `SPOTIFY_CLIENT_ID` and `SPOTIFY_CLIENT_SECRET`.
3. Start the daemon and the web manager:

   ```bash
   docker compose up -d --build
   ```

4. Open <http://127.0.0.1:8000/settings>, click **Authorize with Spotify**, put the displayed
   `SPOTIFY_REFRESH_TOKEN` in `.env` and restart the daemon:

   ```bash
   docker compose up -d daemon
   ```

The database lives in `./data/spotify.db`. Don't open it in another program while the daemon is running.
If Spotify ever issues a new refresh token, the daemon saves it to `./data/spotify_token.json` and uses it
until you put a different token in `.env`.

## Daily use

`docker compose up -d` creates and starts both containers. Both come back after a reboot, unless you stopped
them. Stop the web manager when you don't need it; scheduled rotations keep running:

```bash
docker compose stop web
```

Start it again when you want to change something:

```bash
docker compose start web
```

Running `docker compose up -d` again (for example after an update) also starts the web manager, so stop it
afterwards if you want it off.

## Deploying on a server

- Spotify only accepts `http` redirect URIs on `127.0.0.1`. Do the authorization once on your own computer
  as described above, then copy the `.env` values to the server.
- Set `WEB_BIND` to the address the manager should listen on, e.g. your VPN interface IP. The manager has no
  login, so never expose it publicly.
- Failures are only reported in the daemon's logs, and in the playlist page's "Last rotation failed" message.
  A failed scheduled rotation is retried an hour later, up to `SCHEDULER_MAX_RETRIES` times. After that it
  waits for the next scheduled rotation. Container logs are capped at 3 files of 5 MB each.

  ```bash
  docker compose logs daemon
  ```

## Web manager

- **Playlists:** create, edit, delete and pause playlist configurations. Export a configuration to a JSON
  file and import it back. If a playlist with the same name exists, you choose between erasing its
  configuration and importing a paused copy.
- **Playlist page:**
  - refresh the catalog,
  - preview the next rotation (dry run) or rotate now,
  - clear cooldowns,
  - browse, search and filter songs by artist and status, disable albums or songs.
- **Settings:** minimum cooldown, catalog refresh lookback, default filters for new playlists, global rules.

## Configuration

| Variable | Default | Description |
|---|---|---|
| `SPOTIFY_CLIENT_ID` | | Spotify app client ID |
| `SPOTIFY_CLIENT_SECRET` | | Spotify app client secret |
| `SPOTIFY_REFRESH_TOKEN` | | Obtained once through the Settings page |
| `SPOTIFY_REDIRECT_URI` | `http://127.0.0.1:8000/api/auth/callback` | Must match the app settings |
| `TZ` | `UTC` | Timezone of the playlists' rotation times, e.g. `Europe/Zurich` |
| `SCHEDULER_POLL_SECONDS` | `60` | How often due playlists are checked |
| `SCHEDULER_MAX_RETRIES` | `1` | Hourly retries of a failed scheduled rotation before waiting for the next one |
| `WEB_BIND` | `127.0.0.1` | Address the web manager listens on |
| `WEB_PORT` | `8000` | Port the web manager listens on |
| `DATABASE_PATH` | `/data/spotify.db` | SQLite file |

## Development

Requires Python 3.12+ and Node 22.

```bash
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload
```

```bash
cd frontend
npm install
npm run dev
```

The Vite dev server proxies `/api` to the backend on port 8000.

## Spotify API notes

This targets the Web API as it is after the February 2026 Development Mode changes. It uses
`/playlists/{id}/items` and `POST /me/playlists`, and does not rely on batch endpoints. Duplicates are
detected by normalized title instead of ISRC, because ISRCs would require one request per track.
