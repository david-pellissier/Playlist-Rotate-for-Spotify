import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api } from "../api";
import ImportPlaylist from "../components/ImportPlaylist";
import PlaylistCover from "../components/PlaylistCover";
import ScheduleToggle from "../components/ScheduleToggle";
import { formatShortDate } from "../format";
import { useCoverAccent } from "../coverAccent";
import { useAction, useLoader } from "../hooks";
import type { PlaylistSummary } from "../types";

export default function PlaylistsPage() {
  const { data: playlists, error, reload } = useLoader(api.playlists, []);
  const action = useAction();
  const [rotatingId, setRotatingId] = useState<number>();
  const navigate = useNavigate();

  async function rotate(playlist: PlaylistSummary) {
    if (!confirm(`Replace the content of "${playlist.name}" on Spotify now?`)) return;
    setRotatingId(playlist.id);
    await action.run(() => api.rotate(playlist.id, false));
    setRotatingId(undefined);
    reload();
  }

  async function toggleSchedule(playlist: PlaylistSummary) {
    await action.run(() => api.setEnabled(playlist.id, !playlist.enabled));
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
          <Link className="button" to="/settings">Settings</Link>
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
            <PlaylistCard
              key={p.id}
              playlist={p}
              busy={action.busy}
              rotating={rotatingId === p.id}
              onToggle={() => toggleSchedule(p)}
              onRotate={() => rotate(p)}
            />
          ))}
        </div>
      )}
    </section>
  );
}

function PlaylistCard({ playlist: p, busy, rotating, onToggle, onRotate }: {
  playlist: PlaylistSummary;
  busy: boolean;
  rotating: boolean;
  onToggle: () => void;
  onRotate: () => void;
}) {
  const accent = useCoverAccent(p.cover_url);
  return (
    <article className={accent ? "playlist-card themed" : "playlist-card"} style={accent}>
      <div className="playlist-card-art">
        <Link to={`/playlists/${p.id}`} tabIndex={-1} aria-hidden="true">
          <PlaylistCover name={p.name} url={p.cover_url} size="fill" />
        </Link>
        <div className="playlist-card-overlay">
          <div className="playlist-card-title">
            <h2><Link to={`/playlists/${p.id}`}>{p.name}</Link></h2>
            <CardStatus playlist={p} />
          </div>
          <ScheduleToggle enabled={p.enabled} error={p.last_error} busy={busy} compact onToggle={onToggle} />
        </div>
      </div>
      <p className="playlist-card-meta">
        {p.artist_count} {p.artist_count === 1 ? "artist" : "artists"} ·{" "}
        {p.update_interval_days === 1 ? "daily" : `every ${p.update_interval_days} days`}
      </p>
      <div className="playlist-card-actions">
        <button className="primary small" disabled={busy} onClick={onRotate}>{rotating ? "Rotating…" : "Rotate now"}</button>
        <Link className="button small" to={`/playlists/${p.id}/edit`}>Edit</Link>
      </div>
    </article>
  );
}

function CardStatus({ playlist: p }: { playlist: PlaylistSummary }) {
  if (p.last_error) return <p className="playlist-card-status failing" title={p.last_error}>Last rotation failed</p>;
  if (!p.enabled) return <p className="playlist-card-status">Paused</p>;
  return <p className="playlist-card-status">Next · {formatShortDate(p.next_rotation_at)}</p>;
}
