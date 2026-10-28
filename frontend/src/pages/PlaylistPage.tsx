import { type CSSProperties, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api } from "../api";
import CatalogView from "../components/CatalogView";
import Icon, { type IconName } from "../components/Icon";
import HistoryView from "../components/HistoryView";
import JobProgress, { useJobProgress } from "../components/JobProgress";
import Menu from "../components/Menu";
import PlaylistCover from "../components/PlaylistCover";
import PlaylistStatus from "../components/PlaylistStatus";
import RotationView from "../components/RotationView";
import { formatDate, formatSchedule } from "../format";
import { useAction, useLoader } from "../hooks";
import type { Rotation } from "../types";

type Tab = "songs" | "rotation" | "history";

export default function PlaylistPage() {
  const id = Number(useParams().id);
  const { data: playlist, error, reload } = useLoader(() => api.playlist(id), [id]);
  const [tab, setTab] = useState<Tab>("songs");
  const [rotation, setRotation] = useState<Rotation>();
  const [catalogVersion, setCatalogVersion] = useState(0);
  const action = useAction();
  const progress = useJobProgress(id, action.busy, () => {
    reload();
    setCatalogVersion((v) => v + 1);
  });
  const working = action.busy || progress !== null;

  async function rotate(dryRun: boolean) {
    if (!dryRun && !confirm("Replace the Spotify playlist content now?")) return;
    const result = await action.run(() => api.rotate(id, dryRun));
    if (result) {
      setRotation(result);
      setTab("rotation");
    }
    reload();
    setCatalogVersion((v) => v + 1);
  }

  async function refresh() {
    await action.run(() => api.sync(id));
    setCatalogVersion((v) => v + 1);
  }

  async function resumeSchedule() {
    await action.run(() => api.updatePlaylist(id, { ...playlist!, enabled: true }));
    reload();
  }

  async function clearCooldowns() {
    if (!confirm("Reset the cooldown of every song in this playlist?")) return;
    await action.run(() => api.clearCooldowns(id));
    setCatalogVersion((v) => v + 1);
  }

  if (error) return <p className="error">{error}</p>;
  if (!playlist) return <p className="muted">Loading…</p>;
  const artistsPerRotation = Math.min(playlist.max_artists ?? Infinity, playlist.artist_names.length);

  return (
    <section className="stack">
      <Link to="/" className="back-link">← Playlists</Link>
      <div
        className="page-header playlist-hero"
        style={playlist.cover_url ? ({ "--hero-image": `url("${playlist.cover_url}")` } as CSSProperties) : undefined}
      >
        <div className="hero-glow" aria-hidden="true" />
        <div className="hero-main">
          <PlaylistCover name={playlist.name} url={playlist.cover_url} size="large" />
          <div className="page-title">
            <span className="hero-eyebrow">Playlist</span>
            <h1>
              {playlist.name}
              <PlaylistStatus enabled={playlist.enabled} error={playlist.last_error} />
            </h1>
            <p className="muted">{playlist.spotify_target}</p>
          </div>
        </div>
        <div className="actions">
          <Link className="button" to={`/playlists/${id}/edit`}>Edit</Link>
          <Menu label="More">
            <button disabled={working} onClick={refresh}>Refresh catalog</button>
            <button disabled={working} onClick={clearCooldowns}>Clear cooldowns</button>
            <a className="button" href={api.exportUrl(id)} download>Export configuration</a>
          </Menu>
          <button disabled={working} onClick={() => rotate(true)}>Dry run</button>
          <button className="primary" disabled={working} onClick={() => rotate(false)}>Rotate now</button>
        </div>
      </div>

      <div className="stats">
        <Stat icon="calendar" label="Next rotation" value={playlist.enabled ? formatDate(playlist.next_rotation_at) : "Paused"} />
        <Stat icon="repeat" label="Schedule" value={formatSchedule(playlist.update_interval_days, playlist.rotation_time)} />
        <Stat
          icon="music"
          label="Songs per rotation"
          value={String(artistsPerRotation * playlist.songs_per_artist)}
          hint={`${artistsPerRotation} of ${playlist.artist_names.length} artists × ${playlist.songs_per_artist}`}
        />
        <Stat icon="clock" label="Last rotation" value={formatDate(playlist.last_rotated_at)} />
      </div>

      {!playlist.enabled && (
        <div className="notice banner">
          <span><strong>Paused.</strong> Manual rotations only.</span>
          <button className="small" disabled={working} onClick={resumeSchedule}>Resume schedule</button>
        </div>
      )}
      {progress ? <JobProgress progress={progress} /> : action.busy && <p className="muted">Working…</p>}
      {action.error && <p className="error">{action.error}</p>}
      {playlist.last_error && <p className="error"><strong>Last rotation failed:</strong> {playlist.last_error}</p>}

      <div className="tabs" role="tablist">
        <TabButton active={tab === "songs"} onClick={() => setTab("songs")}>Songs</TabButton>
        <TabButton active={tab === "rotation"} onClick={() => setTab("rotation")}>Rotation preview</TabButton>
        <TabButton active={tab === "history"} onClick={() => setTab("history")}>History</TabButton>
      </div>

      {tab === "songs" && <CatalogView playlistId={id} albumsOnly={playlist.albums_only} version={catalogVersion} />}
      {tab === "history" && <HistoryView playlistId={id} version={catalogVersion} />}
      {tab === "rotation" && (rotation
        ? <RotationView rotation={rotation} />
        : (
          <div className="empty-state">
            <h2>No preview yet</h2>
            <button disabled={working} onClick={() => rotate(true)}>Run a dry run</button>
          </div>
        ))}
    </section>
  );
}

function Stat({ icon, label, value, hint }: { icon: IconName; label: string; value: string; hint?: string }) {
  return (
    <div className="stat">
      <span className="stat-icon"><Icon name={icon} size={20} /></span>
      <div className="stat-text">
        <span className="stat-label">{label}</span>
        <span className="stat-value">{value}</span>
        {hint && <small>{hint}</small>}
      </div>
    </div>
  );
}

function TabButton({ active, onClick, children }: { active: boolean; onClick: () => void; children: string }) {
  return (
    <button role="tab" aria-selected={active} className={active ? "active" : ""} onClick={onClick}>
      {children}
    </button>
  );
}
