export function formatDuration(seconds: number): string {
  return `${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, "0")}`;
}

export function nameHue(name: string): number {
  return [...name].reduce((sum, char) => sum + char.charCodeAt(0), 0) % 360;
}

export function todayIso(): string {
  const now = new Date();
  return new Date(now.getTime() - now.getTimezoneOffset() * 60_000).toISOString().slice(0, 10);
}

export function formatDate(value: string | null): string {
  return value ? new Date(value).toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" }) : "—";
}

export function formatSchedule(intervalDays: number, time: string): string {
  return `${intervalDays === 1 ? "Every day" : `Every ${intervalDays} days`} at ${time}`;
}
