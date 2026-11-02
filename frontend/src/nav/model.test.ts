import assert from "node:assert/strict";
import { test } from "node:test";

import {
  NAV_ENTRIES,
  activeGroupId,
  flattenNav,
  isEntryActive,
  isGroupActive,
  isLeafActive,
  type NavGroupEntry,
  type NavLeaf,
} from "./model.ts";

const EXPECTED_PATHS = [
  "/dashboard",
  "/canvas",
  "/guide",
  "/image/generate",
  "/image/edit",
  "/image/upscale",
  "/image/depth",
  "/speech/tts",
  "/speech/asr",
  "/speech/voices",
  "/speech/music",
  "/video/quick",
  "/video/avatar",
  "/video/i2v",
  "/video/motion",
  "/video/assets",
  "/video/templates",
  "/video/characters",
  "/assets",
  "/plugins",
  "/jobs",
  "/settings",
  "/settings/workflows",
  "/settings/prompts",
  "/settings/system",
  "/docs",
  "/dev/cli",
];

function findGroup(id: string): NavGroupEntry {
  const entry = NAV_ENTRIES.find((item) => item.kind === "group" && item.id === id);
  assert.ok(entry && entry.kind === "group", `missing group ${id}`);
  return entry;
}

function activeLeaf(pathname: string): NavLeaf | null {
  for (const entry of NAV_ENTRIES) {
    if (entry.kind !== "group") continue;
    for (const section of entry.sections) {
      for (const leaf of section.items) {
        if (isLeafActive(pathname, leaf)) return leaf;
      }
    }
  }
  return null;
}

test("导航覆盖全部 27 个入口且无重复", () => {
  const paths = flattenNav().map((leaf) => leaf.href ?? leaf.to);
  assert.equal(paths.length, 27);
  assert.equal(new Set(paths).size, paths.length);
  assert.deepEqual(new Set(paths), new Set(EXPECTED_PATHS));
});

test("一级菜单为 9 项：3 个直达 + 6 个分组", () => {
  assert.equal(NAV_ENTRIES.length, 9);
  assert.equal(NAV_ENTRIES.filter((entry) => entry.kind === "link").length, 3);
  assert.equal(NAV_ENTRIES.filter((entry) => entry.kind === "group").length, 6);
});

test("画布是一级直达项，紧跟在总览之后", () => {
  assert.equal(NAV_ENTRIES[0].id, "overview");
  assert.equal(NAV_ENTRIES[1].id, "canvas");
  assert.equal(NAV_ENTRIES[1].kind, "link");
});

test("阅读组顺序为使用文档、API 文档、CLI 文档", () => {
  const reading = findGroup("reading");
  assert.deepEqual(
    reading.sections.flatMap((section) => section.items.map((item) => item.labelKey)),
    ["nav.guide", "nav.apiDocs", "nav.cliDocs"],
  );
});

test("分隔线由导航数据驱动", () => {
  const ids = NAV_ENTRIES.filter((entry) => entry.dividerBefore).map((entry) => entry.id);
  assert.deepEqual(ids, ["image", "resources", "settings"]);
});

test("每个分组都有子项和匹配前缀", () => {
  for (const entry of NAV_ENTRIES) {
    if (entry.kind !== "group") continue;
    assert.ok(entry.sections.length > 0, `${entry.id} 没有 section`);
    assert.ok(entry.match.length > 0, `${entry.id} 没有 match`);
    for (const section of entry.sections) {
      assert.ok(section.items.length > 0, `${entry.id} 有空 section`);
    }
  }
});

test("所有导航目标都是绝对路径", () => {
  for (const leaf of flattenNav()) {
    assert.ok((leaf.href ?? leaf.to).startsWith("/"), `${leaf.labelKey} 不是绝对路径`);
  }
});

test("直达项按各自匹配规则高亮", () => {
  const overview = NAV_ENTRIES.find((entry) => entry.id === "overview");
  const canvas = NAV_ENTRIES.find((entry) => entry.id === "canvas");
  const jobs = NAV_ENTRIES.find((entry) => entry.id === "jobs");
  assert.ok(overview);
  assert.ok(canvas);
  assert.ok(jobs);
  assert.equal(isEntryActive("/dashboard", overview), true);
  assert.equal(isEntryActive("/dashboard/x", overview), false);
  assert.equal(isEntryActive("/canvas", canvas), true);
  assert.equal(isEntryActive("/canvas/abc", canvas), true);
  assert.equal(isEntryActive("/canvasx", canvas), false);
  assert.equal(isEntryActive("/jobs", jobs), true);
  assert.equal(isEntryActive("/jobs/1", jobs), false);
});

test("分组与子项激活规则", () => {
  assert.equal(activeGroupId("/canvas/abc"), null);
  assert.equal(activeGroupId("/guide"), "reading");
  assert.equal(activeLeaf("/guide")?.labelKey, "nav.guide");
  assert.equal(activeGroupId("/image/edit"), "image");
  assert.equal(activeLeaf("/image/edit")?.labelKey, "nav.imageEdit");
  assert.equal(activeGroupId("/speech/tts"), "speech");
  assert.equal(activeLeaf("/speech/tts")?.labelKey, "nav.tts");
  assert.equal(activeGroupId("/video/i2v"), "video");
  assert.equal(activeLeaf("/video/i2v")?.labelKey, "nav.i2v");
  assert.equal(activeGroupId("/settings"), "settings");
  assert.equal(activeLeaf("/settings")?.labelKey, "nav.providers");
  assert.equal(activeLeaf("/settings/system")?.labelKey, "nav.system");
  assert.equal(activeGroupId("/jobs"), null);
  assert.equal(activeGroupId("/docs"), null);
  assert.equal(activeLeaf("/docs"), null);
  assert.equal(activeLeaf("/unknown"), null);
});

test("设置首页与子页不会同时高亮服务提供方", () => {
  const settings = findGroup("settings");
  const providers = settings.sections[0].items.find((leaf) => leaf.to === "/settings");
  assert.ok(providers);
  assert.equal(isLeafActive("/settings", providers), true);
  assert.equal(isLeafActive("/settings/system", providers), false);
});

test("前缀匹配有路径边界", () => {
  assert.equal(activeGroupId("/guidance"), null);
  assert.equal(activeGroupId("/imagery"), null);
  assert.equal(activeGroupId("/devil"), null);
  assert.equal(activeGroupId("/dev/cli"), "reading");
  const reading = findGroup("reading");
  assert.equal(isGroupActive("/docs", reading), false);
  assert.equal(isGroupActive("/dev/cli", reading), true);
  assert.equal(isGroupActive("/guide", reading), true);
});

test("API 文档是外链，不参与 SPA 激活", () => {
  const apiDocs = flattenNav().find((leaf) => leaf.labelKey === "nav.apiDocs");
  assert.ok(apiDocs);
  assert.equal(apiDocs.external, true);
  assert.equal(apiDocs.href, "/docs");
  assert.equal(isLeafActive("/docs", apiDocs), false);
});
