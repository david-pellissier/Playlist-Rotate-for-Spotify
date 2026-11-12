export default function ScheduleToggle({ enabled, error, busy, compact = false, onToggle }: {
  enabled: boolean;
  error: string | null;
  busy: boolean;
  compact?: boolean;
  onToggle: () => void;
}) {
  const action = enabled ? "Pause the schedule" : "Resume the schedule";
  const state = error ? "failing" : enabled ? "on" : "off";
  const label = error ? "Failing" : enabled ? "Active" : "Paused";
  return (
    <button
      type="button"
      className={compact ? `schedule-toggle ${state} compact` : `schedule-toggle ${state}`}
      aria-pressed={enabled}
      aria-label={compact ? `${label}. ${action}` : undefined}
      title={error ? `${error} · ${action}` : action}
      disabled={busy}
      onClick={onToggle}
    >
      <span className="schedule-toggle-icon" aria-hidden="true">
        <svg width="12" height="12" viewBox="0 0 12 12" fill="currentColor">
          {enabled
            ? <><rect x="1.5" y="1" width="3.2" height="10" rx="1" /><rect x="7.3" y="1" width="3.2" height="10" rx="1" /></>
            : <path d="M3 1.3v9.4a.6.6 0 0 0 .92.5l7.3-4.7a.6.6 0 0 0 0-1L3.92.8A.6.6 0 0 0 3 1.3Z" />}
        </svg>
      </span>
      {!compact && label}
    </button>
  );
}
