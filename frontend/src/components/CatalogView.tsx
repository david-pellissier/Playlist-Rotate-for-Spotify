import { useState } from "react";
import { api } from "../api";
import { formatDuration } from "../format";
import { useAction, useDebounced, useLoader } from "../hooks";
import type { CatalogAlbum, CatalogStatus, CatalogTrack } from "../types";

const STATUSES: Record<CatalogStatus, string> = {
  all: "All songs",
  eligible: "Eligible",
  excluded: "Excluded",
  cooldown: "On cooldown",
  current: "In playlist",
};

export default function CatalogView({ playlistId, version }: { playlistId: number; version: number }) {
  const [artistId, setArtistId] = useState("");
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState<CatalogStatus>("all");
  const q = useDebounced(search);
  const { data: catalog, error, reload } = useLoader(
    () => api.catalog(playlistId, { artistId, q, status }),
    [playlistId, artistId, q, status, version],
  );
  const action = useAction();

  async function toggleAlbum(album: CatalogAlbum) {
    await action.run(() => api.toggleAlbum(playlistId, album.id, !album.disabled));
    reload();
  }

  async function toggleTrack(track: CatalogTrack) {
    await action.run(() => api.toggleTrack(playlistId, track.id, !track.disabled));
    reload();
  }

  return (
    <div className="stack">
      <div className="inline">
        <select value={artistId} onChange={(e) => setArtistId(e.target.value)}>
          <option value="">All artists</option>
          {catalog?.artists.map((artist) => (
            <option key={artist.id} value={artist.id}>
              {artist.name} ({artist.eligible}/{artist.total} eligible, {artist.on_cooldown} on cooldown)
            </option>
          ))}
        </select>
        <select value={status} onChange={(e) => setStatus(e.target.value as CatalogStatus)}>
          {Object.entries(STATUSES).map(([value, label]) => <option key={value} value={value}>{label}</option>)}
        </select>
        <input type="search" placeholder="Search songs or albums" value={search} onChange={(e) => setSearch(e.target.value)} />
      </div>

      {(error || action.error) && <p className="error">{error ?? action.error}</p>}
      {!!catalog?.missing_artists.length && (
        <p className="notice">
          Not in the catalog yet (refresh it, or check the exact name): {catalog.missing_artists.join(", ")}
        </p>
      )}
      {catalog?.truncated && <p className="notice">Too many results, refine the search to see everything.</p>}
      {catalog?.albums.length === 0 && <p className="muted">No songs match.</p>}

      {catalog?.albums.map((album) => (
        <article key={album.id} className={`album ${album.disabled ? "disabled" : ""}`}>
          <header>
            {album.image_url && <img src={album.image_url} alt="" width={48} height={48} loading="lazy" />}
            <div>
              <h3>{album.name}</h3>
              <p className="muted">{album.artist_name} · {album.album_type} · {album.release_date}</p>
            </div>
            <button disabled={action.busy} onClick={() => toggleAlbum(album)}>
              {album.disabled ? "Enable album" : "Disable album"}
            </button>
          </header>
          <table>
            <tbody>
              {album.tracks.map((track) => (
                <tr key={track.id} className={track.exclusion ? "excluded" : ""}>
                  <td>{track.name}</td>
                  <td className="muted">{formatDuration(track.duration)}</td>
                  <td className="muted" title="Times played">{track.play_count}×</td>
                  <td><TrackStatus track={track} /></td>
                  <td className="actions">
                    <button className="link" disabled={action.busy} onClick={() => toggleTrack(track)}>
                      {track.disabled ? "Enable" : "Disable"}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </article>
      ))}
    </div>
  );
}

function TrackStatus({ track }: { track: CatalogTrack }) {
  if (track.exclusion) return <span className="muted">{track.exclusion}</span>;
  return (
    <>
      {track.current && <span className="badge current">in playlist</span>}
      {track.cooldown > 0 && <span className="badge cooldown">cooldown {track.cooldown}</span>}
      {!track.current && track.cooldown === 0 && <span className="badge new">eligible</span>}
    </>
  );
}
