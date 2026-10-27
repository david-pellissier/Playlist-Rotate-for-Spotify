import { type CSSProperties, useEffect, useState } from "react";
import { api } from "../api";
import { formatDuration, nameHue } from "../format";
import InfoTip from "./InfoTip";
import MultiSelect, { toggled } from "./MultiSelect";
import { useAction, useDebounced, useLoader } from "../hooks";
import type { Catalog, CatalogAlbum, CatalogTrack, ReleaseType, SongStatus } from "../types";

const STATUSES: Record<SongStatus, string> = {
  available: "Available",
  new: "New release",
  cooldown: "On cooldown",
  current: "In playlist",
  excluded: "Excluded",
};

const RELEASE_TYPES: Record<ReleaseType, string> = {
  album: "Albums",
  single: "Singles & EPs",
};

export default function CatalogView({ playlistId, albumsOnly, version }: {
  playlistId: number;
  albumsOnly: boolean;
  version: number;
}) {
  const defaultHiddenTypes = albumsOnly ? "single" : "";
  const [hiddenArtists, setHiddenArtists] = useState<Set<string>>(new Set());
  const [hiddenStatuses, setHiddenStatuses] = useState<Set<string>>(new Set());
  const [hiddenTypes, setHiddenTypes] = useState<Set<string>>(new Set(defaultHiddenTypes ? [defaultHiddenTypes] : []));
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);
  const q = useDebounced(search);
  const [artistIds, setArtistIds] = useState<string[]>([]);
  const shownArtists = artistIds.filter((id) => !hiddenArtists.has(id));
  const artistParams: Record<string, string[]> = hiddenArtists.size <= shownArtists.length || !shownArtists.length
    ? { hide_artist: [...hiddenArtists] }
    : { artist: shownArtists };
  const { data: catalog, error, reload } = useLoader(
    () => api.catalog(playlistId, {
      q,
      page,
      params: { ...artistParams, hide_status: [...hiddenStatuses], hide_type: [...hiddenTypes] },
    }),
    [playlistId, hiddenArtists, hiddenStatuses, hiddenTypes, q, page, version],
  );
  const action = useAction();

  useEffect(() => {
    if (catalog) setArtistIds(catalog.artists.map((artist) => artist.id));
  }, [catalog]);

  const filterKey = [...hiddenArtists, "|", ...hiddenStatuses, "|", ...hiddenTypes, "|", q.trim()].join(",");
  const filtering = hiddenArtists.size > 0 || hiddenStatuses.size > 0 || q.trim() !== ""
    || [...hiddenTypes].join() !== defaultHiddenTypes;
  const [allOpen, setAllOpen] = useState(false);
  const [toggledOpen, setToggledOpen] = useState<Map<string, boolean>>(new Map());
  const isOpen = (key: string) => toggledOpen.get(key) ?? allOpen;

  useEffect(() => {
    setAllOpen(filtering);
    setToggledOpen(new Map());
  }, [filtering, filterKey]);

  function toggle(key: string) {
    setToggledOpen((current) => new Map(current).set(key, !isOpen(key)));
  }

  function toggleAll() {
    setAllOpen(!allOpen);
    setToggledOpen(new Map());
  }

  function filter(apply: () => void) {
    apply();
    setPage(1);
  }

  function goTo(target: number) {
    setPage(target);
    scrollTo(0, 0);
  }

  async function toggleAlbum(album: CatalogAlbum) {
    await action.run(() => api.setAlbumEnabled(playlistId, album.id, album.exclusion !== null));
    reload();
  }

  async function toggleTrack(track: CatalogTrack) {
    await action.run(() => api.setTrackEnabled(playlistId, track.id, track.exclusion !== null));
    reload();
  }

  return (
    <div className="stack">
      <div className="toolbar">
        <MultiSelect
          noun="artists"
          options={catalog?.artists.map((artist) => ({
            value: artist.id,
            label: artist.name,
            hint: `${artist.eligible}/${artist.total}`,
          })) ?? []}
          hidden={hiddenArtists}
          onChange={(next) => filter(() => setHiddenArtists(next))}
        />
        <input
          type="search"
          aria-label="Search"
          placeholder="Search songs or albums"
          value={search}
          onChange={(e) => filter(() => setSearch(e.target.value))}
        />
        <button disabled={!catalog?.albums.length} onClick={toggleAll}>{allOpen ? "Collapse all" : "Expand all"}</button>
      </div>
      <div className="filter-row">
        <ChipFilter
          label="Status"
          options={STATUSES}
          counts={catalog?.status_counts ?? {}}
          hidden={hiddenStatuses}
          onChange={(next) => filter(() => setHiddenStatuses(next))}
        />
        <ChipFilter
          label="Release"
          options={RELEASE_TYPES}
          counts={catalog?.type_counts ?? {}}
          hidden={hiddenTypes}
          onChange={(next) => filter(() => setHiddenTypes(next))}
        />
      </div>

      {(error || action.error) && <p className="error">{error ?? action.error}</p>}
      {!!catalog?.missing_artists.length && (
        <p className="notice">
          <strong>Not found:</strong> {catalog.missing_artists.join(", ")}
          <InfoTip text="Refresh the catalog, or check that the names exactly match Spotify." />
        </p>
      )}
      {catalog && catalog.total_tracks > 0 && <Pager catalog={catalog} onPage={goTo} />}
      {catalog?.total_tracks === 0 && <div className="empty-state">No songs match these filters.</div>}

      {groupByArtist(catalog?.albums ?? []).map(([artistName, albums]) => {
        const artist = catalog?.artists.find((a) => a.name === artistName);
        const songs = albums.reduce((count, album) => count + album.tracks.length, 0);
        const open = isOpen(`artist:${artistName}`);
        return (
          <section key={artistName} className={open ? "artist-section" : "artist-section collapsed"}>
            <header
              className="artist-header"
              style={artist?.image_url ? ({ "--artist-image": `url("${artist.image_url}")` } as CSSProperties) : undefined}
            >
              <Toggle open={open} label={artistName} onClick={() => toggle(`artist:${artistName}`)} />
              <ArtistAvatar name={artistName} image={artist?.image_url ?? null} />
              <div className="artist-title">
                <h2>{artistName}</h2>
                <small>
                  {filtering && `${songs} matching · `}
                  {artist && `${artist.eligible}/${artist.total} eligible · ${artist.on_cooldown} on cooldown`}
                </small>
              </div>
            </header>
            {open && albums.map((album) => (
              <AlbumCard
                key={album.id}
                album={album}
                open={isOpen(`album:${album.id}`)}
                busy={action.busy}
                onToggleOpen={() => toggle(`album:${album.id}`)}
                onToggleAlbum={() => toggleAlbum(album)}
                onToggleTrack={toggleTrack}
              />
            ))}
          </section>
        );
      })}

      {catalog && catalog.total_artists > catalog.page_size && <Pager catalog={catalog} onPage={goTo} />}
    </div>
  );
}

