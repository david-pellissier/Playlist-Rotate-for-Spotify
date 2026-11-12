import { formatDuration } from "../format";
import type { CatalogAlbum, CatalogTrack } from "../types";
import Toggle from "./Toggle";

export default function AlbumCard({ album, open, busy, onToggleOpen, onToggleAlbum, onToggleTrack }: {
  album: CatalogAlbum;
  open: boolean;
  busy: boolean;
  onToggleOpen: () => void;
  onToggleAlbum: () => void;
  onToggleTrack: (track: CatalogTrack) => void;
}) {
  const eligible = album.tracks.filter((track) => !track.exclusion).length;
  return (
    <article className={album.exclusion ? "album disabled" : "album"}>
      <header className={open ? "album-header" : "album-header collapsed"}>
        <Toggle open={open} label={album.name} onClick={onToggleOpen} />
        {album.image_url
          ? <img className="album-cover" src={album.image_url} alt="" loading="lazy" />
          : <span className="album-cover" />}
        <div className="album-info">
          <h3 title={album.name}>{album.name}</h3>
          <small>
            {album.album_type} · {album.release_date} · {album.tracks.length} {album.tracks.length === 1 ? "song" : "songs"},{" "}
            {eligible} eligible
          </small>
        </div>
        <AlbumStatus album={album} />
        <button className="small" disabled={busy} onClick={onToggleAlbum}>
          {album.exclusion ? "Enable album" : "Disable album"}
        </button>
      </header>
      {open && (
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
                      <button className="small ghost" disabled={busy} onClick={() => onToggleTrack(track)}>
                        {track.exclusion ? "Enable" : "Disable"}
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </article>
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
      {!track.current && track.cooldown === 0 && <span className="badge success">Available</span>}
    </span>
  );
}
