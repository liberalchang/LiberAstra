/**
 * 把 VitePress 构建结果嵌入 frontend/dist/manual，供后端以 /manual/ 托管。
 * 应用内 base 固定为 /manual/；GitHub Pages 仍用默认 /LiberAstra/docs/。
 *
 * 路径兼容：
 * - 本地仓库：frontend/scripts → 仓库根/site/docs-src
 * - Docker：WORKDIR=/build（即 frontend），文档源在 /site/docs-src
 */
import { spawnSync } from "node:child_process";
import { cpSync, existsSync, mkdirSync, rmSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const frontendRoot = resolve(here, "..");
const docsSrcCandidates = [
  resolve(frontendRoot, "../site/docs-src"),
  resolve("/site/docs-src"),
];
const docsSrc = docsSrcCandidates.find((path) => existsSync(resolve(path, "package.json")));
const dest = resolve(frontendRoot, "dist/manual");

function run(command, args, cwd, env = {}) {
  const result = spawnSync(command, args, {
    cwd,
    env: { ...process.env, ...env },
    stdio: "inherit",
    shell: true,
  });
  if (result.status !== 0) {
    process.exit(result.status ?? 1);
  }
}

if (!docsSrc) {
  console.error("找不到 site/docs-src/package.json");
  process.exit(1);
}

const built = resolve(docsSrc, "../docs");

if (!existsSync(resolve(docsSrc, "node_modules"))) {
  run("npm", ["install", "--no-audit", "--no-fund"], docsSrc);
}

run("npm", ["run", "build"], docsSrc, { DOCS_BASE: "/manual/" });

if (!existsSync(resolve(built, "index.html"))) {
  console.error(`VitePress 未生成 ${resolve(built, "index.html")}`);
  process.exit(1);
}

rmSync(dest, { recursive: true, force: true });
mkdirSync(dirname(dest), { recursive: true });
cpSync(built, dest, { recursive: true });
console.log(`已嵌入使用文档 → ${dest}`);
