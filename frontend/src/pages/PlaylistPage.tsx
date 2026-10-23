import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api } from "../api";
import CatalogView from "../components/CatalogView";
import JobProgress, { useJobProgress } from "../components/JobProgress";
import RotationView from "../components/RotationView";
import { formatDate } from "../format";
import { useAction, useLoader } from "../hooks";
import type { Rotation } from "../types";

type Tab = "songs" | "rotation";

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

  async function clearCooldowns() {
    if (!confirm("Reset the cooldown of every song in this playlist?")) return;
    await action.run(() => api.clearCooldowns(id));
    setCatalogVersion((v) => v + 1);
  }

  if (error) return <p className="error">{error}</p>;
  if (!playlist) return <p className="muted">Loading…</p>;

  return (
    <section className="stack">
      <div className="page-header">
        <div>
          <h1>{playlist.name}</h1>
          <p className="muted">
            {playlist.spotify_target} · {playlist.artist_names.length} artists · {playlist.songs_per_artist} songs each ·
            every {playlist.update_interval_days} d at {playlist.rotation_time} · last rotation {formatDate(playlist.last_rotated_at)}
          </p>
        </div>
        <div className="actions">
          <Link className="button" to={`/playlists/${id}/edit`}>Edit</Link>
          <button disabled={working} onClick={refresh}>Refresh catalog</button>
          <button disabled={working} onClick={clearCooldowns}>Clear cooldowns</button>
          <button disabled={working} onClick={() => rotate(true)}>Dry run</button>
          <button className="primary" disabled={working} onClick={() => rotate(false)}>Rotate now</button>
        </div>
      </div>

      {progress ? <JobProgress progress={progress} /> : action.busy && <p className="muted">Working…</p>}
      {action.error && <p className="error">{action.error}</p>}
      {playlist.last_error && <p className="error">Last rotation failed: {playlist.last_error}</p>}

      <div className="tabs">
        <button className={tab === "songs" ? "active" : ""} onClick={() => setTab("songs")}>Songs</button>
        <button className={tab === "rotation" ? "active" : ""} onClick={() => setTab("rotation")}>Rotation</button>
      </div>

      {tab === "songs" && <CatalogView playlistId={id} version={catalogVersion} />}
      {tab === "rotation" && (rotation
        ? <RotationView rotation={rotation} />
        : <p className="muted">Run a dry run to preview the next rotation.</p>)}
    </section>
  );
}
