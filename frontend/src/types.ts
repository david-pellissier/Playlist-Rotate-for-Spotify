export type RuleKind = "keyword" | "regex";

export interface Rule {
  id: number;
  kind: RuleKind;
  pattern: string;
}

export interface Settings {
  min_cooldown: number;
  min_duration: number;
  max_duration: number | null;
  solo_only: boolean;
  exclude_duplicates: boolean;
  albums_only: boolean;
  refresh_lookback_days: number;
}

export type ArtistSelection = "fair" | "random";

export interface PlaylistInput {
  name: string;
  spotify_target: string;
  artists: string;
  songs_per_artist: number;
  max_artists: number | null;
  artist_selection: ArtistSelection;
  max_new_releases: number;
  update_interval_days: number;
  first_rotation_date: string;
  rotation_time: string;
  shuffle: boolean;
  enabled: boolean;
  min_duration: number;
  max_duration: number | null;
  solo_only: boolean;
  exclude_duplicates: boolean;
  albums_only: boolean;
  disabled_rule_ids: number[];
}

export interface Playlist extends PlaylistInput {
  id: number;
  artist_names: string[];
  spotify_playlist_id: string | null;
  last_rotated_at: string | null;
  next_rotation_at: string;
  last_error: string | null;
  rules: Rule[];
}

export interface PlaylistSummary {
  id: number;
  name: string;
  spotify_target: string;
  artist_count: number;
  enabled: boolean;
  update_interval_days: number;
  rotation_time: string;
  last_rotated_at: string | null;
  next_rotation_at: string;
  last_error: string | null;
}

export type ExcludedBy = "user" | "auto" | "album" | null;

export interface CatalogTrack {
  id: string;
  name: string;
  duration: number;
  released: string;
  exclusion: string | null;
  excluded_by: ExcludedBy;
  forced: boolean;
  new_release: boolean;
  cooldown: number;
  current: boolean;
  play_count: number;
}

export interface CatalogAlbum {
  id: string;
  artist_name: string;
  name: string;
  album_type: string;
  release_date: string;
  image_url: string | null;
  exclusion: string | null;
  excluded_by: ExcludedBy;
  forced: boolean;
  tracks: CatalogTrack[];
}

export interface CatalogArtist {
  id: string;
  name: string;
  total: number;
  eligible: number;
  on_cooldown: number;
}

export interface Catalog {
  artists: CatalogArtist[];
  missing_artists: string[];
  albums: CatalogAlbum[];
  total_tracks: number;
  page: number;
  page_size: number;
}

export type CatalogStatus = "all" | "eligible" | "new" | "excluded" | "cooldown" | "current";

export interface Pick {
  track_id: string;
  name: string;
  album_name: string;
  artist_name: string;
  duration: number;
  source: "new" | "random" | "cooldown";
}

export interface Rotation {
  dry_run: boolean;
  selections: { artist_name: string; eligible: number; cooldown: number; picks: Pick[] }[];
  missing_artists: string[];
  skipped_artists: string[];
  order: Pick[];
}

export interface Progress {
  step: string;
  done: number;
  total: number;
}

export type ImportConflict = "fail" | "replace" | "copy";

export interface AuthStatus {
  configured: boolean;
  authorize_url: string | null;
}

export interface RotationSummary {
  id: number;
  rotated_at: string;
  trigger: "manual" | "scheduled";
  error: string | null;
  track_count: number;
  new_releases: number;
}

export interface History {
  rotations: RotationSummary[];
  total: number;
  page: number;
  page_size: number;
}

export interface RotationTrack {
  position: number;
  track_id: string;
  name: string;
  artist_name: string;
  album_name: string;
  duration: number;
  source: Pick["source"];
}
