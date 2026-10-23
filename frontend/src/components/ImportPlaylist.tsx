import { ChangeEvent, useRef, useState } from "react";
import { ApiError, api } from "../api";
import { useAction } from "../hooks";
import type { ImportConflict, Playlist } from "../types";

interface Conflict {
  data: unknown;
  message: string;
}

const EXPORT_FORMAT = "spotify-playlist-rotate";

function readExport(text: string, fileName: string): unknown {
  let data: { format?: unknown };
  try {
    data = JSON.parse(text);
  } catch {
    throw new Error(`${fileName} is not a valid JSON file`);
  }
  if (data?.format !== EXPORT_FORMAT) throw new Error(`${fileName} is not a playlist export`);
  return data;
}

export default function ImportPlaylist({ onImported }: { onImported: (playlist: Playlist) => void }) {
  const fileInput = useRef<HTMLInputElement>(null);
  const [conflict, setConflict] = useState<Conflict>();
  const action = useAction();

  async function attempt(data: unknown, onConflict: ImportConflict): Promise<Playlist | undefined> {
    try {
      return await api.importPlaylist(data, onConflict);
    } catch (failure) {
      if (!(failure instanceof ApiError && failure.status === 409)) throw failure;
      setConflict({ data, message: failure.message });
    }
  }

  async function run(importing: () => Promise<Playlist | undefined>) {
    setConflict(undefined);
    const playlist = await action.run(importing);
    if (playlist) onImported(playlist);
  }

  async function readFile(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    event.target.value = "";
    if (file) await run(async () => attempt(readExport(await file.text(), file.name), "fail"));
  }

  return (
    <>
      <input ref={fileInput} type="file" accept=".json,application/json" hidden onChange={readFile} />
      <button disabled={action.busy} onClick={() => fileInput.current?.click()}>Import</button>
      {action.error && <p className="error">{action.error}</p>}
      {conflict && (
        <div className="modal-backdrop">
          <div className="modal" role="dialog" aria-modal="true" aria-labelledby="import-conflict-title">
            <h2 id="import-conflict-title">Playlist already exists</h2>
            <p>{conflict.message}. What do you want to do?</p>
            <ul className="plain">
              <li><strong>Erase:</strong> replace its configuration with the imported one. Its song history is kept.</li>
              <li><strong>Make a copy:</strong> import it under a new name, paused so it doesn't rotate the same Spotify playlist.</li>
            </ul>
            <div className="actions">
              <button onClick={() => setConflict(undefined)}>Cancel</button>
              <button onClick={() => run(() => attempt(conflict.data, "copy"))}>Make a copy</button>
              <button className="danger" onClick={() => run(() => attempt(conflict.data, "replace"))}>Erase</button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
