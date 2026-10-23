export function formatDuration(seconds: number): string {
  return `${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, "0")}`;
}

export function todayIso(): string {
  const now = new Date();
  return new Date(now.getTime() - now.getTimezoneOffset() * 60_000).toISOString().slice(0, 10);
}

export function formatDay(value: string): string {
  return new Date(`${value}T00:00`).toLocaleDateString(undefined, { weekday: "long", day: "numeric", month: "long", year: "numeric" });
}

export function formatDate(value: string | null): string {
  return value ? new Date(value).toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" }) : "—";
}

export function formatSchedule(intervalDays: number, time: string): string {
  return `${intervalDays === 1 ? "Every day" : `Every ${intervalDays} days`} at ${time}`;
}
