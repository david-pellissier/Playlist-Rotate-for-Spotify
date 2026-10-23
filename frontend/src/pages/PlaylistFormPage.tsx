import { FormEvent, useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { api } from "../api";
import { Checkbox, NumberField } from "../components/Fields";
import RuleList from "../components/RuleList";
import { useAction, useLoader } from "../hooks";
import type { Playlist, PlaylistInput, Rule, Settings } from "../types";

function defaults(settings: Settings): PlaylistInput {
  return {
    name: "",
    spotify_target: "",
    artists: "",
    songs_per_artist: 3,
    max_new_releases: 1,
    update_interval_days: 7,
    shuffle: true,
    enabled: true,
    min_duration: settings.min_duration,
    max_duration: settings.max_duration,
    solo_only: settings.solo_only,
    exclude_duplicates: settings.exclude_duplicates,
    disabled_rule_ids: [],
  };
}

export default function PlaylistFormPage() {
  const params = useParams();
  const id = params.id ? Number(params.id) : undefined;
  const navigate = useNavigate();
  const { data, error } = useLoader(
    () => Promise.all([api.settings(), api.rules(), id ? api.playlist(id) : Promise.resolve(undefined)]),
    [id],
  );
  const [form, setForm] = useState<PlaylistInput>();
  const [playlistRules, setPlaylistRules] = useState<Rule[]>([]);
  const save = useAction();

  useEffect(() => {
    if (!data) return;
    const [settings, , playlist] = data;
    setForm(playlist ?? defaults(settings));
    setPlaylistRules(playlist?.rules ?? []);
  }, [data]);

  if (error) return <p className="error">{error}</p>;
  if (!form || !data) return <p className="muted">Loading…</p>;
  const globalRules = data[1];

  function set<K extends keyof PlaylistInput>(key: K, value: PlaylistInput[K]) {
    setForm((current) => current && { ...current, [key]: value });
  }

  function toggleRule(ruleId: number, enabled: boolean) {
    const disabled = new Set(form!.disabled_rule_ids);
    if (enabled) disabled.delete(ruleId);
    else disabled.add(ruleId);
    set("disabled_rule_ids", [...disabled]);
  }

  async function submit(event: FormEvent) {
    event.preventDefault();
    const saved = await save.run(() => (id ? api.updatePlaylist(id, form!) : api.createPlaylist(form!)));
    if (saved) navigate(`/playlists/${saved.id}`);
  }

  return (
    <form className="stack" onSubmit={submit}>
      <div className="page-header">
        <h1>{id ? `Edit ${(data[2] as Playlist).name}` : "New playlist"}</h1>
        <div className="actions">
          <button type="button" onClick={() => navigate(-1)}>Cancel</button>
          <button className="primary" disabled={save.busy}>Save</button>
        </div>
      </div>
      {save.error && <p className="error">{save.error}</p>}

      <fieldset>
        <legend>General</legend>
        <label>
          Name
          <input required value={form.name} onChange={(e) => set("name", e.target.value)} />
        </label>
        <label>
          Spotify playlist (name, ID or URL)
          <input required value={form.spotify_target} onChange={(e) => set("spotify_target", e.target.value)} />
          <small>A playlist with this name is created if none exists.</small>
        </label>
        <label>
          Artists (one per line, exact Spotify name)
          <textarea rows={12} value={form.artists} onChange={(e) => set("artists", e.target.value)} />
          <small>Empty lines and lines starting with # are ignored.</small>
        </label>
      </fieldset>

      <fieldset className="grid">
        <legend>Rotation</legend>
        <NumberField label="Songs per artist" min={1} value={form.songs_per_artist} onChange={(v) => set("songs_per_artist", v as number)} />
        <NumberField label="Max new releases per artist" min={0} value={form.max_new_releases} onChange={(v) => set("max_new_releases", v as number)} />
        <NumberField label="Update interval (days)" min={1} value={form.update_interval_days} onChange={(v) => set("update_interval_days", v as number)} />
        <Checkbox label="Shuffle track order" checked={form.shuffle} onChange={(v) => set("shuffle", v)} />
        <Checkbox label="Scheduled rotation enabled" checked={form.enabled} onChange={(v) => set("enabled", v)} />
      </fieldset>

      <fieldset className="grid">
        <legend>Filters</legend>
        <NumberField label="Min duration (s)" min={0} value={form.min_duration} onChange={(v) => set("min_duration", v as number)} />
        <NumberField
          label="Max duration (s, empty = none)"
          min={1}
          value={form.max_duration}
          onChange={(v) => set("max_duration", v)}
          optional
        />
        <Checkbox label="Exclude songs with featured artists" checked={form.solo_only} onChange={(v) => set("solo_only", v)} />
        <Checkbox label="Exclude duplicates" checked={form.exclude_duplicates} onChange={(v) => set("exclude_duplicates", v)} />
      </fieldset>

      <fieldset>
        <legend>Global rules</legend>
        <div className="chips">
          {globalRules.map((rule) => (
            <label key={rule.id} className="chip">
              <input
                type="checkbox"
                checked={!form.disabled_rule_ids.includes(rule.id)}
                onChange={(e) => toggleRule(rule.id, e.target.checked)}
              />
              <span className="muted">{rule.kind === "regex" ? "regex" : ""}</span> {rule.pattern}
            </label>
          ))}
        </div>
      </fieldset>

      <fieldset>
        <legend>Playlist rules</legend>
        {id ? (
          <RuleList
            rules={playlistRules}
            onCreate={async (kind, pattern) => {
              const rule = await api.createPlaylistRule(id, kind, pattern);
              setPlaylistRules((rules) => [...rules, rule]);
            }}
            onDelete={async (ruleId) => {
              await api.deleteRule(ruleId);
              setPlaylistRules((rules) => rules.filter((r) => r.id !== ruleId));
            }}
          />
        ) : (
          <p className="muted">Save the playlist first to add its own rules.</p>
        )}
      </fieldset>
    </form>
  );
}
