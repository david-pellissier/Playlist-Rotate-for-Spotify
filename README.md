# Spotify Playlist Rotate

Keeps Spotify playlists fresh by rotating songs from a list of artists. Every artist gets the same number
of songs, new releases are prioritized, and played songs go on cooldown until the artist's catalog has cycled.
A local web manager lets you configure playlists, browse the cached catalog, disable albums or songs and
preview rotations.

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
3. Start the app:

   ```bash
   docker compose up -d --build
   ```

4. Open <http://127.0.0.1:8000/settings>, click **Authorize with Spotify**, put the displayed
   `SPOTIFY_REFRESH_TOKEN` in `.env` and restart:

   ```bash
   docker compose up -d
   ```

The database lives in `./data/spotify.db`.

## Web manager

- **Playlists:** create, edit, delete and pause playlist configurations.
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
| `DATABASE_PATH` | `/data/spotify.db` | SQLite file |

## Development

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
