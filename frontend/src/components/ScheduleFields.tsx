import { formatDay, todayIso } from "../format";
import type { PlaylistInput } from "../types";
import { NumberField } from "./Fields";

export default function ScheduleFields({ form, isNew, onChange }: {
  form: PlaylistInput;
  isNew: boolean;
  onChange: <K extends keyof PlaylistInput>(key: K, value: PlaylistInput[K]) => void;
}) {
  const every = form.update_interval_days === 1 ? "every day" : `every ${form.update_interval_days} days`;

  return (
    <fieldset>
      <legend>Schedule</legend>
      <div className="segmented" role="radiogroup">
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
      {form.first_rotation_date && (
        <p className={form.enabled ? "muted" : "notice"}>
          {!form.enabled && "Paused: this schedule is kept but not used. "}
          Starting {formatDay(form.first_rotation_date)} at {form.rotation_time}, then {every} at the same time.
          Rotating by hand does not move this schedule.
        </p>
      )}
    </fieldset>
  );
}