function ChipFilter<T extends string>({ label, options, counts, hidden, onChange }: {
  label: string;
  options: Record<T, string>;
  counts: Partial<Record<T, number>>;
  hidden: Set<string>;
  onChange: (hidden: Set<string>) => void;
}) {
  return (
    <div className="chips" role="group" aria-label={label}>
      {(Object.entries(options) as [T, string][]).map(([value, name]) => {
        const on = !hidden.has(value);
        return (
          <label key={value} className={on ? "chip on" : "chip"}>
            <input type="checkbox" checked={on} onChange={() => onChange(toggled(hidden, value))} />
            {name}
            <span className="chip-count">{counts[value] ?? 0}</span>
          </label>
        );
      })}
    </div>
  );
}

function groupByArtist(albums: CatalogAlbum[]): [string, CatalogAlbum[]][] {
  const groups = new Map<string, CatalogAlbum[]>();
  for (const album of albums) groups.set(album.artist_name, [...(groups.get(album.artist_name) ?? []), album]);
  return [...groups];
}

function ArtistAvatar({ name, image }: { name: string; image: string | null }) {
  if (image) return <img className="artist-avatar" src={image} alt="" loading="lazy" />;
  const initials = name.split(/\s+/).filter(Boolean).slice(0, 2).map((word) => word[0]).join("").toUpperCase();
  return (
    <span className="artist-avatar initials" style={{ "--avatar-hue": nameHue(name) } as CSSProperties} aria-hidden="true">
      {initials}
    </span>
  );
}

