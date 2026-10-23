export default function PlaylistStatus({ enabled, error }: { enabled: boolean; error: string | null }) {
  if (error) return <span className="badge danger dot" title={error}>Failing</span>;
  if (!enabled) return <span className="badge warning dot">Paused</span>;
  return <span className="badge success dot">Active</span>;
}
