import { useState } from "react";
import { api } from "../api";
import { formatDuration } from "../format";
import InfoTip from "./InfoTip";
import { useAction, useDebounced, useLoader } from "../hooks";
import type { Catalog, CatalogAlbum, CatalogStatus, CatalogTrack } from "../types";

const STATUSES: Record<CatalogStatus, string> = {
  all: "All songs",
  eligible: "Eligible",
  new: "New releases",
  excluded: "Excluded",
  cooldown: "On cooldown",
  current: "In playlist",
};

export default function CatalogView({ playlistId, version }: { playlistId: number; version: number }) {
  const [artistId, setArtistId] = useState("");
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState<CatalogStatus>("all");
  const [page, setPage] = useState(1);
  const q = useDebounced(search);
  const { data: catalog, error, reload } = useLoader(
    () => api.catalog(playlistId, { artistId, q, status, page }),
    [playlistId, artistId, q, status, page, version],
  );
  const action = useAction();

  function filter(apply: () => void) {
    apply();
    setPage(1);
  }

  function goTo(target: number) {
    setPage(target);
    scrollTo(0, 0);
  }

  async function toggleAlbum(album: CatalogAlbum) {
    await action.run(() => api.setAlbumEnabled(playlistId, album.id, album.exclusion !== null));
    reload();
  }

  async function toggleTrack(track: CatalogTrack) {
    await action.run(() => api.setTrackEnabled(playlistId, track.id, track.exclusion !== null));
    reload();
  }

  return (
    <div className="stack">
      <div className="toolbar">
        <select aria-label="Artist" value={artistId} onChange={(e) => filter(() => setArtistId(e.target.value))}>
          <option value="">All artists</option>
          {catalog?.artists.map((artist) => (
            <option key={artist.id} value={artist.id}>
              {artist.name} ({artist.eligible}/{artist.total} eligible)
            </option>
          ))}
        </select>
        <select aria-label="Status" value={status} onChange={(e) => filter(() => setStatus(e.target.value as CatalogStatus))}>
          {Object.entries(STATUSES).map(([value, label]) => <option key={value} value={value}>{label}</option>)}
        </select>
        <input
          type="search"
          aria-label="Search"
          placeholder="Search songs or albums"
          value={search}
          onChange={(e) => filter(() => setSearch(e.target.value))}
        />
      </div>

      {(error || action.error) && <p className="error">{error ?? action.error}</p>}
      {!!catalog?.missing_artists.length && (
        <p className="notice">
          <strong>Not found:</strong> {catalog.missing_artists.join(", ")}
          <InfoTip text="Refresh the catalog, or check that the names exactly match Spotify." />
        </p>
      )}
      {catalog && catalog.total_tracks > 0 && <Pager catalog={catalog} onPage={setPage} />}
      {catalog?.total_tracks === 0 && <div className="empty-state">No songs match these filters.</div>}

      {catalog?.albums.map((album) => (
        <article key={album.id} className={album.exclusion ? "album disabled" : "album"}>
          <header className="album-header">
            {album.image_url
              ? <img className="album-cover" src={album.image_url} alt="" loading="lazy" />
              : <span className="album-cover" />}
            <div className="album-info">
              <h3 title={album.name}>{album.name}</h3>
              <small>{album.artist_name} · {album.album_type} · {album.release_date}</small>
            </div>
            <AlbumStatus album={album} />
            <button className="small" disabled={action.busy} onClick={() => toggleAlbum(album)}>
              {album.exclusion ? "Enable album" : "Disable album"}
            </button>
          </header>
          <div className="table-scroll">
            <table>
              <tbody>
                {album.tracks.map((track) => (
                  <tr key={track.id} className={track.exclusion ? "excluded" : undefined}>
                    <td className="track-name">{track.name}</td>
                    <td className="numeric muted">{formatDuration(track.duration)}</td>
                    <td className="numeric muted" title="Times played">{track.play_count}×</td>
                    <td><TrackStatus track={track} /></td>
                    <td className="cell-actions">
                      {track.excluded_by !== "album" && (
                        <button className="small ghost" disabled={action.busy} onClick={() => toggleTrack(track)}>
                          {track.exclusion ? "Enable" : "Disable"}
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </article>
      ))}

      {catalog && catalog.total_tracks > catalog.page_size && <Pager catalog={catalog} onPage={goTo} />}
    </div>
  );
}

function Pager({ catalog, onPage }: { catalog: Catalog; onPage: (page: number) => void }) {
  const pages = Math.max(1, Math.ceil(catalog.total_tracks / catalog.page_size));
  const first = (catalog.page - 1) * catalog.page_size + 1;
  const last = Math.min(catalog.page * catalog.page_size, catalog.total_tracks);
  return (
    <div className="pager">
      <span className="muted">
        {first}–{last} of {catalog.total_tracks} songs
      </span>
      {pages > 1 && (
        <div className="row">
          <button className="small" disabled={catalog.page <= 1} onClick={() => onPage(catalog.page - 1)}>Previous</button>
          <span className="muted">Page {catalog.page} of {pages}</span>
          <button className="small" disabled={catalog.page >= pages} onClick={() => onPage(catalog.page + 1)}>Next</button>
        </div>
      )}
    </div>
  );
}

function AlbumStatus({ album }: { album: CatalogAlbum }) {
  if (album.excluded_by === "auto") return <span className="badge warning">Excluded: {album.exclusion}</span>;
  if (album.excluded_by === "user") return <span className="badge warning">Album disabled</span>;
  if (album.forced) return <span className="badge info">Enabled manually</span>;
  return null;
}

function TrackStatus({ track }: { track: CatalogTrack }) {
  if (track.exclusion) return <span className="badge">{track.exclusion}</span>;
  return (
    <span className="badges">
      {track.forced && <span className="badge info">Enabled manually</span>}
      {track.new_release && <span className="badge info">New release</span>}
      {track.current && <span className="badge accent">In playlist</span>}
      {track.cooldown > 0 && <span className="badge warning">Cooldown {track.cooldown}</span>}
      {!track.current && track.cooldown === 0 && <span className="badge success">Eligible</span>}
    </span>
  );
}
