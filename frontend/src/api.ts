import type {
  AuthStatus, Catalog, CatalogStatus, Playlist, PlaylistInput, PlaylistSummary, Rotation, Rule, RuleKind, Settings,
} from "./types";

type ErrorDetail = string | { loc: (string | number)[]; msg: string }[] | undefined;

function describe(detail: ErrorDetail): string | undefined {
  if (Array.isArray(detail)) return detail.map((d) => `${d.loc.at(-1)}: ${d.msg}`).join(", ");
  return detail;
}

async function request<T>(path: string, method = "GET", body?: unknown): Promise<T> {
  const response = await fetch(`/api${path}`, {
    method,
    headers: body === undefined ? undefined : { "Content-Type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  if (!response.ok) {
    const payload = await response.json().catch(() => ({}));
    throw new Error(describe(payload.detail) ?? response.statusText);
  }
  return response.status === 204 ? (undefined as T) : response.json();
}

export const api = {
  auth: () => request<AuthStatus>("/auth"),
  settings: () => request<Settings>("/settings"),
  saveSettings: (settings: Settings) => request<Settings>("/settings", "PUT", settings),
  rules: () => request<Rule[]>("/rules"),
  createRule: (kind: RuleKind, pattern: string) => request<Rule>("/rules", "POST", { kind, pattern }),
  deleteRule: (id: number) => request<void>(`/rules/${id}`, "DELETE"),

  playlists: () => request<PlaylistSummary[]>("/playlists"),
  playlist: (id: number) => request<Playlist>(`/playlists/${id}`),
  createPlaylist: (data: PlaylistInput) => request<Playlist>("/playlists", "POST", data),
  updatePlaylist: (id: number, data: PlaylistInput) => request<Playlist>(`/playlists/${id}`, "PUT", data),
  deletePlaylist: (id: number) => request<void>(`/playlists/${id}`, "DELETE"),
  createPlaylistRule: (id: number, kind: RuleKind, pattern: string) =>
    request<Rule>(`/playlists/${id}/rules`, "POST", { kind, pattern }),

  catalog: (id: number, filters: { artistId: string; q: string; status: CatalogStatus }) => {
    const params = new URLSearchParams({ q: filters.q, status: filters.status });
    if (filters.artistId) params.set("artist_id", filters.artistId);
    return request<Catalog>(`/playlists/${id}/catalog?${params}`);
  },
  toggleAlbum: (id: number, albumId: string, disabled: boolean) =>
    request<void>(`/playlists/${id}/albums/${albumId}`, "PUT", { disabled }),
  toggleTrack: (id: number, trackId: string, disabled: boolean) =>
    request<void>(`/playlists/${id}/tracks/${trackId}`, "PUT", { disabled }),
  clearCooldowns: (id: number) => request<void>(`/playlists/${id}/clear-cooldowns`, "POST"),
  sync: (id: number) => request<void>(`/playlists/${id}/sync`, "POST"),
  rotate: (id: number, dryRun: boolean) => request<Rotation>(`/playlists/${id}/rotate?dry_run=${dryRun}`, "POST"),
};
