import { formatDay, formatSchedule, todayIso } from "../format";
import type { PlaylistInput } from "../types";
import { NumberField } from "./Fields";
import Panel from "./Panel";

export default function ScheduleFields({ form, isNew, onChange }: {
  form: PlaylistInput;
  isNew: boolean;
  onChange: <K extends keyof PlaylistInput>(key: K, value: PlaylistInput[K]) => void;
}) {
  return (
    <Panel title="Schedule" description="When the playlist rotates on its own.">
      <div className="segmented" role="radiogroup" aria-label="Schedule">
        <label className={form.enabled ? "selected" : ""}>
          <input type="radio" name="schedule" checked={form.enabled} onChange={() => onChange("enabled", true)} />
          <strong>Active</strong>
          <small>Rotates automatically on the schedule below</small>
        </label>
        <label className={form.enabled ? "" : "selected paused"}>
          <input type="radio" name="schedule" checked={!form.enabled} onChange={() => onChange("enabled", false)} />
          <strong>Paused</strong>
          <small>Rotates only when you click "Rotate now"</small>
        </label>
      </div>
      <div className="field-grid">
        <label>
          First rotation
          <input
            type="date"
            required
            min={isNew ? todayIso() : undefined}
            value={form.first_rotation_date}
            onChange={(e) => onChange("first_rotation_date", e.target.value)}
          />
        </label>
        <label>
          Rotation time
          <input type="time" required value={form.rotation_time} onChange={(e) => onChange("rotation_time", e.target.value)} />
        </label>
        <NumberField
          label="Repeat every (days)"
          min={1}
          value={form.update_interval_days}
          onChange={(v) => onChange("update_interval_days", v as number)}
        />
      </div>
      {form.first_rotation_date && form.update_interval_days > 0 && (
        <p className={form.enabled ? "muted" : "notice"}>
          {!form.enabled && <strong>Paused: this schedule is kept but not used. </strong>}
          First rotation on {formatDay(form.first_rotation_date)} at {form.rotation_time}, then{" "}
          {formatSchedule(form.update_interval_days, form.rotation_time).toLowerCase()}. Rotating by hand doesn't move
          this schedule.
        </p>
      )}
    </Panel>
  );
}
