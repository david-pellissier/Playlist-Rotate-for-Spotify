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
  refresh_lookback_days: number;
}

export interface PlaylistInput {
  name: string;
  spotify_target: string;
  artist_names: string[];
  songs_per_artist: number;
  max_new_releases: number;
  update_interval_days: number;
  shuffle: boolean;
  enabled: boolean;
  min_duration: number;
  max_duration: number | null;
  solo_only: boolean;
  exclude_duplicates: boolean;
  disabled_rule_ids: number[];
}

export interface Playlist extends PlaylistInput {
  id: number;
  spotify_playlist_id: string | null;
  last_rotated_at: string | null;
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
  last_rotated_at: string | null;
  next_rotation_at: string | null;
  last_error: string | null;
}

export interface CatalogTrack {
  id: string;
  name: string;
  duration: number;
  released: string;
  exclusion: string | null;
  disabled: boolean;
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
  disabled: boolean;
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
  truncated: boolean;
}

export type CatalogStatus = "all" | "eligible" | "excluded" | "cooldown" | "current";

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
  order: Pick[];
}

export interface AuthStatus {
  configured: boolean;
  authorize_url: string | null;
}
