import { FormEvent, useEffect, useState } from "react";
import { api } from "../api";
import { Checkbox, NumberField } from "../components/Fields";
import Panel from "../components/Panel";
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
      <div className="page-header">
        <div className="page-title">
          <h1>Settings</h1>
          <p className="muted">Spotify connection, defaults and rules shared by all playlists.</p>
        </div>
      </div>

      <Panel title="Spotify">
        {auth.configured ? (
          <div className="row">
            <span className="badge success dot">Connected</span>
            <span className="muted">Credentials are set in the environment.</span>
          </div>
        ) : auth.authorize_url ? (
          <div className="banner">
            <span>
              <span className="badge warning dot">Not connected</span>{" "}
              Authorize once, then copy the token shown into your <code>.env</code> file and restart the daemon.
            </span>
            <a className="button primary" href={auth.authorize_url}>Authorize with Spotify</a>
          </div>
        ) : (
          <p className="error">Set SPOTIFY_CLIENT_ID and SPOTIFY_CLIENT_SECRET in your <code>.env</code> file.</p>
        )}
      </Panel>

      <form onSubmit={submit}>
        <Panel title="Defaults" description="Duration, featuring and duplicate settings are copied into new playlists.">
          <div className="field-grid">
            <NumberField label="Minimum cooldown (rotations)" min={0} value={form.min_cooldown} onChange={(v) => set("min_cooldown", v as number)} />
            <NumberField
              label="Catalog refresh lookback (days)"
              min={0}
              value={form.refresh_lookback_days}
              onChange={(v) => set("refresh_lookback_days", v as number)}
            />
            <NumberField label="Min duration (seconds)" min={0} value={form.min_duration} onChange={(v) => set("min_duration", v as number)} />
            <NumberField
              label="Max duration (seconds)"
              min={1}
              optional
              placeholder="No limit"
              value={form.max_duration}
              onChange={(v) => set("max_duration", v)}
            />
            <Checkbox label="Exclude songs with featured artists" checked={form.solo_only} onChange={(v) => set("solo_only", v)} />
            <Checkbox label="Exclude duplicates" checked={form.exclude_duplicates} onChange={(v) => set("exclude_duplicates", v)} />
          </div>
          <div className="actions">
            {save.error && <span className="error">{save.error}</span>}
            {saved && <span className="success">Saved</span>}
            <button className="primary" disabled={save.busy}>Save defaults</button>
          </div>
        </Panel>
      </form>

      <Panel title="Global rules" description="Matched against song and album titles in every playlist, unless a playlist turns them off.">
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
      </Panel>
    </section>
  );
}
