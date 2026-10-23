import { FormEvent, useEffect, useState } from "react";
import { api } from "../api";
import { Checkbox, NumberField } from "../components/Fields";
import RuleList from "../components/RuleList";
import { useAction, useLoader } from "../hooks";
import type { Settings } from "../types";

export default function SettingsPage() {
  const { data, error, setData } = useLoader(() => Promise.all([api.settings(), api.rules(), api.auth()]), []);
  const [form, setForm] = useState<Settings>();
  const save = useAction();
  const [saved, setSaved] = useState(false);

  useEffect(() => setForm(data?.[0]), [data?.[0]]);

  if (error) return <p className="error">{error}</p>;
  if (!data || !form) return <p className="muted">Loading…</p>;
  const [, rules, auth] = data;

  function set<K extends keyof Settings>(key: K, value: Settings[K]) {
    setSaved(false);
    setForm((current) => current && { ...current, [key]: value });
  }

  async function submit(event: FormEvent) {
    event.preventDefault();
    setSaved(!!(await save.run(() => api.saveSettings(form!))));
  }

  return (
    <section className="stack">
      <h1>Settings</h1>

      <fieldset>
        <legend>Spotify</legend>
        {auth.configured ? (
          <p className="success">Credentials are configured.</p>
        ) : auth.authorize_url ? (
          <p>
            No refresh token yet. <a href={auth.authorize_url}>Authorize with Spotify</a> and copy the token shown
            into your <code>.env</code> file, then restart.
          </p>
        ) : (
          <p className="error">Set SPOTIFY_CLIENT_ID and SPOTIFY_CLIENT_SECRET in your <code>.env</code> file.</p>
        )}
      </fieldset>

      <form className="stack" onSubmit={submit}>
        <fieldset className="grid">
          <legend>Defaults</legend>
          <NumberField label="Minimum cooldown (rotations)" min={0} value={form.min_cooldown} onChange={(v) => set("min_cooldown", v as number)} />
          <NumberField
            label="Catalog refresh lookback (days)"
            min={0}
            value={form.refresh_lookback_days}
            onChange={(v) => set("refresh_lookback_days", v as number)}
          />
          <NumberField label="Min duration (s)" min={0} value={form.min_duration} onChange={(v) => set("min_duration", v as number)} />
          <NumberField
            label="Max duration (s, empty = none)"
            min={1}
            optional
            value={form.max_duration}
            onChange={(v) => set("max_duration", v)}
          />
          <Checkbox label="Exclude songs with featured artists" checked={form.solo_only} onChange={(v) => set("solo_only", v)} />
          <Checkbox label="Exclude duplicates" checked={form.exclude_duplicates} onChange={(v) => set("exclude_duplicates", v)} />
          <small>Duration, featuring and duplicate defaults apply to newly created playlists.</small>
        </fieldset>
        <div className="actions">
          {save.error && <span className="error">{save.error}</span>}
          {saved && <span className="success">Saved</span>}
          <button className="primary" disabled={save.busy}>Save defaults</button>
        </div>
      </form>

      <fieldset>
        <legend>Global rules</legend>
        <p className="muted">Applied to the track and album titles of every playlist, unless the playlist disables them.</p>
        <RuleList
          rules={rules}
          onCreate={async (kind, pattern) => {
            const rule = await api.createRule(kind, pattern);
            setData((current) => current && [current[0], [...current[1], rule], current[2]]);
          }}
          onDelete={async (id) => {
            await api.deleteRule(id);
            setData((current) => current && [current[0], current[1].filter((r) => r.id !== id), current[2]]);
          }}
        />
      </fieldset>
    </section>
  );
}
