import assert from "node:assert/strict";
import test from "node:test";

import { filterAcceptedFiles, inferAssetKind, matchesAccept } from "./fileAccept.ts";

function file(name: string, type = ""): File {
  return new File([new Uint8Array([1])], name, { type });
}

test("MIME 通配匹配扩展名兜底", () => {
  assert.equal(matchesAccept(file("a.png", "image/png"), "image/*"), true);
  assert.equal(matchesAccept(file("a.png", "image/png"), "video/*"), false);
  assert.equal(matchesAccept(file("a.mp3"), "audio/*"), true);
  assert.equal(matchesAccept(file("a.mp4", "application/octet-stream"), "video/*"), true);
  assert.equal(matchesAccept(file("a.bin", "application/octet-stream"), "video/*"), false);
});

test("扩展名与 text/plain 组合", () => {
  const accept = ".srt,text/plain";
  assert.equal(matchesAccept(file("a.srt"), accept), true);
  assert.equal(matchesAccept(file("a.srt", "application/x-subrip"), accept), true);
  assert.equal(matchesAccept(file("a.srt", "text/plain"), accept), true);
  assert.equal(matchesAccept(file("a.png", "image/png"), accept), false);
});

test("大小写和多类型", () => {
  assert.equal(matchesAccept(file("A.HTML", "text/html"), ".html,text/html"), true);
  assert.equal(matchesAccept(file("a.webm", "video/webm"), "image/*,video/*"), true);
  assert.equal(matchesAccept(file("a.txt", "text/plain"), ""), true);
});

test("filterAcceptedFiles 保留顺序并返回被拒文件", () => {
  const ok = file("ok.png", "image/png");
  const bad = file("bad.mp4", "video/mp4");
  const result = filterAcceptedFiles([ok, bad], "image/*");
  assert.deepEqual(result.accepted, [ok]);
  assert.deepEqual(result.rejected, [bad]);
});

test("inferAssetKind 按 MIME 与扩展名推断", () => {
  assert.equal(inferAssetKind(file("a.png", "image/png")), "image");
  assert.equal(inferAssetKind(file("a.mp4")), "video");
  assert.equal(inferAssetKind(file("a.m4a", "application/octet-stream")), "audio");
  assert.equal(inferAssetKind(file("a.srt")), "subtitle");
  assert.equal(inferAssetKind(file("a.md", "text/markdown")), "text");
  assert.equal(inferAssetKind(file("a.bin")), null);
});
