import { Link } from "react-router-dom";
import { api } from "../api";
import { formatDate } from "../format";
import { useAction, useLoader } from "../hooks";

export default function PlaylistsPage() {
  const { data: playlists, error, reload } = useLoader(api.playlists, []);
  const action = useAction();

  async function remove(id: number, name: string) {
    if (!confirm(`Delete the configuration "${name}"? The Spotify playlist itself is kept.`)) return;
    await action.run(() => api.deletePlaylist(id));
    reload();
  }

  return (
    <section>
      <div className="page-header">
        <h1>Playlists</h1>
        <Link className="button primary" to="/playlists/new">New playlist</Link>
      </div>
      {(error || action.error) && <p className="error">{error ?? action.error}</p>}
      {playlists?.length === 0 && <p className="muted">No playlist configured yet.</p>}
      {!!playlists?.length && (
        <table>
          <thead>
            <tr>
              <th>Name</th>
              <th>Spotify playlist</th>
              <th>Artists</th>
              <th>Every</th>
              <th>Last rotation</th>
              <th>Next rotation</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {playlists.map((p) => (
              <tr key={p.id}>
                <td>
                  <Link to={`/playlists/${p.id}`}>{p.name}</Link>
                  {!p.enabled && <span className="badge paused">paused</span>}
                  {p.last_error && <span className="badge danger" title={p.last_error}>error</span>}
                </td>
                <td className="muted">{p.spotify_target}</td>
                <td>{p.artist_count}</td>
                <td>{p.update_interval_days} d at {p.rotation_time}</td>
                <td>{formatDate(p.last_rotated_at)}</td>
                <td>{p.enabled ? formatDate(p.next_rotation_at) : <span className="muted">paused</span>}</td>
                <td className="actions">
                  <Link className="button" to={`/playlists/${p.id}/edit`}>Edit</Link>
                  <button className="danger" disabled={action.busy} onClick={() => remove(p.id, p.name)}>Delete</button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </section>
  );
}
