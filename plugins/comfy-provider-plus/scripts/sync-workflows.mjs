#!/usr/bin/env node
/**
 * 将包内 workflows/ 同步到 ~/.openclaw/workspace/workflows/comfy-plus/
 * 不修改 OpenClaw 主配置。
 */
import fs from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";

const here = path.dirname(fileURLToPath(import.meta.url));
const srcDir = path.resolve(here, "../workflows");
const destDir = path.join(os.homedir(), ".openclaw", "workspace", "workflows", "comfy-plus");

await fs.mkdir(destDir, { recursive: true });
const files = await fs.readdir(srcDir);
for (const name of files) {
  if (!name.endsWith(".json")) continue;
  await fs.copyFile(path.join(srcDir, name), path.join(destDir, name));
  console.log(`synced ${name} -> ${destDir}`);
}
