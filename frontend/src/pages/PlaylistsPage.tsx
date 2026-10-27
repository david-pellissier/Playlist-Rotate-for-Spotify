import { Link, useNavigate } from "react-router-dom";
import { api } from "../api";
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
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Playlist</th>
                <th className="hide-sm">Status</th>
                <th className="numeric hide-sm">Artists</th>
                <th className="hide-sm">Schedule</th>
                <th className="hide-sm">Last rotation</th>
                <th className="hide-sm">Next rotation</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {playlists.map((p) => (
                <tr key={p.id}>
                  <td>
                    <div className="cell-playlist">
                      <PlaylistCover name={p.name} url={p.cover_url} />
                      <div className="cell-title">
                        <Link to={`/playlists/${p.id}`}>{p.name}</Link>
                        <small>{p.spotify_target}</small>
                        <span className="show-sm"><PlaylistStatus enabled={p.enabled} error={p.last_error} /></span>
                      </div>
                    </div>
                  </td>
                  <td className="hide-sm"><PlaylistStatus enabled={p.enabled} error={p.last_error} /></td>
                  <td className="numeric hide-sm">{p.artist_count}</td>
                  <td className="nowrap hide-sm">{formatSchedule(p.update_interval_days, p.rotation_time)}</td>
                  <td className="nowrap hide-sm">{formatDate(p.last_rotated_at)}</td>
                  <td className="nowrap hide-sm">{p.enabled ? formatDate(p.next_rotation_at) : <span className="muted">—</span>}</td>
                  <td className="cell-actions">
                    <Link className="button small" to={`/playlists/${p.id}/edit`}>Edit</Link>
                    <button className="small danger" disabled={action.busy} onClick={() => remove(p.id, p.name)}>
                      Delete
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
