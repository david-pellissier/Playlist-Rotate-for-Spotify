import { formatDuration } from "../format";
import type { Rotation } from "../types";

const SOURCE_BADGES = {
  new: <span className="badge info">New release</span>,
  random: null,
  cooldown: <span className="badge warning">From cooldown</span>,
};

export default function RotationView({ rotation }: { rotation: Rotation }) {
  return (
    <div className="stack">
      <p className={rotation.dry_run ? "notice" : "success"}>
        {rotation.dry_run
          ? <><strong>Dry run:</strong> nothing was changed. The next rotation would pick these {rotation.order.length} songs.</>
          : <><strong>Playlist updated</strong> with {rotation.order.length} songs.</>}
      </p>
      {rotation.skipped_artists.length > 0 && (
        <p className="muted">
          <strong>Sitting out this rotation:</strong> {rotation.skipped_artists.join(", ")}
        </p>
      )}
      {rotation.missing_artists.length > 0 && (
        <p className="error"><strong>No exact Spotify match for:</strong> {rotation.missing_artists.join(", ")}</p>
      )}
      <div className="cards">
        {rotation.selections.map((selection) => (
          <article key={selection.artist_name} className="card">
            <div>
              <h3>{selection.artist_name}</h3>
              <small>{selection.eligible} eligible songs · picked songs sit out {selection.cooldown} rotations</small>
            </div>
            <ul className="plain">
              {selection.picks.map((pick) => (
                <li key={pick.track_id} className="pick">
                  <span className="row">{pick.name}{SOURCE_BADGES[pick.source]}</span>
                  <small>{pick.album_name}</small>
                </li>
              ))}
              {selection.picks.length === 0 && <li className="error">No eligible songs</li>}
            </ul>
          </article>
        ))}
      </div>
      <h2>Playlist order</h2>
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th className="numeric">#</th>
              <th>Song</th>
              <th>Artist</th>
              <th>Album</th>
              <th className="numeric">Length</th>
            </tr>
          </thead>
          <tbody>
            {rotation.order.map((pick, index) => (
              <tr key={pick.track_id}>
                <td className="numeric muted">{index + 1}</td>
                <td>{pick.name}</td>
                <td>{pick.artist_name}</td>
                <td className="muted">{pick.album_name}</td>
                <td className="numeric muted">{formatDuration(pick.duration)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
