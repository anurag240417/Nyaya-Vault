export function formatDate(value) {
  if (!value) return "—";
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value));
}
export function formatBytes(bytes) {
  const v = Number(bytes);
  if (!Number.isFinite(v)) return "—";
  if (v === 0) return "0 B";
  const u = ["B", "KB", "MB", "GB"];
  const i = Math.min(Math.floor(Math.log(v) / Math.log(1024)), u.length - 1);
  return `${(v / 1024 ** i).toFixed(i === 0 ? 0 : 1)} ${u[i]}`;
}
export function shortHash(value, length = 10) {
  return value ? `${value.slice(0, length)}…` : "—";
}
export function initials(name) {
  if (!name) return "?";
  return name
    .split(/[\s._-]+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((p) => p[0].toUpperCase())
    .join("");
}
