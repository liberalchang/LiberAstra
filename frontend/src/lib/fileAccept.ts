/** 上传文件类型判断：accept 解析、扩展名兜底、素材类型推断。 */

const EXTENSION_MIME: Record<string, string> = {
  png: "image/png",
  jpg: "image/jpeg",
  jpeg: "image/jpeg",
  webp: "image/webp",
  gif: "image/gif",
  bmp: "image/bmp",
  tif: "image/tiff",
  tiff: "image/tiff",
  avif: "image/avif",
  svg: "image/svg+xml",
  mp4: "video/mp4",
  mov: "video/quicktime",
  avi: "video/x-msvideo",
  webm: "video/webm",
  mkv: "video/x-matroska",
  m4v: "video/x-m4v",
  flv: "video/x-flv",
  wmv: "video/x-ms-wmv",
  mp3: "audio/mpeg",
  wav: "audio/wav",
  m4a: "audio/mp4",
  ogg: "audio/ogg",
  flac: "audio/flac",
  aac: "audio/aac",
  opus: "audio/opus",
  wma: "audio/x-ms-wma",
  srt: "text/plain",
  vtt: "text/vtt",
  txt: "text/plain",
  md: "text/markdown",
  markdown: "text/markdown",
  json: "application/json",
  csv: "text/csv",
  html: "text/html",
  htm: "text/html",
};

function extension(name: string): string {
  const index = name.lastIndexOf(".");
  return index >= 0 ? name.slice(index + 1).toLowerCase() : "";
}

function effectiveMime(file: File): string {
  const mime = (file.type || "").toLowerCase();
  if (mime && mime !== "application/octet-stream") return mime;
  return EXTENSION_MIME[extension(file.name)] ?? "";
}

/** 与 <input accept> 一致：支持 MIME 通配、具体 MIME、点号扩展名和逗号组合。 */
export function matchesAccept(file: File, accept?: string): boolean {
  const tokens = (accept ?? "")
    .split(",")
    .map((token) => token.trim().toLowerCase())
    .filter(Boolean);
  if (tokens.length === 0) return true;
  const mime = effectiveMime(file);
  const name = file.name.toLowerCase();
  return tokens.some((token) => {
    if (token.startsWith(".")) return name.endsWith(token);
    if (token.endsWith("/*")) return mime.startsWith(token.slice(0, -1));
    return mime === token;
  });
}

export function filterAcceptedFiles(
  files: Iterable<File>,
  accept?: string,
): { accepted: File[]; rejected: File[] } {
  const accepted: File[] = [];
  const rejected: File[] = [];
  for (const file of files) {
    (matchesAccept(file, accept) ? accepted : rejected).push(file);
  }
  return { accepted, rejected };
}

export type InferredAssetKind = "image" | "video" | "audio" | "subtitle" | "text";

/** 素材库显式上传时推断 kind；无法判断返回 null，由调用方给出错误提示。 */
export function inferAssetKind(file: File): InferredAssetKind | null {
  const mime = effectiveMime(file);
  const ext = extension(file.name);
  if (ext === "srt" || ext === "vtt") return "subtitle";
  if (mime.startsWith("image/")) return "image";
  if (mime.startsWith("video/")) return "video";
  if (mime.startsWith("audio/")) return "audio";
  if (mime.startsWith("text/") || mime === "application/json") return "text";
  if (["txt", "md", "markdown", "json", "csv"].includes(ext)) return "text";
  return null;
}
