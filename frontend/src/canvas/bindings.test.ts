import assert from "node:assert/strict";
import { test } from "node:test";

import { bindingSources, findNodeByVar, missingBindingEdges } from "./bindings.ts";
import type { CanvasFlowNode } from "./types.ts";

function node(
  id: string,
  varName: string,
  mediaKind: "image" | "text" | "character",
): CanvasFlowNode {
  return {
    id,
    type: "input",
    position: { x: 0, y: 0 },
    data: { kind: "input", mediaKind, varName },
  } as unknown as CanvasFlowNode;
}

test("绑定源按变量找到画布节点并区分媒体类型", () => {
  const nodes = [
    node("img", "input_image_ref", "image"),
    node("character", "input_character_heroine", "character"),
    node("text", "input_text_script", "text"),
  ];
  const sources = bindingSources(nodes, {
    image: "input_image_ref",
    reference: "input_character_heroine",
    prompt: "input_text_script",
    missing: "input_image_ghost",
  });
  assert.deepEqual(
    sources.map((item) => [item.varName, item.node?.id ?? null, item.mediaKind]),
    [
      ["input_image_ref", "img", "image"],
      ["input_character_heroine", "character", "image"],
      ["input_text_script", "text", null],
      ["input_image_ghost", null, null],
    ],
  );
});

test("同一个变量被多个槽位引用时只返回一次", () => {
  const nodes = [node("img", "input_image_ref", "image")];
  const sources = bindingSources(nodes, {
    first_frame: "input_image_ref",
    last_frame: "input_image_ref",
  });
  assert.deepEqual(sources.map((item) => item.varName), ["input_image_ref"]);
});

test("按变量名查找节点，空变量返回 null", () => {
  const nodes = [node("img", "input_image_ref", "image")];
  assert.equal(findNodeByVar(nodes, "input_image_ref")?.id, "img");
  assert.equal(findNodeByVar(nodes, "input_image_ghost"), null);
  assert.equal(findNodeByVar(nodes, ""), null);
});

test("媒体绑定缺边时返回修复项，文本绑定和已有边不返回", () => {
  const nodes = [
    node("img", "output_image_kf_1", "image"),
    {
      id: "audio",
      type: "concat",
      position: { x: 0, y: 0 },
      data: { kind: "concat", mediaKind: "audio", order: [], varName: "output_audio_tail_2" },
    },
    node("text", "input_text_script", "text"),
    {
      id: "video",
      type: "function",
      position: { x: 0, y: 0 },
      data: {
        kind: "function",
        varName: "output_video_2",
        outputKind: "video",
        bindings: {
          image: "output_image_kf_1",
          ref_audio: "output_audio_tail_2",
          prompt: "input_text_script",
        },
      },
    },
  ] as unknown as CanvasFlowNode[];

  const missing = missingBindingEdges(nodes, [{ source: "img", target: "video" }]);
  assert.deepEqual(missing, [
    {
      source: "audio",
      target: "video",
      varName: "output_audio_tail_2",
      slot: "ref_audio",
    },
  ]);

  assert.deepEqual(
    missingBindingEdges(nodes, [
      { source: "img", target: "video" },
      { source: "audio", target: "video" },
    ]),
    [],
  );
});