function Toggle({ open, label, onClick }: { open: boolean; label: string; onClick: () => void }) {
  return (
    <button
      className={open ? "toggle open" : "toggle"}
      aria-expanded={open}
      aria-label={`${open ? "Collapse" : "Expand"} ${label}`}
      title={open ? "Collapse" : "Expand"}
      onClick={onClick}
    >
      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round">
        <path d="m9 6 6 6-6 6" />
      </svg>
    </button>
  );
}

function AlbumCard({ album, open, busy, onToggleOpen, onToggleAlbum, onToggleTrack }: {
  album: CatalogAlbum;
  open: boolean;
  busy: boolean;
  onToggleOpen: () => void;
  onToggleAlbum: () => void;
  onToggleTrack: (track: CatalogTrack) => void;
}) {
  const eligible = album.tracks.filter((track) => !track.exclusion).length;
  return (
    <article className={album.exclusion ? "album disabled" : "album"}>
      <header className={open ? "album-header" : "album-header collapsed"}>
        <Toggle open={open} label={album.name} onClick={onToggleOpen} />
        {album.image_url
          ? <img className="album-cover" src={album.image_url} alt="" loading="lazy" />
          : <span className="album-cover" />}
        <div className="album-info">
          <h3 title={album.name}>{album.name}</h3>
          <small>
            {album.album_type} · {album.release_date} · {album.tracks.length} {album.tracks.length === 1 ? "song" : "songs"},{" "}
            {eligible} eligible
          </small>
        </div>
        <AlbumStatus album={album} />
        <button className="small" disabled={busy} onClick={onToggleAlbum}>
          {album.exclusion ? "Enable album" : "Disable album"}
        </button>
      </header>
      {open && (
        <div className="table-scroll">
          <table>
            <tbody>
              {album.tracks.map((track) => (
                <tr key={track.id} className={track.exclusion ? "excluded" : undefined}>
                  <td className="track-name">{track.name}</td>
                  <td className="numeric muted">{formatDuration(track.duration)}</td>
                  <td className="numeric muted" title="Times played">{track.play_count}×</td>
                  <td><TrackStatus track={track} /></td>
                  <td className="cell-actions">
                    {track.excluded_by !== "album" && (
                      <button className="small ghost" disabled={busy} onClick={() => onToggleTrack(track)}>
                        {track.exclusion ? "Enable" : "Disable"}
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </article>
  );
}

function Pager({ catalog, onPage }: { catalog: Catalog; onPage: (page: number) => void }) {
  const pages = Math.max(1, Math.ceil(catalog.total_artists / catalog.page_size));
  const first = (catalog.page - 1) * catalog.page_size + 1;
  const last = Math.min(catalog.page * catalog.page_size, catalog.total_artists);
  return (
    <div className="pager">
      <span className="muted">
        {catalog.total_artists > catalog.page_size
          ? `Artists ${first}–${last} of ${catalog.total_artists}`
          : `${catalog.total_artists} ${catalog.total_artists === 1 ? "artist" : "artists"}`}
        {` · ${catalog.total_tracks} ${catalog.total_tracks === 1 ? "song" : "songs"}`}
      </span>
      {pages > 1 && (
        <div className="row">
          <button className="small" disabled={catalog.page <= 1} onClick={() => onPage(catalog.page - 1)}>Previous</button>
          <span className="muted">Page {catalog.page} of {pages}</span>
          <button className="small" disabled={catalog.page >= pages} onClick={() => onPage(catalog.page + 1)}>Next</button>
        </div>
      )}
    </div>
  );
}

function AlbumStatus({ album }: { album: CatalogAlbum }) {
  if (album.excluded_by === "auto") return <span className="badge warning">Excluded: {album.exclusion}</span>;
  if (album.excluded_by === "user") return <span className="badge warning">Album disabled</span>;
  if (album.forced) return <span className="badge info">Enabled manually</span>;
  return null;
}

function TrackStatus({ track }: { track: CatalogTrack }) {
  if (track.exclusion) return <span className="badge">{track.exclusion}</span>;
  return (
    <span className="badges">
      {track.forced && <span className="badge info">Enabled manually</span>}
      {track.new_release && <span className="badge info">New release</span>}
      {track.current && <span className="badge accent">In playlist</span>}
      {track.cooldown > 0 && <span className="badge warning">Cooldown {track.cooldown}</span>}
      {!track.current && track.cooldown === 0 && <span className="badge success">Available</span>}
    </span>
  );
}
