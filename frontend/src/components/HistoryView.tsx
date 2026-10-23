import { useState } from "react";
import { api } from "../api";
import { formatDate, formatDuration } from "../format";
import { useAction, useLoader } from "../hooks";
import type { RotationSummary } from "../types";

export default function HistoryView({ playlistId, version }: { playlistId: number; version: number }) {
  const [page, setPage] = useState(1);
  const [openId, setOpenId] = useState<number>();
  const { data: history, error, reload } = useLoader(() => api.history(playlistId, page), [playlistId, page, version]);
  const clear = useAction();

  async function clearHistory() {
    if (!confirm("Delete the whole rotation history of this playlist? Cooldowns and play counts are kept.")) return;
    await clear.run(() => api.clearHistory(playlistId));
    setPage(1);
    setOpenId(undefined);
    reload();
  }

  if (error) return <p className="error">{error}</p>;
  if (!history) return <p className="muted">Loading…</p>;
  if (history.total === 0) {
    return (
      <div className="empty-state">
        <h2>No rotations yet</h2>
        <p>Every rotation, scheduled or manual, will be listed here with the songs it put in the playlist.</p>
      </div>
    );
  }

  const pages = Math.ceil(history.total / history.page_size);
  return (
    <div className="stack">
      <div className="pager">
        <span className="muted">{history.total} {history.total === 1 ? "rotation" : "rotations"}</span>
        <button className="small danger" disabled={clear.busy} onClick={clearHistory}>Clear history</button>
      </div>
      {clear.error && <p className="error">{clear.error}</p>}
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Date</th>
              <th className="hide-sm">Trigger</th>
              <th>Result</th>
              <th className="numeric hide-sm">Songs</th>
              <th className="numeric hide-sm">New releases</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {history.rotations.map((rotation) => (
              <HistoryRow
                key={rotation.id}
                playlistId={playlistId}
                rotation={rotation}
                open={openId === rotation.id}
                onToggle={() => setOpenId(openId === rotation.id ? undefined : rotation.id)}
              />
            ))}
          </tbody>
        </table>
      </div>
      {pages > 1 && (
        <div className="pager">
          <span />
          <div className="row">
            <button className="small" disabled={history.page <= 1} onClick={() => setPage(history.page - 1)}>Newer</button>
            <span className="muted">Page {history.page} of {pages}</span>
            <button className="small" disabled={history.page >= pages} onClick={() => setPage(history.page + 1)}>Older</button>
          </div>
        </div>
      )}
    </div>
  );
}

function HistoryRow({ playlistId, rotation, open, onToggle }: {
  playlistId: number;
  rotation: RotationSummary;
  open: boolean;
  onToggle: () => void;
}) {
  const trigger = rotation.trigger === "scheduled" ? "Scheduled" : "Manual";
  return (
    <>
      <tr>
        <td className="nowrap">
          {formatDate(rotation.rotated_at)}
          <small className="show-sm">
            {trigger}
            {!rotation.error && ` · ${rotation.track_count} songs`}
          </small>
        </td>
        <td className="hide-sm"><span className="badge">{trigger}</span></td>
        <td>
          {rotation.error
            ? <span className="badge danger" title={rotation.error}>Failed</span>
            : <span className="badge success">Updated</span>}
        </td>
        <td className="numeric hide-sm">{rotation.error ? "—" : rotation.track_count}</td>
        <td className="numeric hide-sm">{rotation.error ? "—" : rotation.new_releases}</td>
        <td className="cell-actions">
          {rotation.error
            ? null
            : <button className="small ghost" onClick={onToggle}>{open ? "Hide songs" : "Show songs"}</button>}
        </td>
      </tr>
      {rotation.error && (
        <tr className="history-detail">
          <td colSpan={6}><span className="error">{rotation.error}</span></td>
        </tr>
      )}
      {open && (
        <tr className="history-detail">
          <td colSpan={6}><RotationTracks playlistId={playlistId} rotationId={rotation.id} /></td>
        </tr>
      )}
    </>
  );
}

function RotationTracks({ playlistId, rotationId }: { playlistId: number; rotationId: number }) {
  const { data: tracks, error } = useLoader(() => api.rotationTracks(playlistId, rotationId), [playlistId, rotationId]);
  if (error) return <p className="error">{error}</p>;
  if (!tracks) return <p className="muted">Loading…</p>;
  return (
    <ol className="history-tracks">
      {tracks.map((track) => (
        <li key={track.position}>
          <span className="track-name">{track.name}</span>
          <small>{track.artist_name} · {track.album_name} · {formatDuration(track.duration)}</small>
          {track.source === "new" && <span className="badge info">New release</span>}
          {track.source === "cooldown" && <span className="badge warning">From cooldown</span>}
        </li>
      ))}
    </ol>
  );
}
