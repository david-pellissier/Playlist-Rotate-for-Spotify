import { formatDuration } from "../format";
import type { Rotation } from "../types";

const SOURCE_LABELS = { new: "new release", random: "random", cooldown: "from cooldown" };

export default function RotationView({ rotation }: { rotation: Rotation }) {
  return (
    <div className="stack">
      <p className={rotation.dry_run ? "notice" : "success"}>
        {rotation.dry_run ? "Dry run: nothing was changed." : "The playlist was updated."} {rotation.order.length} tracks.
      </p>
      {rotation.missing_artists.length > 0 && (
        <p className="error">No exact Spotify match for: {rotation.missing_artists.join(", ")}</p>
      )}
      <div className="cards">
        {rotation.selections.map((selection) => (
          <article key={selection.artist_name} className="card">
            <h3>{selection.artist_name}</h3>
            <p className="muted">{selection.eligible} eligible · cooldown {selection.cooldown} rotations</p>
            <ul className="plain">
              {selection.picks.map((pick) => (
                <li key={pick.track_id}>
                  {pick.name} <span className="muted">— {pick.album_name}</span>
                  {pick.source !== "random" && <span className={`badge ${pick.source}`}>{SOURCE_LABELS[pick.source]}</span>}
                </li>
              ))}
              {selection.picks.length === 0 && <li className="error">No eligible songs</li>}
            </ul>
          </article>
        ))}
      </div>
      <h2>Playlist order</h2>
      <table>
        <tbody>
          {rotation.order.map((pick, index) => (
            <tr key={pick.track_id}>
              <td className="muted">{index + 1}</td>
              <td>{pick.name}</td>
              <td>{pick.artist_name}</td>
              <td className="muted">{pick.album_name}</td>
              <td className="muted">{formatDuration(pick.duration)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
