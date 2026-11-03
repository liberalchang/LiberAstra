import assert from "node:assert/strict";
import { test } from "node:test";

import { hasTemplateIdConflict } from "./promptTemplates.ts";

test("新建模板 ID 与现有条目重复时判定冲突", () => {
  assert.equal(hasTemplateIdConflict("t2i", ["t2i", "i2i"]), true);
  assert.equal(hasTemplateIdConflict("  t2i  ", ["t2i"]), true);
});

test("唯一 ID、空 ID 与大小写不同 ID 不冲突", () => {
  assert.equal(hasTemplateIdConflict("my_task", ["t2i", "i2i"]), false);
  assert.equal(hasTemplateIdConflict("   ", ["t2i"]), false);
  assert.equal(hasTemplateIdConflict("T2I", ["t2i"]), false);
});
