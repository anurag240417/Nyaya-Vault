// Decides how a document is presented. A "notice" is judged by the type the
// officer entered (it's a purpose, not a file format); everything else comes
// from the real MIME type of the current version, with the typed label only as
// a fallback for rows that predate the MIME field.
export function documentKind(doc) {
  const type = String(doc?.document_type || "").toLowerCase();
  if (/notice/.test(type)) return "notice";
  const mime = String(doc?.mime_type || "").toLowerCase();
  if (mime.startsWith("video/")) return "video";
  if (mime.startsWith("image/")) return "image";
  if (!mime) {
    if (/video|footage|cctv/.test(type)) return "video";
    if (/image|photo|picture/.test(type)) return "image";
  }
  return "document";
}
