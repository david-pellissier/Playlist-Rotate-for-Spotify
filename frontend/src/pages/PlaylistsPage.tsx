import { Link, useNavigate } from "react-router-dom";
import { api } from "../api";
import Icon from "../components/Icon";
import ImportPlaylist from "../components/ImportPlaylist";
import PlaylistCover from "../components/PlaylistCover";
import PlaylistStatus from "../components/PlaylistStatus";
import { formatDate, formatSchedule } from "../format";
import { useAction, useLoader } from "../hooks";

export default function PlaylistsPage() {
  const { data: playlists, error, reload } = useLoader(api.playlists, []);
  const action = useAction();
  const navigate = useNavigate();

  async function remove(id: number, name: string) {
    if (!confirm(`Delete the configuration "${name}"? The Spotify playlist itself is kept.`)) return;
    await action.run(() => api.deletePlaylist(id));
    reload();
  }

  return (
    <section className="stack">
      <div className="page-header">
        <div className="page-title">
          <h1>Playlists</h1>
          {!!playlists?.length && (
            <p className="muted">
              {playlists.length} {playlists.length === 1 ? "playlist" : "playlists"} · {playlists.filter((p) => p.enabled).length} on schedule
            </p>
          )}
        </div>
        <div className="actions">
          <ImportPlaylist onImported={(playlist) => navigate(`/playlists/${playlist.id}`)} />
          <Link className="button primary" to="/playlists/new">New playlist</Link>
        </div>
      </div>

      {(error || action.error) && <p className="error">{error ?? action.error}</p>}
      {!playlists && !error && <p className="muted">Loading…</p>}

      {playlists?.length === 0 && (
        <div className="empty-state">
          <h2>No playlists yet</h2>
          <Link className="button primary" to="/playlists/new">New playlist</Link>
        </div>
      )}

      {!!playlists?.length && (
        <div className="playlist-grid">
          {playlists.map((p) => (
            <article key={p.id} className="playlist-card">
              <Link to={`/playlists/${p.id}`} className="playlist-card-link">
                <PlaylistCover name={p.name} url={p.cover_url} size="fill" />
                <div className="playlist-card-title">
                  <h2>{p.name}</h2>
                  {p.spotify_target !== p.name && <small>{p.spotify_target}</small>}
                </div>
              </Link>
              <div className="playlist-card-meta">
                <span><Icon name="users" />{p.artist_count} {p.artist_count === 1 ? "artist" : "artists"}</span>
                <span><Icon name="repeat" />{formatSchedule(p.update_interval_days, p.rotation_time)}</span>
                <span><Icon name="calendar" />{p.enabled ? `Next: ${formatDate(p.next_rotation_at)}` : "No scheduled rotation"}</span>
              </div>
              <div className="playlist-card-footer">
                <PlaylistStatus enabled={p.enabled} error={p.last_error} />
                <div className="actions">
                  <Link className="button small" to={`/playlists/${p.id}/edit`}>Edit</Link>
                  <button className="small ghost danger" disabled={action.busy} onClick={() => remove(p.id, p.name)}>
                    Delete
                  </button>
                </div>
              </div>
            </article>
          ))}
        </div>
      )}
    </section>
  );
}
