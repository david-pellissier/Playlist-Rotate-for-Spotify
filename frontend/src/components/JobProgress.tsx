import { useEffect, useRef, useState } from "react";
import { api } from "../api";
import type { Progress } from "../types";

const POLL_INTERVAL_MS = 1000;

export function useJobProgress(playlistId: number, requestPending: boolean, onFinished: () => void) {
  const [progress, setProgress] = useState<Progress | null>(null);
  const finished = useRef(onFinished);
  finished.current = onFinished;

  useEffect(() => {
    let active = true;
    let timer: ReturnType<typeof setTimeout>;
    let sawJob = false;

    async function poll() {
      const current = await api.progress(playlistId).catch(() => null);
      if (!active) return;
      setProgress(current);
      if (current) {
        sawJob = true;
      } else if (sawJob && !requestPending) {
        sawJob = false;
        finished.current();
      }
      if (current || requestPending) timer = setTimeout(poll, POLL_INTERVAL_MS);
    }

    poll();
    return () => {
      active = false;
      clearTimeout(timer);
    };
  }, [playlistId, requestPending]);

  return progress;
}

export default function JobProgress({ progress }: { progress: Progress }) {
  const percent = progress.total ? Math.round((progress.done / progress.total) * 100) : undefined;
  return (
    <div className="job-progress">
      <div className="job-progress-label">
        <span>{progress.step}…</span>
        {progress.total > 0 && (
          <span className="muted">
            {progress.done} / {progress.total} · {percent}%
          </span>
        )}
      </div>
      <progress value={progress.total ? progress.done : undefined} max={progress.total || undefined} />
    </div>
  );
}
