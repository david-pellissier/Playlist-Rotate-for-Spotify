import { FormEvent, useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { api } from "../api";
import { Checkbox, NumberField } from "../components/Fields";
import Panel from "../components/Panel";
import RuleList from "../components/RuleList";
import ScheduleFields from "../components/ScheduleFields";
import { todayIso } from "../format";
import { useAction, useLoader } from "../hooks";
import type { ArtistSelection, Playlist, PlaylistInput, Rule, Settings } from "../types";

function defaults(settings: Settings): PlaylistInput {
  return {
    name: "",
    spotify_target: "",
    artists: "",
    songs_per_artist: 3,
    max_artists: null,
    artist_selection: "fair",
    max_new_releases: 1,
    update_interval_days: 7,
    first_rotation_date: todayIso(),
    rotation_time: "06:00",
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
  const backTo = id ? `/playlists/${id}` : "/";

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
        <div className="page-title">
          <Link to={backTo} className="back-link">← {id ? (data[2] as Playlist).name : "Playlists"}</Link>
          <h1>{id ? "Edit playlist" : "New playlist"}</h1>
        </div>
      </div>

      <Panel title="General" description="Which Spotify playlist to fill, and with which artists.">
        <div className="field-grid">
          <label>
            Name
            <input required value={form.name} onChange={(e) => set("name", e.target.value)} />
          </label>
          <label>
            Spotify playlist
            <input required value={form.spotify_target} onChange={(e) => set("spotify_target", e.target.value)} />
            <small>Name, ID or URL. A playlist with this name is created if you don't own one yet.</small>
          </label>
        </div>
        <label>
          Artists
          <textarea rows={12} value={form.artists} onChange={(e) => set("artists", e.target.value)} />
          <small>One per line, with the exact Spotify name. Empty lines and lines starting with # are ignored.</small>
        </label>
      </Panel>

      <ScheduleFields form={form} isNew={!id} onChange={set} />

      <Panel title="Rotation" description="Which artists and how many of their songs go into every rotation." grid>
        <NumberField
          label="Artists per rotation"
          min={1}
          value={form.max_artists}
          onChange={(v) => set("max_artists", v)}
          optional
          placeholder="All artists"
        />
        <label>
          Artist choice
          <select
            value={form.artist_selection}
            disabled={form.max_artists === null}
            onChange={(e) => set("artist_selection", e.target.value as ArtistSelection)}
          >
            <option value="fair">Fair: artists left out longest first</option>
            <option value="random">Random</option>
          </select>
          <small>{form.max_artists === null ? "Used when artists per rotation is limited." : "Ties are broken at random."}</small>
        </label>
        <NumberField label="Songs per artist" min={1} value={form.songs_per_artist} onChange={(v) => set("songs_per_artist", v as number)} />
        <NumberField
          label="Max new releases per artist"
          min={0}
          value={form.max_new_releases}
          onChange={(v) => set("max_new_releases", v as number)}
        />
        <Checkbox label="Shuffle track order" checked={form.shuffle} onChange={(v) => set("shuffle", v)} />
      </Panel>

      <Panel title="Filters" description="Songs that don't pass these filters are never picked." grid>
        <NumberField label="Min duration (seconds)" min={0} value={form.min_duration} onChange={(v) => set("min_duration", v as number)} />
        <NumberField
          label="Max duration (seconds)"
          min={1}
          value={form.max_duration}
          onChange={(v) => set("max_duration", v)}
          optional
          placeholder="No limit"
        />
        <Checkbox label="Exclude songs with featured artists" checked={form.solo_only} onChange={(v) => set("solo_only", v)} />
        <Checkbox label="Exclude duplicates" checked={form.exclude_duplicates} onChange={(v) => set("exclude_duplicates", v)} />
      </Panel>

      <Panel title="Global rules" description="Click a rule to turn it off for this playlist. Manage the list in Settings.">
        <div className="chips">
          {globalRules.map((rule) => {
            const enabled = !form.disabled_rule_ids.includes(rule.id);
            return (
              <label key={rule.id} className={enabled ? "chip on" : "chip"}>
                <input type="checkbox" checked={enabled} onChange={(e) => toggleRule(rule.id, e.target.checked)} />
                {rule.kind === "regex" && <span className="chip-kind">regex</span>}
                {rule.pattern}
              </label>
            );
          })}
          {globalRules.length === 0 && <span className="muted">No global rules.</span>}
        </div>
      </Panel>

      <Panel title="Playlist rules" description="Extra keywords or regexes that only apply to this playlist. Saved immediately.">
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
      </Panel>

      <div className="form-footer">
        {save.error && <span className="error">{save.error}</span>}
        <Link className="button" to={backTo}>Cancel</Link>
        <button className="primary" disabled={save.busy}>{id ? "Save changes" : "Create playlist"}</button>
      </div>
    </form>
  );
}
