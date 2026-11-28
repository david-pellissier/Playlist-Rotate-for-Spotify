import type {
  AuthStatus, Catalog, History, ImportConflict, Pick, Playlist, PlaylistInput, PlaylistSummary, Progress,
  Rotation, RotationTrack, Rule, RuleKind, Settings,
} from "./types";

export interface CatalogFilters {
  q: string;
  page: number;
  params: Record<string, string[]>;
}

type ErrorDetail = string | { loc: (string | number)[]; msg: string }[] | undefined;

function describe(detail: ErrorDetail): string | undefined {
  if (Array.isArray(detail)) return detail.map((d) => `${d.loc.at(-1)}: ${d.msg}`).join(", ");
  return detail;
}

function plannedTracks(order: Pick[]) {
  return { tracks: order.map(({ track_id, source }) => ({ track_id, source })) };
}

export class ApiError extends Error {
  constructor(message: string, readonly status: number) {
    super(message);
  }
}

async function request<T>(path: string, method = "GET", body?: unknown): Promise<T> {
  const response = await fetch(`/api${path}`, {
    method,
    headers: body === undefined ? undefined : { "Content-Type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  if (!response.ok) {
    const payload = await response.json().catch(() => ({}));
    throw new ApiError(describe(payload.detail) ?? response.statusText, response.status);
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
  setEnabled: (id: number, enabled: boolean) => request<void>(`/playlists/${id}/enabled`, "PUT", { enabled }),
  deletePlaylist: (id: number) => request<void>(`/playlists/${id}`, "DELETE"),
  exportUrl: (id: number) => `/api/playlists/${id}/export`,
  importPlaylist: (data: unknown, onConflict: ImportConflict = "fail") =>
    request<Playlist>(`/playlists/import?on_conflict=${onConflict}`, "POST", data),
  createPlaylistRule: (id: number, kind: RuleKind, pattern: string) =>
    request<Rule>(`/playlists/${id}/rules`, "POST", { kind, pattern }),

  catalog: (id: number, filters: CatalogFilters) => {
    const params = new URLSearchParams({ q: filters.q, page: String(filters.page) });
    for (const [name, values] of Object.entries(filters.params)) {
      for (const value of values) params.append(name, value);
    }
    return request<Catalog>(`/playlists/${id}/catalog?${params}`);
  },
  setAlbumEnabled: (id: number, albumId: string, enabled: boolean) =>
    request<void>(`/playlists/${id}/albums/${albumId}`, "PUT", { enabled }),
  setTrackEnabled: (id: number, trackId: string, enabled: boolean) =>
    request<void>(`/playlists/${id}/tracks/${trackId}`, "PUT", { enabled }),
  clearCooldowns: (id: number) => request<void>(`/playlists/${id}/clear-cooldowns`, "POST"),
  sync: (id: number) => request<void>(`/playlists/${id}/sync`, "POST"),
  progress: (id: number) => request<Progress | null>(`/playlists/${id}/progress`),
  history: (id: number, page: number) => request<History>(`/playlists/${id}/history?page=${page}`),
  clearHistory: (id: number) => request<void>(`/playlists/${id}/history`, "DELETE"),
  rewind: (id: number, rotationId: number) => request<void>(`/playlists/${id}/history/${rotationId}/rewind`, "POST"),
  rotationTracks: (id: number, rotationId: number) => request<RotationTrack[]>(`/playlists/${id}/history/${rotationId}`),
  rotate: (id: number, dryRun: boolean) => request<Rotation>(`/playlists/${id}/rotate?dry_run=${dryRun}`, "POST"),
  rotatePlanned: (id: number, order: Pick[]) =>
    request<Rotation>(`/playlists/${id}/rotate/planned`, "POST", plannedTracks(order)),
  savePlan: (id: number, order: Pick[]) => request<void>(`/playlists/${id}/plan`, "PUT", plannedTracks(order)),
  cancelPlan: (id: number) => request<void>(`/playlists/${id}/plan`, "DELETE"),
};
