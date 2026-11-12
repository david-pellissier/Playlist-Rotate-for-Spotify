import { type CSSProperties, useEffect, useState } from "react";
import { api } from "../api";
import { nameHue } from "../format";
import AlbumCard from "./AlbumCard";
import ChipFilter from "./ChipFilter";
import InfoTip from "./InfoTip";
import MultiSelect from "./MultiSelect";
import Toggle from "./Toggle";
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
  const defaultReleases = albumsOnly ? "album" : "";
  const [hiddenArtists, setHiddenArtists] = useState<Set<string>>(new Set());
  const [statuses, setStatuses] = useState<Set<string>>(new Set());
  const [releases, setReleases] = useState<Set<string>>(new Set(defaultReleases ? [defaultReleases] : []));
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
      params: { ...artistParams, status: [...statuses], release: [...releases] },
    }),
    [playlistId, hiddenArtists, statuses, releases, q, page, version],
  );
  const action = useAction();

  useEffect(() => {
    if (catalog) setArtistIds(catalog.artists.map((artist) => artist.id));
  }, [catalog]);

  const filterKey = [...hiddenArtists, "|", ...statuses, "|", ...releases, "|", q.trim()].join(",");
  const filtering = hiddenArtists.size > 0 || statuses.size > 0 || q.trim() !== ""
    || [...releases].join() !== defaultReleases;
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
          selected={statuses}
          onChange={(next) => filter(() => setStatuses(next))}
        />
        <ChipFilter
          label="Release"
          options={RELEASE_TYPES}
          counts={catalog?.type_counts ?? {}}
          selected={releases}
          onChange={(next) => filter(() => setReleases(next))}
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

      {groupByArtist(catalog?.albums ?? []).map(([artistId, albums]) => {
        const artist = catalog?.artists.find((a) => a.id === artistId);
        const artistName = artist?.name ?? "";
        const songs = albums.reduce((count, album) => count + album.tracks.length, 0);
        const open = isOpen(`artist:${artistId}`);
        return (
          <section key={artistId} className={open ? "artist-section" : "artist-section collapsed"}>
            <header
              className="artist-header"
              style={artist?.image_url ? ({ "--artist-image": `url("${artist.image_url}")` } as CSSProperties) : undefined}
            >
              <Toggle open={open} label={artistName} onClick={() => toggle(`artist:${artistId}`)} />
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
                open={isOpen(`album:${artistId}:${album.id}`)}
                busy={action.busy}
                onToggleOpen={() => toggle(`album:${artistId}:${album.id}`)}
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

function groupByArtist(albums: CatalogAlbum[]): [string, CatalogAlbum[]][] {
  const groups = new Map<string, CatalogAlbum[]>();
  for (const album of albums) groups.set(album.artist_id, [...(groups.get(album.artist_id) ?? []), album]);
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
